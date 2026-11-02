"""Realce tipo foto de estudio (Fase 12)."""

import numpy as np

from app.pipeline.color import enhance


def _piece() -> tuple[np.ndarray, np.ndarray]:
    """Mitad blanca en sombra (0,75), un naranja apagado, un negro con tinte cian y un blanco puro."""
    image = np.zeros((40, 40, 3), np.float32)
    image[:10] = 0.75
    image[10:20] = (0.7, 0.3, 0.15)
    image[20:30] = (0.06, 0.08, 0.09)
    image[30:] = 0.99
    image[30:, :2] = 0.01
    return image, np.ones((40, 40), np.float32)


def test_strength_zero_leaves_colors_untouched() -> None:
    image, alpha = _piece()
    assert np.array_equal(enhance(image, alpha, 0.0), image)


def test_enhance_brightens_midtones_and_saturates_colors() -> None:
    image, alpha = _piece()
    result = enhance(image, alpha, 1.0)
    assert result[5, 20].mean() > image[5, 20].mean() + 0.03  # blanco en sombra más limpio
    orange_before = image[15, 20].max() - image[15, 20].min()
    orange_after = result[15, 20].max() - result[15, 20].min()
    assert orange_after > orange_before
    assert result[35, 20].mean() <= 1.0


def test_enhance_does_not_tint_dark_neutrals() -> None:
    image, alpha = _piece()
    result = enhance(image, alpha, 1.0)
    # La curva aclara el negro en proporción; lo que no debe crecer es el tinte relativo a su brillo.
    tint_before = (image[25, 20, 2] - image[25, 20, 0]) / image[25, 20].mean()
    tint_after = (result[25, 20, 2] - result[25, 20, 0]) / result[25, 20].mean()
    assert tint_after <= tint_before + 0.01


def test_enhance_ignores_the_background() -> None:
    image, alpha = _piece()
    alpha[:] = 0.0
    assert np.array_equal(enhance(image, alpha, 1.0), image)
