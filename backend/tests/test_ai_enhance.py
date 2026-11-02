"""Fase 13: "Mejorar con IA" (Flux Kontext en fal.ai y OpenAI), sin red: las respuestas se simulan."""

import base64
import io
import json
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

import app.pipeline.run as run
from app.config import get_settings
from app.contracts import AppSettings, ProcessOptions
from app.contracts.settings import AiSettings
from app.db.models import SettingRow
from app.db.session import get_sessionmaker
from app.main import create_app
from app.pipeline.ai_enhance import AiEnhanceError, build_prompt, enhance_with_ai


def _png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _image(width: int = 400, height: int = 500) -> np.ndarray:
    return np.full((height, width, 3), 0.8, np.float32)


def test_ai_enhance_is_off_unless_selected() -> None:
    assert ProcessOptions().ai_enhance is False
    assert AiSettings().provider == "none"


def test_prompt_keeps_the_piece_and_forbids_animated_styles() -> None:
    prompt = build_prompt(AiSettings(extra_prompt="fondo gris"))
    assert "same shape" in prompt
    assert "not a cartoon" in prompt and "not animated" in prompt
    assert prompt.endswith("fondo gris")


def test_flux_kontext_sends_the_photo_and_returns_it_at_the_format_size() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        body = json.loads(request.content)
        seen["body"] = body
        result = "data:image/png;base64," + base64.b64encode(_png(1024, 1280, (10, 200, 30))).decode()
        return httpx.Response(200, json={"images": [{"url": result}]})

    settings = AiSettings(provider="fal_flux_kontext", fal_api_key=SecretStr("clave-fal"))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = enhance_with_ai(_image(), settings, client)

    assert seen["url"] == "https://fal.run/fal-ai/flux-pro/kontext"
    assert seen["auth"] == "Key clave-fal"
    body = seen["body"]
    assert isinstance(body, dict)
    assert str(body["image_url"]).startswith("data:image/png;base64,")
    assert "not animated" in str(body["prompt"])
    assert result.shape == (500, 400, 3)
    assert result[250, 200, 1] > 0.7  # el verde de la respuesta, no la foto enviada


def test_openai_asks_for_high_fidelity_and_a_portrait_size() -> None:
    seen: dict[str, bytes | str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = request.content
        b64 = base64.b64encode(_png(1024, 1536, (200, 20, 20))).decode()
        return httpx.Response(200, json={"data": [{"b64_json": b64}]})

    settings = AiSettings(provider="openai", openai_api_key=SecretStr("sk-prueba"), openai_quality="high")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = enhance_with_ai(_image(1080, 1350), settings, client)

    body = seen["body"]
    assert isinstance(body, bytes)
    assert seen["auth"] == "Bearer sk-prueba"
    for field in (b"gpt-image-2", b"1024x1536", b"input_fidelity", b"high"):
        assert field in body
    assert result.shape == (1350, 1080, 3)


def test_service_errors_never_include_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "bad key"})

    settings = AiSettings(provider="openai", openai_api_key=SecretStr("sk-secreta"))
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(AiEnhanceError) as error,
    ):
        enhance_with_ai(_image(), settings, client)
    assert "clave" in str(error.value) and "bad key" in str(error.value)
    assert "sk-secreta" not in str(error.value)


def test_no_credits_is_explained_with_the_service_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"error": {"message": "You have no credits remaining.", "code": "credit_balance_exhausted"}}
        return httpx.Response(429, json=body)

    settings = AiSettings(provider="openai", openai_api_key=SecretStr("sk-secreta"))
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(AiEnhanceError) as error,
    ):
        enhance_with_ai(_image(), settings, client)
    assert "no tiene saldo" in str(error.value)
    assert "You have no credits remaining." in str(error.value)


def test_a_model_without_input_fidelity_is_asked_again_without_it() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        if b"input_fidelity" in request.content:
            error = {"message": "Unknown parameter: 'input_fidelity'.", "param": "input_fidelity"}
            return httpx.Response(400, json={"error": error})
        b64 = base64.b64encode(_png(1024, 1024, (20, 20, 200))).decode()
        return httpx.Response(200, json={"data": [{"b64_json": b64}]})

    settings = AiSettings(provider="openai", openai_api_key=SecretStr("sk-prueba"))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = enhance_with_ai(_image(), settings, client)
    assert len(bodies) == 2 and b"input_fidelity" not in bodies[1]
    assert result.shape == (500, 400, 3)


