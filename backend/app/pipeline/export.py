"""Formatos de salida: aplica los ajustes de Ajustes > Formatos sobre los presets por defecto,
guarda con perfil sRGB y respeta el peso máximo (5 MB en storefront)."""

import io
import re
import unicodedata
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageCms

from app.contracts import PRESETS, Preset, PresetSpec
from app.contracts.settings import ExportSettings
from app.pipeline.types import FloatImage, to_uint8

_EXTENSIONS = {"webp": "webp", "jpeg": "jpg", "png": "png"}
_SRGB_PROFILE = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def resolve_preset(preset: Preset, export: ExportSettings | None) -> PresetSpec:
    spec = PRESETS[preset]
    override = export.presets.get(preset) if export else None
    if override is None:
        return spec
    return replace(
        spec,
        width=override.width or spec.width,
        height=override.height or spec.height,
        format=override.format or spec.format,
        quality=override.quality or spec.quality,
        default_fill_ratio=override.fill_ratio or spec.default_fill_ratio,
        max_bytes=override.max_bytes or spec.max_bytes,
    )


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "imagen"


def output_path(out_dir: Path, base_name: str, preset: Preset, spec: PresetSpec, variant_suffix: str) -> Path:
    preset_suffix = "" if preset == "storefront" else f"_{preset}"
    return out_dir / f"{base_name}{preset_suffix}{variant_suffix}.{_EXTENSIONS[spec.format]}"


def encode(image: FloatImage, spec: PresetSpec) -> bytes:
    """Codifica bajando la calidad de 4 en 4 hasta cumplir `max_bytes` (mínimo 60)."""
    picture = Image.fromarray(to_uint8(image), "RGB")
    quality = spec.quality
    while True:
        buffer = io.BytesIO()
        if spec.format == "png":
            picture.save(buffer, format="PNG", icc_profile=_SRGB_PROFILE, optimize=True)
        else:
            picture.save(buffer, format=spec.format.upper(), quality=quality, icc_profile=_SRGB_PROFILE)
        data = buffer.getvalue()
        if spec.max_bytes is None or len(data) <= spec.max_bytes or spec.format == "png" or quality <= 60:
            return data
        quality -= 4
