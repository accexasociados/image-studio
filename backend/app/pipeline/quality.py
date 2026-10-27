"""Marca las imágenes que conviene revisar a mano. Devuelve códigos estables (la web los traduce):

- `touches_border`: la pieza toca el borde de la foto (probablemente quedó cortada).
- `object_too_small` / `object_too_large`: la pieza ocupa muy poco o casi toda la foto.
- `multiple_objects`: hay varias piezas separadas.
- `uncertain_edges`: muchos bordes con alfa intermedio (translúcido o poco contraste con el fondo).
- `low_resolution`: la pieza es demasiado chica para el formato más grande pedido sin agrandarla más de 2x.
"""

import cv2
import numpy as np

from app.contracts.settings import QualitySettings
from app.pipeline.types import Alpha

# Las métricas de borde se calculan sobre la máscara reducida a este tamaño para no depender
# de la resolución de la foto.
_NORMALIZED_SIDE = 1024
_BORDER_MARGIN_RATIO = 0.003


def normalized_uncertain_edge_ratio(alpha: Alpha) -> float:
    scale = _NORMALIZED_SIDE / max(alpha.shape)
    small = alpha if scale >= 1 else cv2.resize(alpha, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    binary = (small > 0.5).astype(np.uint8)
    edge = cv2.morphologyEx(binary, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8)).astype(bool)
    if not edge.any():
        return 0.0
    values = small[edge]
    return float(((values > 0.15) & (values < 0.85)).mean())


def review_reasons(
    alpha: Alpha, components: int, settings: QualitySettings, *, needed_upscale: float
) -> list[str]:
    reasons: list[str] = []
    piece = alpha > 0.5
    height, width = alpha.shape
    area = float(piece.mean())

    margin = max(2, round(max(height, width) * _BORDER_MARGIN_RATIO))
    if settings.flag_touching_border and (
        piece[:margin].any() or piece[-margin:].any() or piece[:, :margin].any() or piece[:, -margin:].any()
    ):
        reasons.append("touches_border")
    if area < settings.min_object_area:
        reasons.append("object_too_small")
    if area > settings.max_object_area:
        reasons.append("object_too_large")
    if settings.flag_multiple_objects and components > 1:
        reasons.append("multiple_objects")
    if normalized_uncertain_edge_ratio(alpha) > settings.low_confidence_edge_ratio:
        reasons.append("uncertain_edges")
    if needed_upscale > 2.0:
        reasons.append("low_resolution")
    return reasons
