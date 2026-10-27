"""Escenas (Fase 11): la pieza apoyada en un piso de estudio, sobre un pedestal o sobre una foto de fondo.

Todo se dibuja con código (sin IA generativa), así que la pieza nunca cambia. Lo que evita el efecto
"flotando" es la oclusión de contacto: una sombra fina y oscura pegada a la base, más una penumbra amplia.
El estilo "white" no pasa por aquí: lo compone `compose_on_canvas`."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.pipeline.compose import Crop, piece_bounds
from app.pipeline.types import Alpha, FloatImage

SceneKind = Literal["studio", "pedestal", "color", "photo"]

# Altura de la base de la pieza en el lienzo y margen libre arriba (fracciones del alto).
_FLOOR_Y = 0.80
_PEDESTAL_TOP_Y = 0.70
_TOP_MARGIN = 0.07


@dataclass(frozen=True)
class BackgroundPhoto:
    path: Path
    floor_y: float
    center_x: float
    piece_height: float


@dataclass(frozen=True)
class SceneSpec:
    kind: SceneKind
    wall: tuple[int, int, int] = (255, 255, 255)
    floor: tuple[int, int, int] = (236, 234, 230)
    pedestal: tuple[int, int, int] = (228, 223, 214)
    # Opacidad del reflejo en el piso (0 a 1); solo estudio y color.
    reflection: float = 0.14
    background: BackgroundPhoto | None = None


@dataclass(frozen=True)
class _Placed:
    image: FloatImage
    alpha: Alpha
    top: int
    bottom: int
    foot_left: int
    foot_right: int


def brand_colors(hex_rgb: tuple[int, int, int]) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Pared y piso a partir de un solo color de marca: pared más clara, piso el color tal cual."""
    color = np.array(hex_rgb, np.float32)
    wall = color + (255.0 - color) * 0.45
    return (
        (round(float(wall[0])), round(float(wall[1])), round(float(wall[2]))),
        hex_rgb,
    )


def render_scene(
    crop: Crop, canvas_size: tuple[int, int], fill_ratio: float, spec: SceneSpec, shadow_strength: float
) -> FloatImage:
    """Compone la pieza en la escena. `shadow_strength` 0 = sin sombra, 1 = normal."""
    if spec.kind == "photo":
        if spec.background is None:
            raise ValueError("La escena 'photo' necesita una foto de fondo.")
        return _photo(crop, canvas_size, fill_ratio, spec.background, shadow_strength)
    if spec.kind == "pedestal":
        return _pedestal(crop, canvas_size, fill_ratio, spec, shadow_strength)
    return _studio(crop, canvas_size, fill_ratio, spec, shadow_strength)


def _rgb(value: tuple[int, int, int]) -> np.ndarray:
    return np.array(value, np.float32) / 255.0


