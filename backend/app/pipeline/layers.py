"""Líneas de capa: `keep` no toca nada; `smooth` atenúa la textura fina y suave de la luminancia (las
líneas de la impresión) y deja los bordes fuertes (contornos pintados, cambios de color, siluetas).

Un filtro que alisa todo por igual dejaba la pieza con aspecto de plástico; aquí solo se recorta el detalle
de amplitud pequeña ("coring") y se deja una parte para que la superficie conserve algo de textura."""

import cv2
import numpy as np

from app.pipeline.types import Alpha, FloatImage, luminance

# Escala de la textura que se atenúa (fracción del lado mayor): cubre el paso de las líneas de capa.
_DETAIL_SIGMA = 0.0035
# Detalle menor que esto (luminancia) cuenta como línea de capa; un contorno pintado es mucho mayor.
_CORING_THRESHOLD = 0.1
# Fracción de la textura que queda aun con fuerza 100, para que no parezca plástico.
_RESIDUAL = 0.2


def smooth_layer_lines(image: FloatImage, alpha: Alpha, strength: int) -> FloatImage:
    if strength <= 0:
        return image
    amount = min(strength, 100) / 100.0
    lum = luminance(image)
    sigma = max(max(image.shape[:2]) * _DETAIL_SIGMA, 1.2)
    base = cv2.GaussianBlur(lum, (0, 0), sigma)
    detail = lum - base
    keep = np.clip(np.abs(detail) / _CORING_THRESHOLD, 0.0, 1.0) ** 2
    factor = _RESIDUAL + (1.0 - _RESIDUAL) * keep
    new_lum = base + detail * (1.0 - amount + amount * factor)
    # Solo dentro de la pieza y sin llegar a la silueta, para no ablandar el contorno.
    inner = cv2.erode((alpha > 0.5).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32)
    weight = cv2.GaussianBlur(inner, (0, 0), 2.0)
    # Se cambia la luminancia y se conserva el color: el mismo ajuste en los tres canales.
    smoothed: FloatImage = np.clip(image + ((new_lum - lum) * weight)[..., None], 0.0, 1.0).astype(np.float32)
    return smoothed
