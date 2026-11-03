"""Descarga los pesos de los modelos a MODELS_DIR y verifica su integridad.

Uso: python -m scripts.download_models [--upscale realesrgan_x2plus,nomos8k_dat | --upscale all] [--local-ai]
Por defecto descarga BiRefNet y el modelo de ampliación por defecto de Ajustes > Proceso.
Con --local-ai también baja la IA generativa local de la Fase 14 (~9 GB; ver LOCAL_AI_REPOS).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import get_args

import httpx

from app.config import get_settings
from app.contracts import UpscaleModel
from app.contracts.settings import PipelineSettings
from app.pipeline.catalog import UPSCALE_MODELS, UpscaleModelSpec, model_path

BIREFNET_REPO = "ZhengPeng7/BiRefNet"

# F14: IA generativa local. Todas permiten uso comercial. Solo se bajan los pesos en fp16 (la mitad).
# carpeta en MODELS_DIR -> (repositorio, archivos, licencia)
LOCAL_AI_REPOS: dict[str, tuple[str, list[str], str]] = {
    # Modelo base de Stable Diffusion XL: el que redibuja.
    "sdxl": (
        "stabilityai/stable-diffusion-xl-base-1.0",
        [
            "model_index.json",
            "scheduler/*",
            "tokenizer/*",
            "tokenizer_2/*",
            "text_encoder/config.json",
            "text_encoder/model.fp16.safetensors",
            "text_encoder_2/config.json",
            "text_encoder_2/model.fp16.safetensors",
            "unet/config.json",
            "unet/diffusion_pytorch_model.fp16.safetensors",
        ],
        "CreativeML Open RAIL++-M",
    ),
    # VAE de SDXL corregido para fp16 (el original da imágenes negras en media precisión).
    "sdxl_vae": (
        "madebyollin/sdxl-vae-fp16-fix",
        ["config.json", "diffusion_pytorch_model.safetensors"],
        "MIT",
    ),
    # ControlNet Tile: obliga al redibujo a respetar la forma y los colores de la foto.
    "controlnet_tile": (
        "xinsir/controlnet-tile-sdxl-1.0",
        ["config.json", "diffusion_pytorch_model.safetensors"],
        "Apache-2.0",
    ),
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_upscaler(models_dir: Path, spec: UpscaleModelSpec) -> Path:
    target = model_path(models_dir, spec.id)
    if target.exists() and sha256_of(target) == spec.sha256:
        print(f"{spec.id}: ya descargado ({target})")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    print(f"{spec.id}: descargando {spec.size_mb} MB...")
    with httpx.stream("GET", spec.url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes(1024 * 1024):
                handle.write(chunk)
    actual = sha256_of(partial)
    if actual != spec.sha256:
        partial.unlink()
        raise RuntimeError(f"Hash inválido para {spec.file}: {actual}")
    partial.replace(target)
    print(f"{spec.id}: OK ({target})")
    return target


def download_birefnet(models_dir: Path) -> str:
    """huggingface_hub verifica el SHA-256 de los archivos LFS durante la descarga."""
    from huggingface_hub import HfApi, snapshot_download

    target = models_dir / "birefnet"
    revision = HfApi().model_info(BIREFNET_REPO).sha
    print(f"BiRefNet: descargando revisión {revision}...")
    snapshot_download(BIREFNET_REPO, revision=revision, local_dir=target)
    print(f"BiRefNet: OK ({target})")
    return str(revision)


def download_local_ai(models_dir: Path) -> dict[str, dict[str, str]]:
    """Baja cada repositorio en su revisión actual y la deja anotada en el manifiesto (huggingface_hub
    verifica el SHA-256 de los archivos LFS)."""
    from huggingface_hub import HfApi, snapshot_download

    entries: dict[str, dict[str, str]] = {}
    for folder, (repo, patterns, license_name) in LOCAL_AI_REPOS.items():
        revision = str(HfApi().model_info(repo).sha)
        print(f"{folder}: descargando {repo} revisión {revision}...")
        snapshot_download(repo, revision=revision, local_dir=models_dir / folder, allow_patterns=patterns)
        entries[folder] = {"repo": repo, "revision": revision, "path": folder, "license": license_name}
        print(f"{folder}: OK ({models_dir / folder})")
    return entries


def _upscale_choice(value: str) -> list[UpscaleModel]:
    known: tuple[UpscaleModel, ...] = get_args(UpscaleModel)
    if value == "all":
        return list(known)
    chosen = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in chosen if item not in known]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"Modelos desconocidos: {', '.join(unknown)}. Opciones: {', '.join(known)}"
        )
    return [model for model in known if model in chosen]


def main() -> int:
    default = PipelineSettings().upscale_model
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upscale",
        type=_upscale_choice,
        default=[] if default == "lanczos" else [default],
        help="Modelos de ampliación separados por coma, o 'all'.",
    )
    parser.add_argument(
        "--local-ai",
        action="store_true",
        help="También baja la IA generativa local (SDXL + ControlNet Tile, ~9 GB).",
    )
    args = parser.parse_args()

    models_dir = get_settings().models_dir
    models_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = models_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}
    for model in args.upscale:
        spec = UPSCALE_MODELS[model]
        path = download_upscaler(models_dir, spec)
        manifest[model] = {
            "sha256": spec.sha256,
            "path": str(path.relative_to(models_dir)),
            "license": spec.license,
        }
    birefnet_revision = download_birefnet(models_dir)
    manifest["birefnet"] = {"repo": BIREFNET_REPO, "revision": birefnet_revision, "path": "birefnet"}
    if args.local_ai:
        manifest.update(download_local_ai(models_dir))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifiesto: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
