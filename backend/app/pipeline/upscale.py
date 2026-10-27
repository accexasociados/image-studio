"""Mejora de resolución: Real-ESRGAN x2 por tiles en FP32, solo cuando hace falta, más reinyección
del detalle fino de la foto original para que las líneas de capa no queden "enceradas"."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.pipeline.types import Alpha, FloatImage


@dataclass(frozen=True)
class UpscaleParams:
    tile_size: int = 512
    tile_overlap: int = 32
    # Fracción del detalle fino que se toma de la original escalada con Lanczos en vez del modelo.
    detail_reinjection: float = 0.6
    use_model: bool = True


@lru_cache(maxsize=1)
def load_realesrgan(weights_path: Path, device: str) -> Any:
    import torch
    from spandrel import ModelLoader

    descriptor = ModelLoader().load_from_file(str(weights_path))
    return descriptor.model.to(torch.device(device)).float().eval()


def _run_tiles(image: FloatImage, model: Any, device: str, params: UpscaleParams, scale: int) -> FloatImage:
    import torch

    height, width = image.shape[:2]
    tile, overlap = params.tile_size, params.tile_overlap
    output = np.zeros((height * scale, width * scale, 3), np.float32)
    weight = np.zeros((height * scale, width * scale, 1), np.float32)
    step = max(tile - 2 * overlap, 1)
    for top in range(0, height, step):
        for left in range(0, width, step):
            y0, x0 = max(top - overlap, 0), max(left - overlap, 0)
            y1, x1 = min(top + step + overlap, height), min(left + step + overlap, width)
            patch = torch.from_numpy(image[y0:y1, x0:x1].transpose(2, 0, 1).copy()).unsqueeze(0).to(device)
            with torch.inference_mode():
                result = model(patch)[0].clamp(0, 1).float().cpu().numpy().transpose(1, 2, 0)
            # Ventana que se desvanece en el solape para que no se noten las uniones entre tiles.
            ramp_y = _ramp(y1 - y0, overlap if y0 > 0 else 0, overlap if y1 < height else 0)
            ramp_x = _ramp(x1 - x0, overlap if x0 > 0 else 0, overlap if x1 < width else 0)
            window = np.repeat(np.repeat(np.outer(ramp_y, ramp_x), scale, 0), scale, 1)[..., None]
            output[y0 * scale : y1 * scale, x0 * scale : x1 * scale] += result * window
            weight[y0 * scale : y1 * scale, x0 * scale : x1 * scale] += window
    blended: FloatImage = (output / np.maximum(weight, 1e-6)).astype(np.float32)
    return blended


def _ramp(length: int, fade_start: int, fade_end: int) -> FloatImage:
    ramp: FloatImage = np.ones(length, np.float32)
    if fade_start:
        ramp[:fade_start] = np.linspace(0.05, 1.0, fade_start, dtype=np.float32)
    if fade_end:
        ramp[-fade_end:] = np.linspace(1.0, 0.05, fade_end, dtype=np.float32)
    return ramp


def reinject_detail(
    model_output: FloatImage, reference: FloatImage, amount: float, sigma: float
) -> FloatImage:
    """Reemplaza parte de las altas frecuencias del modelo por las de la original escalada."""
    model_low = cv2.GaussianBlur(model_output, (0, 0), sigma)
    reference_high = reference - cv2.GaussianBlur(reference, (0, 0), sigma)
    model_high = model_output - model_low
    mixed = model_low + (1.0 - amount) * model_high + amount * reference_high
    result: FloatImage = np.clip(mixed, 0.0, 1.0).astype(np.float32)
    return result


def upscale(
    image: FloatImage, alpha: Alpha, factor: float, model: Any | None, device: str, params: UpscaleParams
) -> tuple[FloatImage, Alpha]:
    """Escala `image` y `alpha` por `factor` (>= 1). Usa el modelo x2 tantas veces como haga falta."""
    if factor <= 1.0:
        return image, alpha
    height, width = image.shape[:2]
    target = (round(width * factor), round(height * factor))
    lanczos = cv2.resize(image, target, interpolation=cv2.INTER_LANCZOS4)
    scaled_alpha = np.clip(cv2.resize(alpha, target, interpolation=cv2.INTER_CUBIC), 0, 1).astype(np.float32)

    if model is None or not params.use_model:
        return np.clip(lanczos, 0, 1).astype(np.float32), scaled_alpha

    current = image
    # Una pasada x2 más Lanczos hasta 2,8x; la segunda pasada (4x más lenta) solo si hace falta más.
    while current.shape[1] * 1.4 < target[0]:
        current = _run_tiles(current, model, device, params, scale=2)
    enhanced: FloatImage = cv2.resize(current, target, interpolation=cv2.INTER_AREA).astype(np.float32)
    sigma = max(0.8, factor * 0.6)
    reference: FloatImage = np.clip(lanczos, 0, 1).astype(np.float32)
    return reinject_detail(enhanced, reference, params.detail_reinjection, sigma), scaled_alpha