def _place(crop: Crop, canvas_size: tuple[int, int], scale: float, base: tuple[float, float]) -> _Placed:
    """Escala la pieza y la ubica con la base (fila inferior) en `base` = (x, y) del lienzo."""
    width, height = canvas_size
    _top, bottom, left, right = piece_bounds(crop.alpha)
    resized_w = max(round(crop.image.shape[1] * scale), 1)
    resized_h = max(round(crop.image.shape[0] * scale), 1)
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4
    image = np.clip(cv2.resize(crop.image, (resized_w, resized_h), interpolation=interpolation), 0, 1)
    alpha = np.clip(cv2.resize(crop.alpha, (resized_w, resized_h), interpolation=interpolation), 0, 1)

    # Igual que en el fondo blanco: mitad caja, mitad centro de masa, para piezas asimétricas.
    columns_mass = alpha.sum(axis=0)
    mass_x = float((columns_mass * np.arange(resized_w)).sum() / max(columns_mass.sum(), 1e-6))
    anchor_x = 0.5 * (left + right) / 2.0 * scale + 0.5 * mass_x
    offset_x = round(base[0] - anchor_x)
    offset_y = round(base[1] - bottom * scale)

    placed_image = np.zeros((height, width, 3), np.float32)
    placed_alpha = np.zeros((height, width), np.float32)
    src_y0, src_x0 = max(-offset_y, 0), max(-offset_x, 0)
    dst_y0, dst_x0 = max(offset_y, 0), max(offset_x, 0)
    h = min(resized_h - src_y0, height - dst_y0)
    w = min(resized_w - src_x0, width - dst_x0)
    placed_image[dst_y0 : dst_y0 + h, dst_x0 : dst_x0 + w] = image[src_y0 : src_y0 + h, src_x0 : src_x0 + w]
    placed_alpha[dst_y0 : dst_y0 + h, dst_x0 : dst_x0 + w] = alpha[src_y0 : src_y0 + h, src_x0 : src_x0 + w]

    rows = np.flatnonzero((placed_alpha > 0.5).any(axis=1))
    piece_top, piece_bottom = int(rows[0]), int(rows[-1])
    # Huella: columnas ocupadas en el 4 % inferior (la base o las patas).
    band_top = max(piece_bottom - max(int((piece_bottom - piece_top) * 0.04), 2), piece_top)
    columns = np.flatnonzero((placed_alpha[band_top : piece_bottom + 1] > 0.5).any(axis=0))
    return _Placed(placed_image, placed_alpha, piece_top, piece_bottom, int(columns[0]), int(columns[-1]))


def _scale_for(crop: Crop, canvas_size: tuple[int, int], fill_ratio: float, max_height: float) -> float:
    width, height = canvas_size
    top, bottom, left, right = piece_bounds(crop.alpha)
    piece_w, piece_h = right - left, bottom - top
    return min(fill_ratio * width / piece_w, fill_ratio * height / piece_h, max_height / piece_h)


def _contact_shadow(placed: _Placed, canvas_size: tuple[int, int], strength: float) -> Alpha:
    width, height = canvas_size
    result = np.zeros((height, width), np.float32)
    if strength <= 0:
        return result
    footprint = placed.foot_right - placed.foot_left + 1
    center = (round((placed.foot_left + placed.foot_right) / 2), placed.bottom)
    # Oclusión de contacto: fina, oscura y pegada a la base.
    core = np.zeros_like(result)
    cv2.ellipse(
        core, center, (max(int(footprint * 0.5), 2), max(int(footprint * 0.035), 2)), 0, 0, 360, 1.0, -1
    )
    core = cv2.GaussianBlur(core, (0, 0), max(footprint * 0.02, 1.5)).astype(np.float32)
    # Penumbra amplia, un poco hacia atrás (luz cenital algo frontal).
    soft = np.zeros_like(result)
    soft_center = (center[0], round(center[1] - footprint * 0.03))
    cv2.ellipse(
        soft, soft_center, (max(int(footprint * 0.75), 2), max(int(footprint * 0.13), 2)), 0, 0, 360, 1.0, -1
    )
    soft = cv2.GaussianBlur(soft, (0, 0), max(footprint * 0.09, 3.0)).astype(np.float32)
    return np.clip((core * 0.6 + soft * 0.22) * strength, 0, 1).astype(np.float32)


def _reflection(placed: _Placed, opacity: float) -> tuple[FloatImage, Alpha]:
    """La pieza volteada bajo la base, desvaneciéndose: piso satinado."""
    image, alpha = np.zeros_like(placed.image), np.zeros_like(placed.alpha)
    base = placed.bottom
    rows = min(int((placed.bottom - placed.top) * 0.22), alpha.shape[0] - base - 1, base)
    if opacity <= 0 or rows <= 0:
        return image, alpha
    image[base + 1 : base + 1 + rows] = placed.image[base - rows + 1 : base + 1][::-1]
    fade = np.linspace(opacity, 0.0, rows, dtype=np.float32)[:, None]
    alpha[base + 1 : base + 1 + rows] = placed.alpha[base - rows + 1 : base + 1][::-1] * fade
    return (
        cv2.GaussianBlur(image, (0, 0), 2).astype(np.float32),
        cv2.GaussianBlur(alpha, (0, 0), 2).astype(np.float32),
    )


