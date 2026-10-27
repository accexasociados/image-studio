"""Proceso real sin GPU: máscara dada (mask_override) y mejora de resolución "lanczos"."""

from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from app.config import get_settings
from app.contracts import AppSettings, ProcessOptions
from app.contracts.settings import PresetOverride
from app.pipeline.color import correct_color
from app.pipeline.compose import Crop, compose_on_canvas
from app.pipeline.export import encode, resolve_preset, slugify
from app.pipeline.layers import smooth_layer_lines
from app.pipeline.quality import review_reasons
from app.pipeline.run import process_image
from app.pipeline.shadow import ShadowParams, resolve_shadow, shadow_map


def _scene(width: int = 600, height: int = 800) -> tuple[np.ndarray, np.ndarray]:
    """Cartulina gris azulada con una pieza naranja con "líneas de capa" (rayas finas)."""
    image = np.empty((height, width, 3), np.float32)
    image[:] = (0.70, 0.73, 0.80)
    alpha = np.zeros((height, width), np.float32)
    cv2.ellipse(alpha, (width // 2, height // 2), (width // 4, height // 3), 0, 0, 360, 1.0, -1)
    stripes = (np.arange(height) % 4 < 2).astype(np.float32)[:, None] * 0.06
    piece = np.stack([0.85 - stripes, 0.40 - stripes, 0.10 + 0 * stripes], axis=-1).repeat(width, axis=1)
    image = image * (1 - alpha[..., None]) + piece * alpha[..., None]
    return image.astype(np.float32), alpha


@pytest.fixture
def real_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_MODE", "real")
    monkeypatch.setenv("DEVICE", "cpu")
    get_settings.cache_clear()


def test_white_balance_neutralizes_bluish_background() -> None:
    image, alpha = _scene()
    result = correct_color(image, alpha, white_balance=True)
    background = result.image[alpha < 0.01].mean(axis=0)
    assert result.white_balance_applied
    assert background.max() - background.min() < 0.03


def test_white_balance_skips_colorful_background() -> None:
    image, alpha = _scene()
    image[alpha < 0.01] = (0.45, 0.30, 0.75)  # cajas moradas: no es referencia neutra
    assert not correct_color(image, alpha, white_balance=True).white_balance_applied


def test_shadow_auto_is_strong_for_light_pieces() -> None:
    image, alpha = _scene()
    assert resolve_shadow("auto", image, alpha, ShadowParams()) == "soft"
    white = np.ones_like(image)
    assert resolve_shadow("auto", white, alpha, ShadowParams()) == "strong"
    assert shadow_map(alpha, "none", ShadowParams()).max() == 0.0
    normal = shadow_map(alpha, "soft", ShadowParams()).max()
    assert shadow_map(alpha, "soft", ShadowParams(intensity=2.0)).max() > normal * 1.9
    assert shadow_map(alpha, "soft", ShadowParams(intensity=0.0)).max() == 0.0


def test_compose_keeps_pure_white_background_and_contact_shadow() -> None:
    image, alpha = _scene()
    canvas = compose_on_canvas(Crop(image, alpha), (1000, 1000), 0.8, "soft")
    as_bytes = np.clip(np.rint(canvas * 255), 0, 255).astype(np.uint8)
    assert (as_bytes[:40, :40] == 255).all()
    assert (as_bytes[:, :20] == 255).all()
    rows = np.flatnonzero((as_bytes < 250).any(axis=(1, 2)))
    assert as_bytes[rows[-1]].min() < 255  # hay sombra bajo la base
    assert 0.75 <= (rows[-1] - rows[0]) / 1000 <= 0.9


def test_smooth_reduces_layer_texture_only_inside_piece() -> None:
    image, alpha = _scene()
    smoothed = smooth_layer_lines(image, alpha, 80)
    center = (slice(380, 420), slice(280, 320))
    # Desviación de cada canal por separado (la textura), no entre canales (el color).
    assert smoothed[center].std(axis=(0, 1)).max() < image[center].std(axis=(0, 1)).max() * 0.6
    np.testing.assert_allclose(smoothed[:20, :20], image[:20, :20])


def test_export_respects_max_bytes_and_overrides() -> None:
    settings = AppSettings()
    settings.export.presets["instagram_feed"] = PresetOverride(width=1080, height=1080, quality=80)
    assert resolve_preset("instagram_feed", settings.export).height == 1080
    assert resolve_preset("storefront", settings.export).width == 2000

    noise = np.random.default_rng(0).random((800, 800, 3), dtype=np.float32)
    detailed = cv2.GaussianBlur(noise, (0, 0), 1.2)
    spec = resolve_preset("storefront", None)
    full = len(encode(detailed, spec))
    limited = len(encode(detailed, replace(spec, max_bytes=int(full * 0.6))))
    assert limited <= full * 0.6
    assert slugify("Dragón Articulado #2") == "dragon-articulado-2"


def test_quality_flags_border_and_low_resolution() -> None:
    alpha = np.zeros((100, 100), np.float32)
    alpha[20:100, 30:70] = 1.0
    reasons = review_reasons(alpha, 2, AppSettings().quality, needed_upscale=3.0)
    assert {"touches_border", "multiple_objects", "low_resolution"} <= set(reasons)


def test_real_pipeline_end_to_end_without_gpu(tmp_path: Path, real_mode: None) -> None:
    image, alpha = _scene()
    source, mask = tmp_path / "pieza.png", tmp_path / "mask.png"
    Image.fromarray((image * 255).astype(np.uint8)).save(source)
    Image.fromarray((alpha * 255).astype(np.uint8)).save(mask)
    settings = AppSettings()
    settings.pipeline.upscale_model = "lanczos"

    result = process_image(
        source,
        ProcessOptions(presets=["storefront", "instagram_feed"], generate_both_layer_variants=True),
        tmp_path / "out",
        base_name="DRG-01",
        mask_override=mask,
        settings=settings,
    )

    names = sorted(Path(output.path).name for output in result.outputs)
    assert names == [
        "DRG-01.webp",
        "DRG-01_instagram_feed.jpg",
        "DRG-01_instagram_feed_smooth.jpg",
        "DRG-01_smooth.webp",
    ]
    storefront = next(o for o in result.outputs if o.preset == "storefront" and o.variant == "keep")
    with Image.open(storefront.path) as rendered:
        pixels = np.asarray(rendered.convert("RGB"))
    assert pixels.shape == (2000, 2000, 3)
    assert (pixels[:50, :50] == 255).all()
    assert storefront.bytes < 5 * 1024 * 1024
    assert "low_resolution" in result.review_reasons  # pieza de 600 px para un lienzo de 2000
    assert {"segment", "color", "upscale", "total"} <= set(result.timings_ms)
