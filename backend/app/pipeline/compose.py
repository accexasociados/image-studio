"""Composición final: limpia el halo del fondo en los bordes, encuadra la pieza en el lienzo blanco
y aplica la sombra. Fuera de la sombra el fondo queda exactamente blanco."""

from dataclasses import dataclass

import cv2
import numpy as np

from app.pipeline.shadow import ResolvedShadow, ShadowParams, shadow_map
from app.pipeline.types import Alpha, FloatImage


@dataclass(frozen=True)
class Crop:
    image: FloatImage
    alpha: Alpha


def decontaminate_edges(image: FloatImage, alpha: Alpha) -> FloatImage:
    """Quita el color del fondo original que queda mezclado en los píxeles del borde.

    Estima el fondo local por convolución normalizada y despeja el color de la pieza:
    F = (I - (1 - a) * B) / a, solo donde el alfa es parcial."""
    background_weight = (alpha < 0.05).astype(np.float32)
    sigma = max(image.shape[:2]) * 0.01
    numerator = cv2.GaussianBlur(image * background_weight[..., None], (0, 0), sigma)
    denominator = cv2.GaussianBlur(background_weight, (0, 0), sigma)[..., None]
    background = numerator / np.maximum(denominator, 1e-4)

    a = alpha[..., None]
    foreground = (image - (1.0 - a) * background) / np.maximum(a, 0.1)
    partial = ((alpha > 0.02) & (alpha < 0.98))[..., None]
    return np.where(partial, np.clip(foreground, 0.0, 1.0), image).astype(np.float32)


def crop_to_piece(image: FloatImage, alpha: Alpha, padding_ratio: float = 0.02) -> Crop:
    rows = np.flatnonzero((alpha > 0.02).any(axis=1))
    columns = np.flatnonzero((alpha > 0.02).any(axis=0))
    if rows.size == 0 or columns.size == 0:
        return Crop(image, alpha)
    pad = round(max(image.shape[:2]) * padding_ratio)
    top, bottom = max(int(rows[0]) - pad, 0), min(int(rows[-1]) + pad + 1, image.shape[0])
    left, right = max(int(columns[0]) - pad, 0), min(int(columns[-1]) + pad + 1, image.shape[1])
    return Crop(image[top:bottom, left:right].copy(), alpha[top:bottom, left:right].copy())


def piece_bounds(alpha: Alpha) -> tuple[int, int, int, int]:
    rows = np.flatnonzero((alpha > 0.5).any(axis=1))
    columns = np.flatnonzero((alpha > 0.5).any(axis=0))
    return int(rows[0]), int(rows[-1]) + 1, int(columns[0]), int(columns[-1]) + 1


def compose_on_canvas(
    crop: Crop,
    canvas_size: tuple[int, int],
    fill_ratio: float,
    shadow: ResolvedShadow,
    background: tuple[int, int, int] = (255, 255, 255),
    shadow_params: ShadowParams | None = None,
) -> FloatImage:
    """Ubica la pieza en un lienzo (ancho, alto): el lado que manda ocupa `fill_ratio` del lienzo."""
    width, height = canvas_size
    top, bottom, left, right = piece_bounds(crop.alpha)
    piece_w, piece_h = right - left, bottom - top
    scale = fill_ratio * min(width / piece_w, height / piece_h)

    resized_w = max(round(crop.image.shape[1] * scale), 1)
    resized_h = max(round(crop.image.shape[0] * scale), 1)
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4
    image = np.clip(cv2.resize(crop.image, (resized_w, resized_h), interpolation=interpolation), 0, 1)
    alpha = np.clip(cv2.resize(crop.alpha, (resized_w, resized_h), interpolation=interpolation), 0, 1)

    # Centro horizontal: mitad caja, mitad centro de masa (las piezas asimétricas se ven centradas).
    # Vertical: centrado con la base un poco más alta que el centro para dejar sitio a la sombra.
    columns_mass = alpha.sum(axis=0)
    mass_x = float((columns_mass * np.arange(resized_w)).sum() / max(columns_mass.sum(), 1e-6))
    box_x = (left + right) / 2.0 * scale
    anchor_x = 0.5 * box_x + 0.5 * mass_x
    anchor_y = (top + bottom) / 2.0 * scale
    offset_x = round(width / 2.0 - anchor_x)
    offset_y = round(height * 0.48 - anchor_y)

    placed_image = np.zeros((height, width, 3), np.float32)
    placed_alpha = np.zeros((height, width), np.float32)
    src_y0, src_x0 = max(-offset_y, 0), max(-offset_x, 0)
    dst_y0, dst_x0 = max(offset_y, 0), max(offset_x, 0)
    h = min(resized_h - src_y0, height - dst_y0)
    w = min(resized_w - src_x0, width - dst_x0)
    placed_image[dst_y0 : dst_y0 + h, dst_x0 : dst_x0 + w] = image[src_y0 : src_y0 + h, src_x0 : src_x0 + w]
    placed_alpha[dst_y0 : dst_y0 + h, dst_x0 : dst_x0 + w] = alpha[src_y0 : src_y0 + h, src_x0 : src_x0 + w]

    canvas = np.empty((height, width, 3), np.float32)
    canvas[:] = np.array(background, np.float32) / 255.0
    darkness = shadow_map(placed_alpha, shadow, shadow_params or ShadowParams())
    canvas *= 1.0 - darkness[..., None]
    a = placed_alpha[..., None]
    result = placed_image * a + canvas * (1.0 - a)
    # Fondo exacto: donde no hay pieza ni sombra, el color de fondo sin residuos de interpolación.
    untouched = (placed_alpha < 1.0 / 255.0) & (darkness == 0.0)
    result[untouched] = np.array(background, np.float32) / 255.0
    return np.clip(result, 0.0, 1.0).astype(np.float32)