def _sweep(canvas_size: tuple[int, int], wall: np.ndarray, floor: np.ndarray, horizon: float) -> FloatImage:
    """Fondo continuo de estudio: la pared se curva hacia el piso sin línea visible."""
    width, height = canvas_size
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None, None]
    t = np.clip((y - (horizon - 0.18)) / 0.36, 0, 1)
    t = t * t * (3 - 2 * t)
    background = wall * (1 - t) + floor * t
    x = np.linspace(-1, 1, width, dtype=np.float32)[None, :, None]
    vignette = 1 - 0.035 * x * x - 0.03 * (1 - y)
    # broadcast_to devuelve una vista de solo lectura: se copia porque luego se oscurece in situ.
    return np.array(np.broadcast_to(background * vignette, (height, width, 3)), np.float32)


def _over(background: np.ndarray, image: np.ndarray, alpha: np.ndarray) -> FloatImage:
    a = alpha[..., None]
    result: FloatImage = (image * a + background * (1 - a)).astype(np.float32)
    return result


def _studio(
    crop: Crop, canvas_size: tuple[int, int], fill_ratio: float, spec: SceneSpec, shadow_strength: float
) -> FloatImage:
    width, height = canvas_size
    base_y = height * _FLOOR_Y
    scale = _scale_for(crop, canvas_size, fill_ratio, base_y - height * _TOP_MARGIN)
    placed = _place(crop, canvas_size, scale, (width / 2, base_y))
    background = _sweep(canvas_size, _rgb(spec.wall), _rgb(spec.floor), horizon=_FLOOR_Y)
    background *= 1 - _contact_shadow(placed, canvas_size, shadow_strength)[..., None]
    reflection_image, reflection_alpha = _reflection(placed, spec.reflection)
    background = _over(background, reflection_image, reflection_alpha)
    return np.clip(_over(background, placed.image, placed.alpha), 0, 1)


