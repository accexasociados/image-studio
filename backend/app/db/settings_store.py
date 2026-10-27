"""Lectura y escritura de AppSettings en la tabla `settings`, con los secretos cifrados (Fernet)."""

from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contracts.settings import SECRET_FIELDS, AppSettings, SettingsSection
from app.db.models import SettingRow

_ENCRYPTED_PREFIX = "enc:"


def _load_key() -> bytes:
    """SECRET_KEY del entorno; en local, si no existe, se genera una vez en data/secret.key."""
    settings = get_settings()
    if settings.secret_key is not None:
        return settings.secret_key.get_secret_value().encode()
    key_file: Path = settings.data_dir / "secret.key"
    if not key_file.exists():
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(Fernet.generate_key())
    return key_file.read_bytes().strip()


def _fernet() -> Fernet:
    return Fernet(_load_key())


def _encrypt_secrets(section: str, value: dict[str, Any], fernet: Fernet) -> dict[str, Any]:
    for secret_section, field in SECRET_FIELDS:
        raw = value.get(field)
        if secret_section == section and isinstance(raw, str) and raw:
            value[field] = _ENCRYPTED_PREFIX + fernet.encrypt(raw.encode()).decode()
    return value


def _decrypt_secrets(section: str, value: dict[str, Any], fernet: Fernet) -> dict[str, Any]:
    for secret_section, field in SECRET_FIELDS:
        raw = value.get(field)
        if secret_section == section and isinstance(raw, str) and raw.startswith(_ENCRYPTED_PREFIX):
            try:
                value[field] = fernet.decrypt(raw.removeprefix(_ENCRYPTED_PREFIX).encode()).decode()
            except InvalidToken:
                # La llave cambió: el secreto se pierde y hay que volver a cargarlo desde la web.
                value[field] = None
    return value


def load_settings(session: Session) -> AppSettings:
    fernet = _fernet()
    data: dict[str, Any] = {}
    for row in session.query(SettingRow).all():
        section: SettingsSection = row.section  # type: ignore[assignment]
        if section in AppSettings.model_fields:
            data[section] = _decrypt_secrets(section, dict(row.value), fernet)
    return AppSettings.model_validate(data)


def save_settings(session: Session, settings: AppSettings) -> None:
    fernet = _fernet()
    dumped = settings.model_dump(mode="python")
    for section, value in dumped.items():
        plain = {
            key: (item.get_secret_value() if isinstance(item, SecretStr) else item)
            for key, item in value.items()
        }
        encrypted = _encrypt_secrets(section, plain, fernet)
        row = session.get(SettingRow, section)
        if row is None:
            session.add(SettingRow(section=section, value=encrypted))
        else:
            row.value = encrypted
    session.commit()
