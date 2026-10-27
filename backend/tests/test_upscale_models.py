"""Fase 10: modelos de ampliación elegibles, fidelidad por foto y ampliación con modelos x4."""

from pathlib import Path
from typing import get_args

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contracts import ProcessOptions, UpscaleModel
from app.main import create_app
from app.pipeline.catalog import UPSCALE_MODELS
from app.pipeline.upscale import UpscaleParams, Upscaler, upscale


def test_catalog_covers_every_model_in_the_contract() -> None:
    assert set(UPSCALE_MODELS) == set(get_args(UpscaleModel))
    assert all(spec.scale in (2, 4) and len(spec.sha256) == 64 for spec in UPSCALE_MODELS.values())


def test_upscale_models_endpoint_reports_what_is_installed(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models_dir = isolated_env / "models"
    (models_dir / "upscale").mkdir(parents=True)
    (models_dir / UPSCALE_MODELS["nmkd_siax"].file).write_bytes(b"pesos")
    monkeypatch.setenv("MODELS_DIR", str(models_dir))

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/settings/upscale-models")

    installed = {item["id"]: item["installed"] for item in response.json()}
    assert installed == {"realesrgan_x2plus": False, "nmkd_siax": True}


def test_pipeline_settings_accept_only_known_models() -> None:
    with TestClient(create_app()) as client:
        valid = client.put("/api/v1/settings/pipeline", json={"upscale_model": "realesrgan_x2plus"})
        invalid = client.put("/api/v1/settings/pipeline", json={"upscale_model": "otro"})

    assert valid.json()["pipeline"]["upscale_model"] == "realesrgan_x2plus"
    assert invalid.status_code == 422


def test_upscale_fidelity_is_a_percentage() -> None:
    assert ProcessOptions().upscale_fidelity is None
    assert ProcessOptions(upscale_fidelity=30).upscale_fidelity == 30
    with pytest.raises(ValidationError):
        ProcessOptions(upscale_fidelity=101)


class _NearestX4:
    """Modelo falso x4: repite cada píxel y cuenta cuántas veces lo llaman."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, patch: object) -> object:
        import torch

        assert isinstance(patch, torch.Tensor)
        self.calls += 1
        return patch.repeat_interleave(4, dim=2).repeat_interleave(4, dim=3)


@pytest.mark.parametrize(("factor", "passes"), [(1.2, 1), (3.0, 1), (6.0, 2)])
def test_x4_models_run_once_unless_much_more_is_needed(factor: float, passes: int) -> None:
    pytest.importorskip("torch")
    model = _NearestX4()
    image = np.random.default_rng(0).random((40, 30, 3)).astype(np.float32)
    alpha = np.ones((40, 30), np.float32)

    result, scaled = upscale(image, alpha, factor, Upscaler(model, 4), "cpu", UpscaleParams(tile_size=256))

    assert model.calls == passes
    assert result.shape[:2] == scaled.shape == (round(40 * factor), round(30 * factor))
