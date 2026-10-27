"""Líneas de capa: `keep` no toca nada; `smooth` atenúa la textura fina solo dentro de la pieza,
con un filtro guiado que respeta los bordes fuertes (pintura, cambios de color, siluetas)."""

import cv2
import numpy as np

from app.pipeline.segment import guided_filter
from app.pipeline.types import Alpha, FloatImage


def smooth_layer_lines(image: FloatImage, alpha: Alpha, strength: int) -> FloatImage:
    if strength <= 0:
        return image
    amount = min(strength, 100) / 100.0
    long_side = max(image.shape[:2])
    radius = max(2, round(long_side * 0.004))
    # Más intensidad = eps mayor = se alisan variaciones de luminancia más grandes.
    eps = (0.015 + 0.12 * amount) ** 2

    smoothed = np.empty_like(image)
    for channel in range(3):
        plane = np.ascontiguousarray(image[..., channel])
        smoothed[..., channel] = guided_filter(plane, plane, radius, eps)

    # Peso: solo dentro de la pieza y lejos de la silueta, para no ablandar el contorno.
    inner = cv2.erode((alpha > 0.5).astype(np.uint8), np.ones((radius * 2 + 1,) * 2, np.uint8))
    weight = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), radius) * amount
    blended = image * (1.0 - weight[..., None]) + smoothed * weight[..., None]
    return np.clip(blended, 0.0, 1.0).astype(np.float32)
