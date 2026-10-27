"""Descarga los pesos de los modelos a MODELS_DIR y verifica su integridad.

Uso: python -m scripts.download_models [--upscale realesrgan_x2plus,nomos8k_dat | --upscale all]
Por defecto descarga BiRefNet y el modelo de ampliación por defecto de Ajustes > Proceso.
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
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifiesto: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
