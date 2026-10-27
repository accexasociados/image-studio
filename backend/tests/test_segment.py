import hashlib
from pathlib import Path

import cv2
import numpy as np

from app.pipeline.segment import SegmentationParams, clean_mask, guided_filter, uncertain_edge_ratio

VENDOR_DIR = Path(__file__).resolve().parents[1] / "app" / "pipeline" / "vendor" / "birefnet"
VENDOR_HASHES = {
    "birefnet.py": "208771ae626f653d64128fbf2d6ac9f8e645c5cc5e286258a73ec3322bbfe5ef",
    "BiRefNet_config.py": "e7b8c2a74f6cea6a59553d517f71d47f2c1d90e670a13416af17c25fe2f3dc52",
}


def test_vendored_birefnet_is_unmodified() -> None:
    for name, expected in VENDOR_HASHES.items():
        assert hashlib.sha256((VENDOR_DIR / name).read_bytes()).hexdigest() == expected, name


def _disk_mask(size: int = 200, radius: int = 60) -> np.ndarray:
    mask = np.zeros((size, size), np.float32)
    cv2.circle(mask, (size // 2, size // 2), radius, 1.0, -1)
    return mask


def test_guided_filter_snaps_blurry_mask_to_image_edges() -> None:
    sharp = _disk_mask()
    blurry = cv2.GaussianBlur(sharp, (0, 0), 4)
    refined = guided_filter(sharp, blurry, radius=8, eps=1e-4)
    # El disco empieza en x=40 de la fila 100: el salto en el borde real debe ser mucho más nítido.
    step_refined = refined[100, 40] - refined[100, 39]
    step_blurry = blurry[100, 40] - blurry[100, 39]
    assert step_refined > 0.4
    assert step_refined > 4 * step_blurry


def test_clean_mask_drops_specks_and_fills_small_holes_only() -> None:
    mask = _disk_mask(400, 150)
    mask[5:8, 5:8] = 1.0  # polvo
    cv2.circle(mask, (200, 200), 2, 0.0, -1)  # hueco pequeño: se rellena
    cv2.circle(mask, (200, 120), 25, 0.0, -1)  # hueco real (ojo de la calabaza): se respeta
    cleaned, components = clean_mask(mask, SegmentationParams())
    assert components == 1
    assert cleaned[6, 6] == 0.0
    assert cleaned[200, 200] == 1.0
    assert cleaned[120, 200] == 0.0


def test_uncertain_edge_ratio_is_low_for_hard_edges() -> None:
    assert uncertain_edge_ratio(_disk_mask()) == 0.0
    assert uncertain_edge_ratio(np.full((50, 50), 0.5, np.float32)) == 0.0
