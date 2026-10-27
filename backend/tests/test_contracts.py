import pytest
from pydantic import ValidationError

from app.contracts import AppSettings, ImageUpdate, ProcessOptions


def test_process_options_defaults() -> None:
    options = ProcessOptions()
    assert options.presets == ["storefront", "instagram_feed"]
    assert options.layer_lines == "keep"
    assert options.shadow == "auto"
    assert options.upscale == 2


def test_process_options_removes_duplicate_presets() -> None:
    assert ProcessOptions(presets=["storefront", "storefront"]).presets == ["storefront"]


@pytest.mark.parametrize(
    "payload",
    [{"presets": []}, {"smooth_strength": 101}, {"fill_ratio": 0.2}, {"upscale": 3}, {"unknown": True}],
)
def test_process_options_rejects_invalid_values(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProcessOptions.model_validate(payload)


def test_sku_only_allows_safe_filename_characters() -> None:
    assert ImageUpdate(sku="DRG-01_v2").sku == "DRG-01_v2"
    with pytest.raises(ValidationError):
        ImageUpdate(sku="../../etc")


def test_app_settings_defaults_are_safe() -> None:
    settings = AppSettings()
    assert settings.telegram.enabled is False
    assert settings.pipeline.half_precision is False
    assert settings.export.background_hex == "#FFFFFF"
