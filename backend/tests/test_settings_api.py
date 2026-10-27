import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import settings as settings_api
from app.db.models import SettingRow
from app.db.session import get_sessionmaker
from app.main import create_app


def test_settings_api_covers_sections_and_never_reveals_secrets() -> None:
    with TestClient(create_app()) as client:
        initial = client.get("/api/v1/settings")
        updated = client.put(
            "/api/v1/settings/telegram",
            json={
                "enabled": True,
                "bot_token": "123456:token-secreto",
                "notify_chat_ids": [42],
            },
        )

    assert initial.status_code == 200
    assert set(initial.json()) == {
        "general",
        "processing_defaults",
        "export",
        "telegram",
        "notifications",
        "hot_folder",
        "importers",
        "quality",
        "pipeline",
    }
    assert updated.status_code == 200
    assert updated.json()["telegram"]["bot_token"] == {"configured": True}
    assert "token-secreto" not in updated.text
    with get_sessionmaker()() as session:
        stored = session.get(SettingRow, "telegram")
        assert stored is not None
        assert stored.value["bot_token"].startswith("enc:")
        assert "token-secreto" not in str(stored.value)


def test_empty_or_omitted_secret_preserves_it_and_null_clears_it() -> None:
    with TestClient(create_app()) as client:
        first = client.put(
            "/api/v1/settings/importers",
            json={"google_drive_api_key": "drive-secret", "max_download_mb": 80},
        )
        empty = client.put(
            "/api/v1/settings/importers",
            json={"google_drive_api_key": "", "max_download_mb": 90},
        )
        omitted = client.put("/api/v1/settings/importers", json={"max_download_mb": 100})
        cleared = client.put(
            "/api/v1/settings/importers",
            json={"google_drive_api_key": None, "max_download_mb": 110},
        )

    assert first.json()["importers"]["google_drive_api_key"] == {"configured": True}
    assert empty.json()["importers"]["google_drive_api_key"] == {"configured": True}
    assert omitted.json()["importers"]["google_drive_api_key"] == {"configured": True}
    assert cleared.json()["importers"]["google_drive_api_key"] == {"configured": False}
    assert cleared.json()["importers"]["max_download_mb"] == 110


def test_section_validation_uses_its_contract() -> None:
    with TestClient(create_app()) as client:
        invalid_section = client.put("/api/v1/settings/unknown", json={})
        invalid_value = client.put("/api/v1/settings/pipeline", json={"tile_size": 64})
        extra_field = client.put("/api/v1/settings/general", json={"unknown": True})

    assert invalid_section.status_code == 422
    assert invalid_value.status_code == 422
    assert extra_field.status_code == 422


def test_telegram_test_sends_to_configured_notification_chats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_post(url: str, *, json: dict[str, object], timeout: float) -> httpx.Response:
        calls.append({"url": url, "json": json, "timeout": timeout})
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(settings_api.httpx, "post", fake_post)
    with TestClient(create_app()) as client:
        missing = client.post("/api/v1/settings/telegram/test")
        client.put(
            "/api/v1/settings/telegram",
            json={"bot_token": "123:secret", "notify_chat_ids": [7, 8]},
        )
        tested = client.post("/api/v1/settings/telegram/test")

    assert missing.status_code == 409
    assert tested.status_code == 200
    assert tested.json() == {"ok": True, "sent": 2}
    assert [call["json"] for call in calls] == [
        {"chat_id": 7, "text": "Image Studio: conexión de Telegram correcta."},
        {"chat_id": 8, "text": "Image Studio: conexión de Telegram correcta."},
    ]


def test_telegram_test_maps_provider_errors_to_bad_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_post(url: str, *, json: dict[str, object], timeout: float) -> httpx.Response:
        del json, timeout
        request = httpx.Request("POST", url)
        return httpx.Response(401, request=request)

    monkeypatch.setattr(settings_api.httpx, "post", failing_post)
    with TestClient(create_app()) as client:
        client.put(
            "/api/v1/settings/telegram",
            json={"bot_token": "bad-token", "notify_chat_ids": [7]},
        )
        response = client.post("/api/v1/settings/telegram/test")

    assert response.status_code == 502
    assert "bad-token" not in response.text
