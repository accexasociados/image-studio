"""Ajuste automático según la foto (2026-11-02): cada foto recibe la fuerza que necesita."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

import app.pipeline.run as run
from app.config import get_settings
from app.contracts import AppSettings, ProcessOptions
from app.pipeline.auto import decide


def _textured(blur: float, glints: bool = False) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(3)
    base = rng.uniform(0.15, 0.45, (600, 600)).astype(np.float32)
    base = cv2.GaussianBlur(base, (0, 0), 0.7)
    if blur:
        base = cv2.GaussianBlur(base, (0, 0), blur)
    image = np.stack([base * 0.5, base * 0.7, base * 1.6], axis=-1).clip(0, 1).astype(np.float32)
    if glints:
        for x in range(120, 480, 60):
            cv2.circle(image, (x, 300), 10, (0.92, 0.94, 0.98), -1)
    alpha = np.zeros((600, 600), np.float32)
    alpha[60:540, 60:540] = 1
    return image, alpha


def test_a_soft_photo_gets_more_sharpening_than_a_crisp_one() -> None:
    soft = decide(*_textured(blur=3.0), exposure_gain=1.0)
    crisp = decide(*_textured(blur=0), exposure_gain=1.0)
    assert soft is not None and crisp is not None
    assert soft.sharpen > crisp.sharpen + 20


def test_glare_is_reduced_only_when_the_photo_has_glints() -> None:
    plain = decide(*_textured(blur=0), exposure_gain=1.0)
    shiny = decide(*_textured(blur=0, glints=True), exposure_gain=1.0)
    assert plain is not None and shiny is not None
    assert plain.glare == 0
    assert shiny.glare > plain.glare + 5


def test_light_reports_the_exposure_change() -> None:
    result = decide(*_textured(blur=0), exposure_gain=1.17)
    assert result is not None and result.light == 17


def test_a_tiny_piece_is_not_measured() -> None:
    image = np.zeros((100, 100, 3), np.float32)
    alpha = np.zeros((100, 100), np.float32)
    alpha[10:20, 10:20] = 1
    assert decide(image, alpha, 1.0) is None


@pytest.fixture
def real_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_MODE", "real")
    monkeypatch.setenv("DEVICE", "cpu")
    get_settings.cache_clear()


def _process(tmp_path: Path, auto: bool, monkeypatch: pytest.MonkeyPatch) -> tuple[object, list[float]]:
    image, alpha = _textured(blur=2.5)
    source, mask = tmp_path / "pieza.png", tmp_path / "mask.png"
    Image.fromarray((image * 255).astype(np.uint8)).save(source)
    Image.fromarray((alpha * 255).astype(np.uint8)).save(mask)
    used: list[float] = []
    original = run.sharpen

    def spy(composed: np.ndarray, strength: float) -> np.ndarray:
        used.append(strength)
        return original(composed, strength)

    monkeypatch.setattr(run, "sharpen", spy)
    settings = AppSettings()
    settings.pipeline.upscale_model = "lanczos"
    result = run.process_image(
        source,
        ProcessOptions(presets=["storefront"], upscale=1, layer_lines="keep", sharpen=10, auto_adjust=auto),
        tmp_path / "out",
        base_name="P",
        mask_override=mask,
        settings=settings,
    )
    return result, used


def test_the_pipeline_uses_and_reports_the_automatic_values(
    tmp_path: Path, real_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, used = _process(tmp_path, True, monkeypatch)
    auto = result.auto_adjustments  # type: ignore[attr-defined]
    assert auto is not None and auto.sharpen > 60
    assert used == [auto.sharpen / 100]


def test_without_automatic_adjustment_the_sliders_are_used(
    tmp_path: Path, real_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, used = _process(tmp_path, False, monkeypatch)
    assert result.auto_adjustments is None  # type: ignore[attr-defined]
    assert used == [0.1]
