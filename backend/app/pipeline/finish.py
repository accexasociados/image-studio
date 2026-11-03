"""Acabado "estudio": el retoque que separa una foto de celular de una foto de catálogo, sin IA generativa.

Se aplica sobre la pieza ya realzada (después de `color.enhance`) y nunca cambia su forma ni su pintura:
solo reparte la luz y el color. Calibrado el 2026-11-02 contra la versión que ChatGPT hizo del Arthas
(medido sobre la pieza a 1000 px): medios tonos 0,29 (el estudio daba 0,38), luces 0,87 (0,68), detalle
medio 55 (32) y dorado con croma 0,13 (0,10).

1. Curva de tonos por puntos: sombras y luces medias quedan, los medios tonos bajan (una pieza azul
   marino no queda azul claro) y solo las luces del pincel seco suben.
2. Claridad: contraste local de radio pequeño medido solo con la pieza, así el borde contra el fondo
   no deja halos. Marca el relieve pintado, pero también las líneas de capa: por eso en una foto de
   colores lisos el ajuste automático lo usa poco (`auto.decide`).
3. Color selectivo: los metales y tonos cálidos apagados ganan croma; un naranja ya vivo no se toca.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from app.pipeline.types import Alpha, FloatImage, luminance


@dataclass(frozen=True)
class FinishParams:
    # Curva de tonos por puntos sobre los percentiles de la pieza: las sombras (p10) y las luces medias
    # (p90) quedan; la mediana baja `midtone_drop`; el p99,5 sube hacia `white_target` sin multiplicarse
    # más de `max_white_gain` (son las luces del pincel seco, lo que hace "saltar" el relieve).
    shadow_percentile: float = 10.0
    highlight_percentile: float = 90.0
    white_percentile: float = 99.5
    midtone_drop: float = 0.2
    white_target: float = 0.86
    # Las sombras no bajan de aquí: el negro de la pieza conserva detalle (no se empasta).
    shadow_floor: float = 0.065
    max_white_gain: float = 1.3
    # Claridad: banda de detalle entre estos radios (fracciones del lado mayor) y su peso.
    clarity_fine: float = 0.0012
    clarity_coarse: float = 0.008
    clarity: float = 0.9
    # Color selectivo: aumento de croma en tonos cálidos (rojo > azul) y en fríos; se apaga a medida que
    # el croma se acerca a `saturated` (la calabaza del Snoopy ya es naranja puro).
    warm_boost: float = 0.35
    cool_boost: float = 0.1
    saturated: float = 0.4


def _monotone_lut(xs: list[float], ys: list[float], size: int = 1024) -> np.ndarray:
    """Curva suave que pasa por los puntos y nunca baja (Fritsch-Carlson): sin bandas ni inversiones."""
    x, y = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
    h, delta = np.diff(x), np.diff(y) / np.diff(x)
    m = np.empty_like(x)
    m[0], m[-1] = delta[0], delta[-1]
    m[1:-1] = np.where(delta[:-1] * delta[1:] > 0, (delta[:-1] + delta[1:]) / 2, 0.0)
    for i, d in enumerate(delta):
        if d == 0:
            m[i] = m[i + 1] = 0.0
            continue
        a, b = m[i] / d, m[i + 1] / d
        r = a * a + b * b
        if r > 9:
            t = 3 / np.sqrt(r)
            m[i], m[i + 1] = t * a * d, t * b * d
    grid = np.linspace(0.0, 1.0, size)
    k = np.clip(np.searchsorted(x, grid, side="right") - 1, 0, len(h) - 1)
    t = (grid - x[k]) / h[k]
    t2, t3 = t * t, t * t * t
    lut = (
        (2 * t3 - 3 * t2 + 1) * y[k]
        + (t3 - 2 * t2 + t) * h[k] * m[k]
        + (-2 * t3 + 3 * t2) * y[k + 1]
        + (t3 - t2) * h[k] * m[k + 1]
    )
    return np.clip(lut, 0.0, 1.0).astype(np.float32)


def studio_finish(
    image: FloatImage,
    alpha: Alpha,
    strength: float,
    highlights: float = 1.0,
    params: FinishParams | None = None,
) -> FloatImage:
    """Curva de tonos, claridad y color selectivo dentro de la pieza (`alpha > 0.5`); 0 = sin cambio.

    `highlights` (0 a 1) es cuánto suben las luces: con brillos fuertes en la foto conviene poco, porque
    lo que crecería es el reflejo y no el pincel seco."""
    params = params or FinishParams()
    piece = alpha > 0.5
    if strength <= 0 or piece.sum() < 100:
        return image
    lum = luminance(image)
    p10, p50, p90, top = (
        float(v)
        for v in np.percentile(
            lum[piece], [params.shadow_percentile, 50.0, params.highlight_percentile, params.white_percentile]
        )
    )

    # 1. Curva de tonos sobre la luminancia; el color sigue a la luz (mismo tono). Con fuerza < 1 cada
    # punto se acerca a la identidad.
    top_target = min(max(params.white_target, top), top * params.max_white_gain, 0.98)
    top_target = top + (top_target - top) * float(np.clip(highlights, 0.0, 1.0))
    shadow_target = max(p10, min(params.shadow_floor, p50 * 0.5))
    xs = [0.0, p10, p50, p90, top, 1.0]
    ys = [0.0, shadow_target, p50 * (1.0 - params.midtone_drop), p90, top_target, 1.0]
    ys = [x + (y - x) * strength for x, y in zip(xs, ys, strict=True)]
    keep = [0] + [i for i in range(1, len(xs)) if xs[i] - xs[i - 1] > 0.01]
    xs, ys = [xs[i] for i in keep], [ys[i] for i in keep]
    if xs[-1] < 1.0:
        xs[-1], ys[-1] = 1.0, 1.0
    lut = _monotone_lut(xs, ys)
    curved = lut[np.clip(np.rint(lum * (len(lut) - 1)), 0, len(lut) - 1).astype(np.int32)]

    # 2. Claridad: blur ponderado por la pieza para que el fondo no entre en el promedio del borde.
    size = max(image.shape[:2])
    weight = np.clip(alpha, 0.0, 1.0).astype(np.float32)

    def _masked_blur(values: np.ndarray, sigma: float) -> np.ndarray:
        num = cv2.GaussianBlur(values * weight, (0, 0), sigma)
        den = cv2.GaussianBlur(weight, (0, 0), sigma)
        blurred: np.ndarray = num / np.maximum(den, 1e-3)
        return blurred

    fine = _masked_blur(curved, max(size * params.clarity_fine, 1.0))
    coarse = _masked_blur(curved, max(size * params.clarity_coarse, 1.0))
    # Menos en los negros y en las luces: ahí la claridad solo empasta o quema.
    midtones = 4.0 * curved * (1.0 - curved)
    curved = np.clip(curved + (fine - coarse) * params.clarity * strength * midtones, 0.0, 1.0)

    ratio = curved / np.maximum(lum, 1e-3)
    result = image * np.minimum(ratio, 4.0)[..., None]
    # Lo que se pasa de 1 en un canal se reparte para no cambiar el tono (el dorado no se vuelve amarillo).
    over = result.max(axis=-1, keepdims=True)
    result = np.where(over > 1.0, result / np.maximum(over, 1e-6), result)

    # 3. Color selectivo: cálido = rojo sobre azul (dorado, cobre, piel); frío = azul sobre rojo.
    new_lum = luminance(result)[..., None]
    warmth = result[..., 0:1] - result[..., 2:3]
    warm = np.clip((warmth - 0.02) / 0.08, 0.0, 1.0)
    cool = np.clip((-warmth - 0.02) / 0.08, 0.0, 1.0)
    chroma = result.max(axis=-1, keepdims=True) - result.min(axis=-1, keepdims=True)
    muted = np.clip(1.0 - chroma / params.saturated, 0.0, 1.0)
    boost = 1.0 + (params.warm_boost * warm + params.cool_boost * cool) * muted * strength
    result = new_lum + (result - new_lum) * boost

    a = alpha[..., None]
    finished: FloatImage = np.clip(image * (1.0 - a) + np.clip(result, 0.0, 1.0) * a, 0.0, 1.0).astype(
        np.float32
    )
    return finished
