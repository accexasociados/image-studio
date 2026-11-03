"""Acabado estudio (F12.16): curva de tonos, claridad y color selectivo sin IA generativa."""

import cv2
import numpy as np

from app.contracts import AutoAdjustments
from app.pipeline.auto import decide
from app.pipeline.finish import _monotone_lut, studio_finish
from app.pipeline.types import luminance


def _piece(spread: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Pieza azul pintada con pincel seco claro y detalles dorados, rodeada de fondo blanco."""
    rng = np.random.default_rng(7)
    base = cv2.GaussianBlur(rng.uniform(0.0, 1.0, (400, 400)).astype(np.float32), (0, 0), 3.0)
    base = (base - base.mean()) / base.std() * 0.08 * spread + 0.33
    image = np.stack([base * 0.75, base * 0.95, base * 1.35], axis=-1)
    image[150:180, 100:300] = (0.47, 0.41, 0.34)  # dorado envejecido (croma 0,13, como el Arthas)
    image[230:236, 120:280] = (0.62, 0.68, 0.78)  # pincel seco
    alpha = np.zeros((400, 400), np.float32)
    alpha[40:360, 40:360] = 1
    image[alpha == 0] = 1.0
    return np.clip(image, 0, 1).astype(np.float32), alpha


def _gold_chroma(image: np.ndarray) -> float:
    gold = image[155:175, 110:290]
    return float((gold.max(-1) - gold.min(-1)).mean())


def test_zero_strength_changes_nothing() -> None:
    image, alpha = _piece()
    assert np.array_equal(studio_finish(image, alpha, 0.0), image)


def test_midtones_go_down_and_drybrush_highlights_go_up() -> None:
    image, alpha = _piece()
    result = studio_finish(image, alpha, 1.0)
    piece = alpha > 0.5
    before, after = luminance(image), luminance(result)
    assert np.median(after[piece]) < np.median(before[piece]) - 0.02
    assert after[230:236, 130:270].mean() > before[230:236, 130:270].mean() + 0.03


def test_with_strong_glare_the_highlights_grow_much_less() -> None:
    image, alpha = _piece()
    stripe = (slice(230, 236), slice(130, 270))
    grown = luminance(studio_finish(image, alpha, 1.0))[stripe].mean()
    held = luminance(studio_finish(image, alpha, 1.0, highlights=0.0))[stripe].mean()
    assert held < grown - 0.05


def test_gold_gets_warmer_but_a_saturated_orange_does_not() -> None:
    image, alpha = _piece()
    assert _gold_chroma(studio_finish(image, alpha, 1.0)) > _gold_chroma(image) * 1.15
    orange = image.copy()
    orange[150:180, 100:300] = (0.95, 0.35, 0.05)
    assert _gold_chroma(studio_finish(orange, alpha, 1.0)) < _gold_chroma(orange) * 1.05


def test_background_and_edges_are_untouched() -> None:
    image, alpha = _piece()
    result = studio_finish(image, alpha, 1.0)
    assert np.array_equal(result[alpha == 0], image[alpha == 0])


def test_curve_never_goes_down() -> None:
    lut = _monotone_lut([0.0, 0.08, 0.35, 0.55, 0.62, 1.0], [0.0, 0.08, 0.28, 0.55, 0.86, 1.0])
    assert np.all(np.diff(lut) >= -1e-6)
    assert lut[0] == 0.0 and abs(float(lut[-1]) - 1.0) < 1e-6


def test_a_flat_photo_gets_more_finish_than_a_contrasted_one() -> None:
    flat = decide(*_piece(spread=0.6), exposure_gain=1.0)
    contrasted = decide(*_piece(spread=3.5), exposure_gain=1.0)
    assert flat is not None and contrasted is not None
    assert flat.finish > contrasted.finish + 20


def test_old_saved_adjustments_without_finish_still_load() -> None:
    saved = {"sharpen": 50, "enhance": 60, "glare": 0, "light": 5}
    assert AutoAdjustments.model_validate(saved).finish == 0
