"""Punto de entrada del proceso de imagen. No depende de FastAPI ni de la BD: lo llaman el worker,
la CLI y cualquier otra entrada.

Modo `stub` (PIPELINE_MODE=stub): pega la foto sobre el lienzo de cada formato sin IA, para que la
API y la web avancen sin GPU. El modo `real` se implementa en la Fase 1."""

import time
from pathlib import Path

from PIL import Image, ImageOps

from app.config import get_settings
from app.contracts import PRESETS, OutputFile, Preset, ProcessOptions, ProcessResult

_EXTENSIONS = {"webp": "webp", "jpeg": "jpg", "png": "png"}


def process_image(
    input_path: Path,
    options: ProcessOptions,
    out_dir: Path,
    *,
    base_name: str,
    mask_override: Path | None = None,
) -> ProcessResult:
    if get_settings().pipeline_mode == "stub":
        return _process_stub(input_path, options, out_dir, base_name=base_name)
    raise NotImplementedError("El proceso real llega en la Fase 1; usa PIPELINE_MODE=stub mientras tanto.")


def _process_stub(
    input_path: Path, options: ProcessOptions, out_dir: Path, *, base_name: str
) -> ProcessResult:
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(input_path) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")

    outputs = [_render_preset(source, preset, options, out_dir, base_name) for preset in options.presets]
    return ProcessResult(outputs=outputs, timings_ms={"total": (time.perf_counter() - started) * 1000})


def _render_preset(
    source: Image.Image, preset: Preset, options: ProcessOptions, out_dir: Path, base_name: str
) -> OutputFile:
    spec = PRESETS[preset]
    fill = options.fill_ratio or spec.default_fill_ratio
    if spec.width is None or spec.height is None:
        long_side = spec.long_side or max(source.size)
        scale = long_side / max(source.size)
        canvas = source.resize(
            (round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS
        )
    else:
        canvas = Image.new("RGB", (spec.width, spec.height), "#FFFFFF")
        scale = min(spec.width * fill / source.width, spec.height * fill / source.height)
        piece = source.resize(
            (round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS
        )
        canvas.paste(piece, ((spec.width - piece.width) // 2, (spec.height - piece.height) // 2))

    suffix = "" if preset == "storefront" else f"_{preset}"
    path = out_dir / f"{base_name}{suffix}.{_EXTENSIONS[spec.format]}"
    save_kwargs: dict[str, int | bool] = {} if spec.format == "png" else {"quality": spec.quality}
    canvas.save(path, format=spec.format.upper(), **save_kwargs)
    return OutputFile(
        preset=preset,
        path=str(path),
        width=canvas.width,
        height=canvas.height,
        bytes=path.stat().st_size,
        variant=options.layer_lines,
    )
