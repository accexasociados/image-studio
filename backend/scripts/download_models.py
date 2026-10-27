"""Descarga los pesos de los modelos a MODELS_DIR y verifica su integridad.

Uso: python -m scripts.download_models
"""

import hashlib
import json
import sys
from pathlib import Path

import httpx

from app.config import get_settings

BIREFNET_REPO = "ZhengPeng7/BiRefNet"
REALESRGAN_X2 = {
    "file": "RealESRGAN_x2plus.pth",
    "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    "sha256": "49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb",
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_realesrgan(models_dir: Path) -> Path:
    target = models_dir / "realesrgan" / REALESRGAN_X2["file"]
    if target.exists() and sha256_of(target) == REALESRGAN_X2["sha256"]:
        print(f"Real-ESRGAN x2: ya descargado ({target})")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    print("Real-ESRGAN x2: descargando...")
    with httpx.stream("GET", REALESRGAN_X2["url"], follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes(1024 * 1024):
                handle.write(chunk)
    actual = sha256_of(partial)
    if actual != REALESRGAN_X2["sha256"]:
        partial.unlink()
        raise RuntimeError(f"Hash inválido para {REALESRGAN_X2['file']}: {actual}")
    partial.replace(target)
    print(f"Real-ESRGAN x2: OK ({target})")
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


def main() -> int:
    models_dir = get_settings().models_dir
    models_dir.mkdir(parents=True, exist_ok=True)
    realesrgan = download_realesrgan(models_dir)
    birefnet_revision = download_birefnet(models_dir)
    manifest = {
        "birefnet": {"repo": BIREFNET_REPO, "revision": birefnet_revision, "path": "birefnet"},
        "realesrgan_x2plus": {
            "sha256": REALESRGAN_X2["sha256"],
            "path": str(realesrgan.relative_to(models_dir)),
        },
    }
    (models_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifiesto: {models_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
