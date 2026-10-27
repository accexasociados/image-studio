"""Sombra de contacto: una elipse difusa bajo la base, deducida de la parte inferior de la máscara,
más una sombra ambiental muy tenue. Es lo que evita el efecto "pieza flotando" típico de la IA."""

from dataclasses import dataclass, field
from typing import Literal

import cv2
import numpy as np

from app.contracts import ShadowMode
from app.pipeline.types import Alpha, FloatImage, luminance

ResolvedShadow = Literal["none", "soft", "strong"]


@dataclass(frozen=True)
class ShadowParams:
    contact_opacity: dict[ResolvedShadow, float] = field(
        default_factory=lambda: {"none": 0.0, "soft": 0.32, "strong": 0.5}
    )
    ambient_opacity: dict[ResolvedShadow, float] = field(
        default_factory=lambda: {"none": 0.0, "soft": 0.08, "strong": 0.13}
    )
    # Piezas con luminancia media superior a esto se consideran claras (modo auto -> strong).
    light_piece_luminance: float = 0.62


def resolve_shadow(mode: ShadowMode, image: FloatImage, alpha: Alpha, params: ShadowParams) -> ResolvedShadow:
    if mode != "auto":
        return mode
    piece = alpha > 0.5
    if not piece.any():
        return "soft"
    return "strong" if float(luminance(image)[piece].mean()) > params.light_piece_luminance else "soft"


def shadow_map(alpha: Alpha, mode: ResolvedShadow, params: ShadowParams) -> Alpha:
    """Opacidad de sombra (0 = nada, 1 = negro) del mismo tamaño que `alpha` ya ubicado en el lienzo."""
    height, width = alpha.shape
    result = np.zeros((height, width), np.float32)
    if mode == "none":
        return result
    rows = np.flatnonzero((alpha > 0.5).any(axis=1))
    if rows.size == 0:
        return result
    top, bottom = int(rows[0]), int(rows[-1])
    object_height = bottom - top + 1

    # Huella: columnas ocupadas en el 4 % inferior de la pieza (la base o las patas).
    band = alpha[max(bottom - max(int(object_height * 0.04), 2), top) : bottom + 1] > 0.5
    columns = np.flatnonzero(band.any(axis=0))
    left, right = int(columns[0]), int(columns[-1])
    footprint = right - left + 1
    center = ((left + right) / 2.0, float(bottom))

    contact = np.zeros_like(result)
    axes = (max(int(footprint * 0.55), 2), max(int(footprint * 0.07), 2))
    cv2.ellipse(contact, (round(center[0]), round(center[1])), axes, 0, 0, 360, 1.0, -1)
    contact = cv2.GaussianBlur(contact, (0, 0), max(footprint * 0.035, 1.5)).astype(np.float32)

    ambient = np.zeros_like(result)
    ambient_axes = (max(int(footprint * 0.8), 2), max(int(footprint * 0.16), 2))
    cv2.ellipse(ambient, (round(center[0]), round(center[1])), ambient_axes, 0, 0, 360, 1.0, -1)
    ambient = cv2.GaussianBlur(ambient, (0, 0), max(footprint * 0.12, 3.0)).astype(np.float32)

    combined = contact * params.contact_opacity[mode] + ambient * params.ambient_opacity[mode]
    # Debajo de la pieza la sombra no se ve; fuera, por debajo de 1/255 se descarta (fondo blanco puro).
    combined[combined < 1.0 / 255.0] = 0.0
    return np.clip(combined, 0.0, 1.0).astype(np.float32)
