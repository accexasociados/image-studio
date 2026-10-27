"""Recorte de la pieza: BiRefNet en FP32 + refinado de bordes con filtro guiado.

Devuelve una máscara alfa float32 en [0, 1] del tamaño de la foto original."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

FloatImage = npt.NDArray[np.float32]
RgbImage = npt.NDArray[np.uint8]

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass(frozen=True)
class SegmentationParams:
    size: int = 1024
    # Radio del filtro guiado relativo al lado mayor (0.002 ≈ 8 px en una foto de 4000 px).
    guided_radius_ratio: float = 0.002
    guided_eps: float = 1e-4
    # Componentes sueltos más chicos que esta fracción de la pieza mayor se descartan (polvo, ruido).
    min_component_ratio: float = 0.01
    # Huecos internos más chicos que esta fracción de la pieza se rellenan; los mayores se respetan.
    max_hole_ratio: float = 0.0015


@dataclass(frozen=True)
class SegmentationResult:
    alpha: FloatImage
    # Fracción de píxeles de borde con alfa dudoso (0.1 a 0.9): alto = translúcido o poco contraste.
    uncertain_edge_ratio: float
    components: int


@lru_cache(maxsize=1)
def load_birefnet(weights_dir: Path, device: str) -> Any:
    import torch
    from safetensors.torch import load_file

    from app.pipeline.vendor.birefnet.birefnet import BiRefNet
    from app.pipeline.vendor.birefnet.BiRefNet_config import BiRefNetConfig

    # bb_pretrained=False: no lee pesos externos; todos los pesos vienen del safetensors (sin pickle).
    model = BiRefNet(config=BiRefNetConfig(bb_pretrained=False))
    model.load_state_dict(load_file(str(weights_dir / "model.safetensors")))
    return model.to(torch.device(device)).float().eval()


def predict_probability(image: RgbImage, model: Any, size: int, device: str) -> FloatImage:
    import torch

    resized = cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    normalized = (resized - _IMAGENET_MEAN) / _IMAGENET_STD
    tensor = torch.from_numpy(normalized.transpose(2, 0, 1)).unsqueeze(0).to(device)
    with torch.inference_mode():
        logits = model(tensor)[-1]
        probability = logits.sigmoid()[0, 0].float().cpu().numpy()
    height, width = image.shape[:2]
    upscaled: FloatImage = cv2.resize(probability, (width, height), interpolation=cv2.INTER_LINEAR)
    return upscaled.astype(np.float32)


def guided_filter(guide: FloatImage, source: FloatImage, radius: int, eps: float) -> FloatImage:
    """Filtro guiado (He et al.): ajusta los bordes de `source` a los bordes reales de `guide`."""
    kernel = (2 * radius + 1, 2 * radius + 1)

    def box(values: FloatImage) -> FloatImage:
        return cv2.boxFilter(values, -1, kernel, borderType=cv2.BORDER_REFLECT).astype(np.float32)

    mean_guide = box(guide)
    mean_source = box(source)
    covariance = box(guide * source) - mean_guide * mean_source
    variance = box(guide * guide) - mean_guide * mean_guide
    a: FloatImage = (covariance / (variance + eps)).astype(np.float32)
    b: FloatImage = (mean_source - a * mean_guide).astype(np.float32)
    return (box(a) * guide + box(b)).astype(np.float32)


def clean_mask(alpha: FloatImage, params: SegmentationParams) -> tuple[FloatImage, int]:
    binary = (alpha > 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return alpha, 0
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = np.flatnonzero(areas >= areas.max() * params.min_component_ratio) + 1
    kept = np.isin(labels, keep)
    # Un margen alrededor de lo conservado deja intacto el borde suave del alfa.
    near_kept = cv2.dilate(kept.astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
    cleaned = np.where(near_kept, alpha, 0.0).astype(np.float32)

    holes = (~kept).astype(np.uint8)
    hole_count, hole_labels, hole_stats, _ = cv2.connectedComponentsWithStats(holes, connectivity=4)
    object_area = float(kept.sum())
    height, width = alpha.shape
    for index in range(1, hole_count):
        x, y, w, h, area = hole_stats[index]
        touches_border = x == 0 or y == 0 or x + w == width or y + h == height
        if not touches_border and area <= object_area * params.max_hole_ratio:
            cleaned[hole_labels == index] = 1.0
    return cleaned, len(keep)


def uncertain_edge_ratio(alpha: FloatImage) -> float:
    binary = (alpha > 0.5).astype(np.uint8)
    edge = cv2.morphologyEx(binary, cv2.MORPH_GRADIENT, np.ones((9, 9), np.uint8)).astype(bool)
    if not edge.any():
        return 0.0
    values = alpha[edge]
    return float(((values > 0.1) & (values < 0.9)).mean())


def segment(
    image: RgbImage, model: Any, device: str, params: SegmentationParams | None = None
) -> SegmentationResult:
    params = params or SegmentationParams()
    probability = predict_probability(image, model, params.size, device)

    guide = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    radius = max(2, round(max(image.shape[:2]) * params.guided_radius_ratio))
    refined = np.clip(guided_filter(guide, probability, radius, params.guided_eps), 0.0, 1.0).astype(
        np.float32
    )

    alpha, components = clean_mask(refined, params)
    return SegmentationResult(
        alpha=alpha, uncertain_edge_ratio=uncertain_edge_ratio(alpha), components=components
    )
