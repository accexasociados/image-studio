from pydantic import SecretStr

from app.contracts import AppSettings
from app.db.migrate import upgrade_to_head
from app.db.models import SettingRow
from app.db.session import get_sessionmaker
from app.db.settings_store import load_settings, save_settings


def test_settings_roundtrip_encrypts_secrets() -> None:
    upgrade_to_head()
    settings = AppSettings()
    settings.telegram.enabled = True
    settings.telegram.bot_token = SecretStr("123456:ABC-token")
    settings.telegram.notify_chat_ids = [42]
    settings.processing_defaults.layer_lines = "smooth"

    with get_sessionmaker()() as session:
        save_settings(session, settings)
        stored = session.get(SettingRow, "telegram")
        assert stored is not None
        assert stored.value["bot_token"].startswith("enc:")
        assert "ABC-token" not in str(stored.value)

    with get_sessionmaker()() as session:
        loaded = load_settings(session)
    assert loaded.telegram.bot_token is not None
    assert loaded.telegram.bot_token.get_secret_value() == "123456:ABC-token"
    assert loaded.telegram.notify_chat_ids == [42]
    assert loaded.processing_defaults.layer_lines == "smooth"


def test_load_settings_returns_defaults_on_empty_db() -> None:
    upgrade_to_head()
    with get_sessionmaker()() as session:
        assert load_settings(session) == AppSettings()
