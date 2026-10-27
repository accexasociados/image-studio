"""Configuración de arranque: solo lo que el proceso necesita antes de abrir su base de datos
(puertos, rutas, conexiones, la llave de cifrado). Todo lo demás (Telegram, avisos, formatos,
importadores, carpeta vigilada, modelos) es editable desde la web y vive en la tabla `settings`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    api_port: int = 8090
    data_dir: Path = PROJECT_ROOT / "data"
    models_dir: Path = PROJECT_ROOT / "models"
    device: Literal["cuda", "cpu"] = "cuda"
    pipeline_mode: Literal["real", "stub"] = "real"
    # Cifra los secretos guardados en la tabla `settings` (token de Telegram, API keys).
    secret_key: SecretStr | None = None
    database_url_env: str | None = Field(default=None, validation_alias="DATABASE_URL")
    queue_backend: Literal["sqlite", "redis"] = "sqlite"
    redis_url: str | None = None
    storage_backend: Literal["local", "s3"] = "local"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: SecretStr | None = None
    cors_origins: str = "http://localhost:5180"

    @property
    def database_url(self) -> str:
        if self.database_url_env:
            return self.database_url_env
        return f"sqlite:///{(self.data_dir / 'studio.db').as_posix()}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