def _pedestal(
    crop: Crop, canvas_size: tuple[int, int], fill_ratio: float, spec: SceneSpec, shadow_strength: float
) -> FloatImage:
    width, height = canvas_size
    top_y = height * _PEDESTAL_TOP_Y
    scale = _scale_for(crop, canvas_size, fill_ratio * 0.9, top_y - height * _TOP_MARGIN)
    placed = _place(crop, canvas_size, scale, (width / 2, top_y))
    columns = np.flatnonzero((placed.alpha > 0.5).any(axis=0))
    piece_w = int(columns[-1] - columns[0] + 1)
    footprint = placed.foot_right - placed.foot_left + 1
    # La tapa abarca la huella con holgura y acompaña el ancho de la pieza, sin pasar del 84 % del lienzo.
    rx = int(min(max(footprint * 0.75, piece_w * 0.55, width * 0.16), width * 0.42))
    ry = max(int(rx * 0.16), 2)
    cx, cy = round((placed.foot_left + placed.foot_right) / 2), round(top_y)
    # La pieza se apoya un poco por delante del centro de la tapa: en la línea del centro parece flotar.
    placed = _place(crop, canvas_size, scale, (width / 2, top_y + ry * 0.35))
    body_h = int(height * 0.13)

    background = _sweep(canvas_size, _rgb(spec.wall), _rgb(spec.floor), horizon=0.86)
    floor_shadow = np.zeros((height, width), np.float32)
    cv2.ellipse(
        floor_shadow, (cx, cy + body_h + int(ry * 0.2)), (int(rx * 1.15), int(ry * 1.3)), 0, 0, 360, 1.0, -1
    )
    floor_shadow = cv2.GaussianBlur(floor_shadow, (0, 0), rx * 0.12).astype(np.float32)
    background *= 1 - 0.28 * floor_shadow[..., None]

    # Cuerpo del cilindro con sombreado lateral (luz arriba a la izquierda).
    color = _rgb(spec.pedestal)
    body = np.zeros((height, width), np.float32)
    cv2.rectangle(body, (cx - rx, cy), (cx + rx, cy + body_h), 1.0, -1)
    cv2.ellipse(body, (cx, cy + body_h), (rx, ry), 0, 0, 180, 1.0, -1)
    xs = (np.arange(width, dtype=np.float32) - cx) / rx
    shade = np.clip(0.93 - 0.10 * xs - 0.16 * xs * xs, 0.6, 1.0)[None, :, None]
    body_color = np.broadcast_to(color * shade, (height, width, 3))
    background = _over(background, body_color, cv2.GaussianBlur(body, (0, 0), 0.8))

    # Tapa algo más clara, con un borde fino al frente.
    cap = np.zeros((height, width), np.float32)
    cv2.ellipse(cap, (cx, cy), (rx, ry), 0, 0, 360, 1.0, -1)
    cap = cv2.GaussianBlur(cap, (0, 0), 0.8).astype(np.float32)
    rows = (np.arange(height, dtype=np.float32)[:, None, None] - cy) / ry
    cap_color = np.broadcast_to(np.clip(color * 1.06 - 0.02 * rows, 0, 1), (height, width, 3))
    background = _over(background, cap_color, cap)
    edge = np.zeros((height, width), np.float32)
    cv2.ellipse(edge, (cx, cy), (rx, ry), 0, 0, 180, 1.0, 2)
    background *= 1 - 0.10 * cv2.GaussianBlur(edge, (0, 0), 1.2)[..., None]

    # La tapa es más clara que el piso: la sombra de contacto necesita más fuerza para leerse.
    background *= 1 - (_contact_shadow(placed, canvas_size, shadow_strength * 1.4) * cap)[..., None]
    return np.clip(_over(background, placed.image, placed.alpha), 0, 1)


@lru_cache(maxsize=8)
def _load_background(path: Path, mtime: float) -> FloatImage:
    del mtime  # Solo forma parte de la clave de la caché.
    with Image.open(path) as opened:
        rgb = ImageOps.exif_transpose(opened).convert("RGB")
        return np.asarray(rgb, np.float32) / 255.0


def _photo(
    crop: Crop,
    canvas_size: tuple[int, int],
    fill_ratio: float,
    background: BackgroundPhoto,
    shadow_strength: float,
) -> FloatImage:
    width, height = canvas_size
    source = _load_background(background.path, background.path.stat().st_mtime)
    source_h, source_w = source.shape[:2]
    # Cubrir el lienzo y mover el recorte para que el punto de apoyo quede lo más cerca posible
    # de su posición relativa en la foto.
    cover = max(width / source_w, height / source_h)
    scaled_w, scaled_h = max(round(source_w * cover), width), max(round(source_h * cover), height)
    interpolation = cv2.INTER_AREA if cover < 1 else cv2.INTER_CUBIC
    scaled = cv2.resize(source, (scaled_w, scaled_h), interpolation=interpolation)
    anchor_x, anchor_y = background.center_x * scaled_w, background.floor_y * scaled_h
    offset_x = int(np.clip(anchor_x - width / 2, 0, scaled_w - width))
    offset_y = int(np.clip(anchor_y - background.floor_y * height, 0, scaled_h - height))
    canvas = np.ascontiguousarray(
        scaled[offset_y : offset_y + height, offset_x : offset_x + width], np.float32
    )

    base = (anchor_x - offset_x, anchor_y - offset_y)
    max_height = min(background.piece_height * height, base[1] - height * 0.04)
    scale = _scale_for(crop, canvas_size, fill_ratio, max_height)
    placed = _place(crop, canvas_size, scale, base)
    canvas *= 1 - _contact_shadow(placed, canvas_size, shadow_strength * 0.9)[..., None]
    return np.clip(_over(canvas, placed.image, placed.alpha), 0, 1)
