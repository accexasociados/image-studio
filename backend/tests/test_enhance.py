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


def test_sharpen_zero_is_identity_and_flat_areas_stay_flat() -> None:
    from app.pipeline.color import sharpen

    flat = np.full((60, 60, 3), 0.95, np.float32)
    assert np.array_equal(sharpen(flat, 0.0), flat)
    assert np.allclose(sharpen(flat, 1.0), flat, atol=1e-5)


def test_sharpen_increases_edge_contrast() -> None:
    import cv2

    from app.pipeline.color import sharpen

    image = np.full((60, 60, 3), 0.9, np.float32)
    image[:, 30:] = 0.1
    image = cv2.GaussianBlur(image, (0, 0), 1.5)
    result = sharpen(image, 0.6)
    assert np.abs(np.diff(result[30, :, 0])).max() > np.abs(np.diff(image[30, :, 0])).max()


def test_enhance_does_not_brighten_existing_glints() -> None:
    from app.pipeline.color import EnhanceParams, enhance

    image = np.full((600, 600, 3), (0.35, 0.2, 0.6), np.float32)  # plástico morado
    image[:, :60] = 0.04  # base negra
    image[:, 540:] = 0.85  # parte blanca
    image[298:303, 298:303] = (0.7, 0.6, 0.9)  # reflejo de la luz
    alpha = np.ones((600, 600), np.float32)

    def glint(result: np.ndarray) -> float:
        lum = result @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        return float(lum[300, 300] - lum[200, 200])

    kept = enhance(image, alpha, 1.0)
    unchecked = enhance(image, alpha, 1.0, EnhanceParams(glint_threshold=1e9))
    # Sin el límite el realce sube el reflejo; con él queda como en la foto (un poco de margen por la curva).
    assert glint(unchecked) > glint(image) * 1.15
    assert glint(kept) < glint(image) * 1.08


def test_exposure_does_not_brighten_a_piece_without_white_when_the_photo_is_well_lit() -> None:
    from app.pipeline.color import correct_color

    image = np.full((300, 300, 3), 0.86, np.float32)  # cartulina bien iluminada
    alpha = np.zeros((300, 300), np.float32)
    alpha[80:220, 80:220] = 1.0
    image[80:220, 80:220] = (0.3, 0.18, 0.5)  # pieza morada, sin blanco
    result = correct_color(image, alpha, white_balance=False)
    # Antes la parte más clara de la pieza se llevaba a 0,94 (ganancia 1,35); ahora manda el fondo.
    assert result.exposure_gain < 1.1
