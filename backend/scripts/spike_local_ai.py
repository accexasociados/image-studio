"""F14 · Prueba de IA generativa local: redibuja una foto con SDXL + ControlNet Tile y mide el tiempo.

No toca el estudio ni la base de datos: lee una imagen y escribe resultados en --out.
ControlNet Tile obliga al redibujo a respetar la forma y los colores de la foto; `strength` es cuánto se
redibuja (0,3 = retoque fino, 0,6 = inventa bastante detalle).

Uso (desde backend/, con `pip install -e ".[ml,local-ai]"` y `python -m scripts.download_models --local-ai`):

    python -m scripts.spike_local_ai --input <foto> --out <carpeta> [--strengths 0.3,0.45,0.6]
        [--size 1024] [--dtype fp16|fp32] [--offload model|sequential] [--steps 30] [--reference <foto>]

En una GTX 1660 (6 GB): empezar con --dtype fp16 --offload model. Si sale sin memoria, --offload sequential
(más lento). Si las imágenes salen negras o grises (la serie 16 a veces falla en fp16), --dtype fp32
--offload sequential. El script avisa si detecta una imagen negra.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from app.config import get_settings

PROMPT = (
    "professional product photograph of a hand-painted miniature figurine, sharp focus, crisp fine details, "
    "clean paint, soft studio lighting, macro lens, high detail, photorealistic"
)
NEGATIVE = (
    "blurry, soft focus, noise, jpeg artifacts, cartoon, illustration, anime, 3d render, painting, "
    "deformed, extra limbs, text, watermark, low quality"
)


def _load_pipeline(models_dir: Path, dtype_name: str, offload: str) -> Any:
    import torch
    from diffusers import AutoencoderKL, ControlNetModel, StableDiffusionXLControlNetImg2ImgPipeline

    dtype = torch.float16 if dtype_name == "fp16" else torch.float32
    controlnet = ControlNetModel.from_pretrained(models_dir / "controlnet_tile", torch_dtype=dtype)
    vae = AutoencoderKL.from_pretrained(models_dir / "sdxl_vae", torch_dtype=dtype)
    # Los pesos del modelo base están solo en fp16: en fp32 se cargan igual y se convierten.
    pipe = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
        models_dir / "sdxl", controlnet=controlnet, vae=vae, torch_dtype=dtype, variant="fp16"
    )
    if offload == "sequential":
        pipe.enable_sequential_cpu_offload()
    else:
        pipe.enable_model_cpu_offload()
    pipe.enable_vae_tiling()
    pipe.enable_attention_slicing()
    pipe.set_progress_bar_config(disable=False)
    return pipe


def _prepare(path: Path, long_side: int) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    scale = long_side / max(image.size)
    # SDXL trabaja en múltiplos de 8 (mejor de 64).
    width = max(round(image.width * scale / 64) * 64, 64)
    height = max(round(image.height * scale / 64) * 64, 64)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _is_black(image: Image.Image) -> bool:
    return float(np.asarray(image, np.float32).mean()) < 8.0


def _sheet(tiles: list[tuple[str, Image.Image]], target: Path, height: int = 900) -> None:
    resized = [(label, im.resize((round(height * im.width / im.height), height))) for label, im in tiles]
    width = sum(im.width for _, im in resized) + 20 * (len(resized) - 1)
    sheet = Image.new("RGB", (width, height + 40), "white")
    draw = ImageDraw.Draw(sheet)
    x = 0
    for label, im in resized:
        draw.text((x + 8, 10), label, fill="black")
        sheet.paste(im, (x, 40))
        x += im.width + 20
    sheet.save(target, quality=90)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strengths", default="0.3,0.45,0.6")
    parser.add_argument("--size", type=int, default=1024, help="Lado mayor en píxeles (SDXL: 1024).")
    parser.add_argument("--dtype", choices=["fp16", "fp32"], default="fp16")
    parser.add_argument("--offload", choices=["model", "sequential"], default="model")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--guidance", type=float, default=5.0)
    parser.add_argument("--control", type=float, default=0.9, help="Peso del ControlNet (fidelidad).")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--reference", type=Path, help="Imagen para comparar (p. ej. la de ChatGPT).")
    args = parser.parse_args()

    import torch

    args.out.mkdir(parents=True, exist_ok=True)
    models_dir = get_settings().models_dir
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "sin GPU"
    print(f"GPU: {gpu} · dtype {args.dtype} · offload {args.offload}")

    started = time.perf_counter()
    pipe = _load_pipeline(models_dir, args.dtype, args.offload)
    load_s = time.perf_counter() - started
    print(f"Modelos cargados en {load_s:.0f} s")

    source = _prepare(args.input, args.size)
    tiles: list[tuple[str, Image.Image]] = [("original", source)]
    report: dict[str, Any] = {
        "gpu": gpu,
        "dtype": args.dtype,
        "offload": args.offload,
        "size": list(source.size),
        "steps": args.steps,
        "control": args.control,
        "load_seconds": round(load_s, 1),
        "runs": [],
    }
    for value in [float(item) for item in args.strengths.split(",") if item.strip()]:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        result = pipe(
            prompt=PROMPT,
            negative_prompt=NEGATIVE,
            image=source,
            control_image=source,
            strength=value,
            num_inference_steps=args.steps,
            guidance_scale=args.guidance,
            controlnet_conditioning_scale=args.control,
            generator=torch.Generator("cpu").manual_seed(args.seed),
        ).images[0]
        seconds = time.perf_counter() - started
        peak = torch.cuda.max_memory_allocated() / 2**30 if torch.cuda.is_available() else 0.0
        black = _is_black(result)
        name = f"strength_{value:.2f}.png"
        result.save(args.out / name)
        tiles.append((f"strength {value:.2f} · {seconds:.0f} s", result))
        report["runs"].append(
            {"strength": value, "seconds": round(seconds, 1), "peak_vram_gb": round(peak, 2), "black": black}
        )
        print(
            f"strength {value:.2f}: {seconds:.0f} s, memoria de video máx. {peak:.1f} GB"
            + ("  ¡IMAGEN NEGRA! repetir con --dtype fp32 --offload sequential" if black else "")
        )
    if args.reference:
        tiles.append(("referencia", ImageOps.exif_transpose(Image.open(args.reference)).convert("RGB")))
    _sheet(tiles, args.out / "comparacion.jpg")
    (args.out / "informe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Listo: {args.out / 'comparacion.jpg'} y {args.out / 'informe.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
