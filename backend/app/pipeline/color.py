"""Corrección de color suave: balance de blancos tomando el fondo como referencia neutra y
exposición de la pieza. Nada de saturación ni contraste agresivos (eso delata el retoque)."""

from dataclasses import dataclass

import cv2
import numpy as np

from app.pipeline.types import Alpha, FloatImage, luminance


@dataclass(frozen=True)
class ColorParams:
    # Fracción de la corrección de blancos que se aplica (1 = neutralizar del todo el fondo).
    white_balance_strength: float = 0.85
    max_channel_gain: float = 1.25
    # Si el fondo tiene más croma que esto, no es una referencia neutra (p. ej. cajas de colores).
    max_background_chroma: float = 0.25
    # La parte más clara de la pieza (percentil) se lleva hacia este valor, con un tope de ganancia.
    exposure_percentile: float = 99.0
    exposure_target: float = 0.94
    max_exposure_gain: float = 1.35


@dataclass(frozen=True)
class ColorResult:
    image: FloatImage
    gains: tuple[float, float, float]
    exposure_gain: float
    white_balance_applied: bool


def _background_reference(image: FloatImage, alpha: Alpha) -> FloatImage | None:
    """Píxeles claros del fondo (la cartulina), lejos de la pieza."""
    background = alpha < 0.02
    if background.sum() < 500:
        return None
    lum = luminance(image)
    # La mitad más clara del fondo: la cartulina, no la mesa oscura de abajo.
    bright = lum >= np.percentile(lum[background], 50)
    candidates = image[background & bright]
    if candidates.shape[0] < 500:
        return None
    return candidates


def white_balance_gains(
    image: FloatImage, alpha: Alpha, params: ColorParams
) -> tuple[float, float, float] | None:
    reference = _background_reference(image, alpha)
    if reference is None:
        return None
    mean = np.median(reference, axis=0)
    gray = float(mean.mean())
    if gray <= 0.05:
        return None
    chroma = float((mean.max() - mean.min()) / max(gray, 1e-6))
    if chroma > params.max_background_chroma:
        return None
    raw = gray / np.maximum(mean, 1e-6)
    gains = 1.0 + (raw - 1.0) * params.white_balance_strength
    clipped = np.clip(gains, 1 / params.max_channel_gain, params.max_channel_gain)
    return float(clipped[0]), float(clipped[1]), float(clipped[2])


def _downsample(image: FloatImage, alpha: Alpha, long_side: int = 1024) -> tuple[FloatImage, Alpha]:
    scale = long_side / max(alpha.shape)
    if scale >= 1:
        return image, alpha
    size = (round(alpha.shape[1] * scale), round(alpha.shape[0] * scale))
    small_image = cv2.resize(image, size, interpolation=cv2.INTER_AREA).astype(np.float32)
    return small_image, cv2.resize(alpha, size, interpolation=cv2.INTER_AREA).astype(np.float32)


def correct_color(
    image: FloatImage,
    alpha: Alpha,
    *,
    white_balance: bool,
    params: ColorParams | None = None,
    apply_to: FloatImage | None = None,
) -> ColorResult:
    """Calcula la corrección sobre una copia reducida de la foto completa (fondo incluido) y la
    aplica a `apply_to` (p. ej. el recorte de la pieza) o, si no se da, a la foto completa."""
    params = params or ColorParams()
    small_image, small_alpha = _downsample(image, alpha)
    gains = white_balance_gains(small_image, small_alpha, params) if white_balance else None
    gain_vector = np.array(gains or (1.0, 1.0, 1.0), dtype=np.float32)

    piece = small_alpha > 0.5
    exposure_gain = 1.0
    if piece.sum() > 100:
        bright = float(np.percentile(luminance(small_image * gain_vector)[piece], params.exposure_percentile))
        if 0.05 < bright < params.exposure_target:
            exposure_gain = min(params.exposure_target / bright, params.max_exposure_gain)

    target = image if apply_to is None else apply_to
    corrected = target * (gain_vector * exposure_gain)

    return ColorResult(
        image=np.clip(corrected, 0.0, 1.0).astype(np.float32),
        gains=gains or (1.0, 1.0, 1.0),
        exposure_gain=exposure_gain,
        white_balance_applied=gains is not None,
    )
