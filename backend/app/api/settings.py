from typing import Annotated

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.contracts import SECRET_FIELDS, AppSettings, AppSettingsPublic, SettingsSection, TelegramTestResult
from app.contracts.options import ProcessOptions
from app.contracts.settings import (
    ExportSettings,
    GeneralSettings,
    HotFolderSettings,
    ImporterSettings,
    ImporterSettingsPublic,
    NotificationSettings,
    PipelineSettings,
    QualitySettings,
    SecretConfigured,
    TelegramSettings,
    TelegramSettingsPublic,
)
from app.db.session import get_session
from app.db.settings_store import load_settings, save_settings

router = APIRouter(prefix="/settings", tags=["settings"])
SessionDep = Annotated[Session, Depends(get_session)]

_SECTION_MODELS: dict[SettingsSection, type[BaseModel]] = {
    "general": GeneralSettings,
    "processing_defaults": ProcessOptions,
    "export": ExportSettings,
    "telegram": TelegramSettings,
    "notifications": NotificationSettings,
    "hot_folder": HotFolderSettings,
    "importers": ImporterSettings,
    "quality": QualitySettings,
    "pipeline": PipelineSettings,
}


def _public_settings(settings: AppSettings) -> AppSettingsPublic:
    telegram = settings.telegram.model_dump(mode="python", exclude={"bot_token"})
    importers = settings.importers.model_dump(mode="python", exclude={"google_drive_api_key"})
    return AppSettingsPublic(
        general=settings.general,
        processing_defaults=settings.processing_defaults,
        export=settings.export,
        telegram=TelegramSettingsPublic(
            **telegram,
            bot_token=SecretConfigured(configured=settings.telegram.bot_token is not None),
        ),
        notifications=settings.notifications,
        hot_folder=settings.hot_folder,
        importers=ImporterSettingsPublic(
            **importers,
            google_drive_api_key=SecretConfigured(
                configured=settings.importers.google_drive_api_key is not None
            ),
        ),
        quality=settings.quality,
        pipeline=settings.pipeline,
    )


@router.get("", response_model=AppSettingsPublic)
def get_app_settings(session: SessionDep) -> AppSettingsPublic:
    return _public_settings(load_settings(session))


@router.put("/{section}", response_model=AppSettingsPublic)
def replace_settings_section(
    section: SettingsSection,
    session: SessionDep,
    payload: Annotated[dict[str, object], Body()],
) -> AppSettingsPublic:
    current = load_settings(session)
    section_payload = dict(payload)
    current_section = getattr(current, section)
    for secret_section, field in SECRET_FIELDS:
        if secret_section == section and (field not in section_payload or section_payload[field] == ""):
            section_payload[field] = getattr(current_section, field)

    try:
        replacement = _SECTION_MODELS[section].model_validate(section_payload)
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.errors(include_url=False),
        ) from None

    complete = current.model_dump(mode="python")
    complete[section] = replacement
    updated = AppSettings.model_validate(complete)
    save_settings(session, updated)
    return _public_settings(updated)


@router.post("/telegram/test", response_model=TelegramTestResult)
def test_telegram(session: SessionDep) -> TelegramTestResult:
    telegram = load_settings(session).telegram
    if telegram.bot_token is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Configura el token de Telegram antes de probarlo.",
        )
    recipients = telegram.notify_chat_ids or telegram.allowed_chat_ids
    if not recipients:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Configura al menos un chat de Telegram para la prueba.",
        )

    url = f"https://api.telegram.org/bot{telegram.bot_token.get_secret_value()}/sendMessage"
    try:
        for chat_id in recipients:
            response = httpx.post(
                url,
                json={"chat_id": chat_id, "text": "Image Studio: conexión de Telegram correcta."},
                timeout=10.0,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or body.get("ok") is not True:
                raise httpx.HTTPError("Telegram rechazó el mensaje de prueba.")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo completar la prueba de Telegram.",
        ) from None
    return TelegramTestResult(sent=len(recipients))
