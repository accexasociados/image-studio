"""Modelos de mejora de resolución que se pueden elegir en Ajustes > Proceso.

Sin dependencias pesadas: lo usan la API (para listar cuáles están instalados), el proceso y el
script de descarga. Cada `id` debe existir en `UpscaleModel` (contracts/settings.py).
"""

from dataclasses import dataclass
from pathlib import Path

from app.contracts.settings import UpscaleModel


@dataclass(frozen=True)
class UpscaleModelSpec:
    id: UpscaleModel
    file: str  # relativo a MODELS_DIR
    url: str
    sha256: str
    scale: int
    size_mb: int
    license: str


UPSCALE_MODELS: dict[UpscaleModel, UpscaleModelSpec] = {
    spec.id: spec
    for spec in (
        UpscaleModelSpec(
            "realesrgan_x2plus",
            "realesrgan/RealESRGAN_x2plus.pth",
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
            "49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb",
            2,
            64,
            "BSD-3-Clause",
        ),
        UpscaleModelSpec(
            "nmkd_siax",
            "upscale/4x_NMKD-Siax_200k.pth",
            "https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth",
            # Mismo SHA-256 que publica OpenModelDB (4x-NMKD-Siax-CX).
            "560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e",
            4,
            64,
            "WTFPL",
        ),
    )
}


def model_path(models_dir: Path, model: UpscaleModel) -> Path:
    return models_dir / UPSCALE_MODELS[model].file