def test_the_retired_openai_model_is_replaced() -> None:
    assert AiSettings().openai_model == "gpt-image-2"
    assert AiSettings(openai_model="gpt-image-1").openai_model == "gpt-image-2"
    assert AiSettings(openai_model="gpt-image-1.5").openai_model == "gpt-image-1.5"


def test_ai_keys_are_encrypted_and_never_returned() -> None:
    with TestClient(create_app()) as client:
        response = client.put(
            "/api/v1/settings/ai",
            json={"provider": "fal_flux_kontext", "fal_api_key": "clave-secreta-fal"},
        )
    assert response.status_code == 200
    assert response.json()["ai"]["fal_api_key"] == {"configured": True}
    assert response.json()["ai"]["openai_api_key"] == {"configured": False}
    assert "clave-secreta-fal" not in response.text
    with get_sessionmaker()() as session:
        stored = session.get(SettingRow, "ai")
        assert stored is not None
        assert stored.value["fal_api_key"].startswith("enc:")


@pytest.fixture
def real_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_MODE", "real")
    monkeypatch.setenv("DEVICE", "cpu")
    get_settings.cache_clear()


def _source(tmp_path: Path) -> tuple[Path, Path]:
    image = np.full((400, 300, 3), 180, np.uint8)
    alpha = np.zeros((400, 300), np.uint8)
    cv2.rectangle(alpha, (90, 60), (210, 340), 255, -1)
    image[alpha > 0] = (230, 110, 30)
    source, mask = tmp_path / "pieza.png", tmp_path / "mask.png"
    Image.fromarray(image).save(source)
    Image.fromarray(alpha).save(mask)
    return source, mask


def _settings(provider: str = "openai") -> AppSettings:
    settings = AppSettings()
    settings.pipeline.upscale_model = "lanczos"
    if provider == "openai":
        settings.ai = AiSettings(provider="openai", openai_api_key=SecretStr("sk-prueba"))
    return settings


def _process(tmp_path: Path, settings: AppSettings, ai: bool = True):  # type: ignore[no-untyped-def]
    source, mask = _source(tmp_path)
    return run.process_image(
        source,
        ProcessOptions(presets=["storefront"], scene="white", upscale=1, ai_enhance=ai),
        tmp_path / "out",
        base_name="P",
        mask_override=mask,
        settings=settings,
    )


def test_pipeline_adds_the_ai_variant_next_to_the_normal_one(
    tmp_path: Path, real_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "enhance_with_ai", lambda image, settings: np.clip(image * 0.9, 0, 1))
    result = _process(tmp_path, _settings())
    variants = sorted(output.variant for output in result.outputs)
    assert variants == ["ai", "smooth"]
    ai = next(output for output in result.outputs if output.variant == "ai")
    assert ai.path.endswith("_ai.webp") and Path(ai.path).exists()
    assert "ai_failed" not in result.review_reasons


def test_a_failing_service_keeps_the_studio_photo_and_flags_it(
    tmp_path: Path, real_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(image: np.ndarray, settings: AiSettings) -> np.ndarray:
        raise AiEnhanceError("El servicio de IA respondió con error 500.")

    monkeypatch.setattr(run, "enhance_with_ai", fail)
    result = _process(tmp_path, _settings())
    assert [output.variant for output in result.outputs] == ["smooth"]
    assert "ai_failed" in result.review_reasons
    assert result.ai_error == "El servicio de IA respondió con error 500."


def test_without_a_service_the_photo_is_flagged_and_nothing_is_sent(
    tmp_path: Path, real_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def never(image: np.ndarray, settings: AiSettings) -> np.ndarray:
        raise AssertionError("no debe llamar al servicio")

    monkeypatch.setattr(run, "enhance_with_ai", never)
    result = _process(tmp_path, _settings(provider="none"))
    assert [output.variant for output in result.outputs] == ["smooth"]
    assert "ai_not_configured" in result.review_reasons


def test_without_the_option_the_service_is_never_called(
    tmp_path: Path, real_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def never(image: np.ndarray, settings: AiSettings) -> np.ndarray:
        raise AssertionError("no debe llamar al servicio")

    monkeypatch.setattr(run, "enhance_with_ai", never)
    result = _process(tmp_path, _settings(), ai=False)
    assert [output.variant for output in result.outputs] == ["smooth"]
    assert "ai_not_configured" not in result.review_reasons
