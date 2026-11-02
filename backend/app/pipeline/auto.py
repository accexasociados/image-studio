"""Ajuste automático según la foto: mide la pieza y decide cuánta nitidez, realce y reducción de brillos
necesita, en vez de aplicar la misma fuerza a todas las fotos.

Se mide sobre el recorte de la pieza ya corregido de color y llevado a 1000 px por el lado mayor, así una
foto de 12 MP y una de 3 MP dan la misma medida. Calibrado el 2026-11-02 con 9 fotos reales:

- nitidez (detalle fino / detalle medio): Arthas 0,18 a 0,22 (foto suave), Snoopy 0,45, Gengar 0,42 a 0,71.
- rango de tonos (percentil 1 a 99,5 de la luminancia): Arthas 0,48 a 0,57, Gengar 0,75 a 0,85, Snoopy 0,93.
- brillos (exceso de luz sobre su superficie, `color.soften_glare`): Arthas 0,5 a 4, Snoopy 7,
  Gengar 9 a 17.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from app.contracts import AutoAdjustments
from app.pipeline.color import _GLARE_CHROMA_RAMP, _GLARE_MIN_CHROMA, _glare_gate
from app.pipeline.types import Alpha, FloatImage, luminance

_SIZE = 1000


@dataclass(frozen=True)
class AutoParams:
    # Nitidez medida -> fuerza del enfoque final (0-100): una foto suave pide más, una nítida casi nada.
    soft: float = 0.2
    crisp: float = 0.6
    sharpen_soft: int = 90
    sharpen_crisp: int = 35
    # Rango de tonos -> realce: una foto plana (sin negros ni blancos) pide más contraste.
    flat: float = 0.55
    full: float = 1.0
    enhance_flat: int = 85
    enhance_full: int = 55
    # Brillos medidos -> reducción: sin reflejos no se toca la pieza (respeta el pincel seco).
    glare_none: float = 1.0
    glare_strong: float = 13.0
    glare_max: int = 85


@dataclass(frozen=True)
class Measures:
    sharpness: float
    tonal_range: float
    glare: float


def measure(image: FloatImage, alpha: Alpha) -> Measures | None:
    ys, xs = np.nonzero(alpha > 0.5)
    if ys.size < 500:
        return None
    crop = image[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    crop_alpha = alpha[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    scale = _SIZE / max(crop.shape[:2])
    size = (max(round(crop.shape[1] * scale), 1), max(round(crop.shape[0] * scale), 1))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized: FloatImage = np.clip(cv2.resize(crop, size, interpolation=interpolation), 0.0, 1.0).astype(
        np.float32
    )
    crop = resized
    small_alpha = cv2.resize(crop_alpha, size, interpolation=cv2.INTER_AREA)
    # Lejos del contorno: el borde contra el fondo no es detalle de la pieza.
    inner = cv2.erode((small_alpha > 0.5).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    if inner.sum() < 500:
        return None

    lum = luminance(crop)
    low, high = np.percentile(lum[inner], [1.0, 99.5])
    blur1 = cv2.GaussianBlur(lum, (0, 0), 1.0)
    fine = float(np.abs(lum - blur1)[inner].mean())
    mid = float(np.abs(blur1 - cv2.GaussianBlur(lum, (0, 0), 4.0))[inner].mean())

    chroma = crop.max(axis=-1) - crop.min(axis=-1)
    colored = np.clip((chroma - _GLARE_MIN_CHROMA) / _GLARE_CHROMA_RAMP, 0.0, 1.0) * inner
    sigma = _SIZE * 0.03
    surface = cv2.GaussianBlur(lum * colored, (0, 0), sigma) / np.maximum(
        cv2.GaussianBlur(colored, (0, 0), sigma), 1e-3
    )
    excess = np.clip(lum - surface, 0.0, None) * colored * _glare_gate(crop, _SIZE)
    return Measures(
        sharpness=fine / max(mid, 1e-4),
        tonal_range=float(high - low),
        glare=float(excess[inner].mean() * 1000),
    )


def _ramp(value: float, start: float, end: float, at_start: float, at_end: float) -> int:
    t = float(np.clip((value - start) / (end - start), 0.0, 1.0))
    return round(at_start + (at_end - at_start) * t)


def decide(
    image: FloatImage, alpha: Alpha, exposure_gain: float, params: AutoParams | None = None
) -> AutoAdjustments | None:
    """Fuerzas (0-100) para esta foto; None si la pieza es muy pequeña para medirla."""
    params = params or AutoParams()
    measures = measure(image, alpha)
    if measures is None:
        return None
    p = params
    return AutoAdjustments(
        sharpen=_ramp(measures.sharpness, p.soft, p.crisp, p.sharpen_soft, p.sharpen_crisp),
        enhance=_ramp(measures.tonal_range, p.flat, p.full, p.enhance_flat, p.enhance_full),
        glare=_ramp(measures.glare, params.glare_none, params.glare_strong, 0, params.glare_max),
        light=round((exposure_gain - 1.0) * 100),
    )
