"""Formatos de salida. Las medidas salen del storefront (object-fit: contain, límite de 5 MB en
ecommerce-api) y de la API de Instagram (JPEG, proporción entre 4:5 y 1.91:1)."""

from dataclasses import dataclass
from typing import Literal

from app.contracts.options import Preset

OutputFormat = Literal["webp", "jpeg", "png"]


@dataclass(frozen=True)
class PresetSpec:
    width: int | None
    height: int | None
    format: OutputFormat
    quality: int
    default_fill_ratio: float
    max_bytes: int | None = None
    # Solo original_hd: lado largo fijo y sin lienzo cuadrado.
    long_side: int | None = None


PRESETS: dict[Preset, PresetSpec] = {
    "storefront": PresetSpec(2000, 2000, "webp", 90, 0.82, max_bytes=5 * 1024 * 1024),
    "instagram_feed": PresetSpec(1080, 1350, "jpeg", 92, 0.75),
    "instagram_square": PresetSpec(1080, 1080, "jpeg", 92, 0.75),
    "original_hd": PresetSpec(None, None, "png", 100, 0.9, long_side=3000),
}
