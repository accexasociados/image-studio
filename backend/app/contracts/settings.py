"""Configuración editable desde la web (tabla `settings`). Todo lo que no sea de arranque vive aquí.

Los campos `SecretStr` se guardan cifrados con SECRET_KEY y la API nunca los devuelve en claro:
solo informa si están configurados (ver `AppSettingsPublic`)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.contracts.options import Preset, ProcessOptions
from app.contracts.presets import OutputFormat

# Pesos en `app/pipeline/catalog.py`. Elegidos el 2026-10-27 comparando con 6 piezas reales (Fase 10).
UpscaleModel = Literal["realesrgan_x2plus", "nmkd_siax"]


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TelegramSettings(_Section):
    enabled: bool = False
    bot_token: SecretStr | None = None
    # Chats que pueden usar el bot como entrada y que reciben los avisos.
    allowed_chat_ids: list[int] = Field(default_factory=list)
    notify_chat_ids: list[int] = Field(default_factory=list)
    notify_on_start: bool = True
    notify_progress_step: int = Field(default=25, ge=0, le=100, description="0 = sin avisos de progreso.")
    notify_on_finish: bool = True
    input_bot_enabled: bool = False
    send_results_as: Literal["files", "zip"] = "zip"


class NotificationSettings(_Section):
    windows_toast: bool = True
    browser: bool = True


class PresetOverride(_Section):
    """Ajuste de un formato de salida; lo que quede en None usa el valor de PRESETS."""

    enabled: bool = True
    width: int | None = Field(default=None, ge=256, le=8000)
    height: int | None = Field(default=None, ge=256, le=8000)
    format: OutputFormat | None = None
    quality: int | None = Field(default=None, ge=50, le=100)
    fill_ratio: float | None = Field(default=None, ge=0.5, le=0.95)
    max_bytes: int | None = Field(default=None, ge=100_000)


class ExportSettings(_Section):
    presets: dict[Preset, PresetOverride] = Field(default_factory=dict)
    background_hex: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    filename_strategy: Literal["sku_then_slug", "slug", "original"] = "sku_then_slug"


class HotFolderSettings(_Section):
    enabled: bool = False
    inbox_dir: str | None = None
    outbox_dir: str | None = None
    poll_seconds: int = Field(default=5, ge=1, le=300)


class ImporterSettings(_Section):
    google_drive_api_key: SecretStr | None = None
    max_download_mb: int = Field(default=40, ge=1, le=500)
    max_images_per_import: int = Field(default=300, ge=1, le=2000)


class QualitySettings(_Section):
    min_object_area: float = Field(default=0.05, ge=0, le=1)
    max_object_area: float = Field(default=0.95, ge=0, le=1)
    flag_touching_border: bool = True
    flag_multiple_objects: bool = True
    # Calibrado el 2026-10-27 con 12 fotos reales: recortes correctos dan 0,27 a 0,51.
    low_confidence_edge_ratio: float = Field(default=0.6, ge=0, le=1)


class PipelineSettings(_Section):
    segmentation_model: Literal["birefnet", "rmbg2"] = "birefnet"
    segmentation_size: int = Field(default=1024, ge=512, le=2048)
    # "lanczos" agranda sin IA.
    upscale_model: UpscaleModel | Literal["lanczos"] = "nmkd_siax"
    tile_size: int = Field(default=512, ge=128, le=1024)
    tile_overlap: int = Field(default=32, ge=0, le=128)
    # La serie GTX 16xx produce NaN en FP16: mantener en False salvo GPU compatible.
    half_precision: bool = False
    # Con Siax, 0,5 da la nitidez más parecida a la real sin perder fidelidad (Fase 10).
    detail_reinjection: float = Field(default=0.5, ge=0, le=1)


class GeneralSettings(_Section):
    language: Literal["es", "en"] = "es"
    # URL con la que se arman los enlaces de los avisos (local o pública cuando esté en la nube).
    public_base_url: str = "http://localhost:5180"


class AppSettings(_Section):
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    processing_defaults: ProcessOptions = Field(default_factory=ProcessOptions)
    export: ExportSettings = Field(default_factory=ExportSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    hot_folder: HotFolderSettings = Field(default_factory=HotFolderSettings)
    importers: ImporterSettings = Field(default_factory=ImporterSettings)
    quality: QualitySettings = Field(default_factory=QualitySettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)


class SecretConfigured(_Section):
    configured: bool


class TelegramSettingsPublic(_Section):
    enabled: bool
    bot_token: SecretConfigured
    allowed_chat_ids: list[int]
    notify_chat_ids: list[int]
    notify_on_start: bool
    notify_progress_step: int
    notify_on_finish: bool
    input_bot_enabled: bool
    send_results_as: Literal["files", "zip"]


class ImporterSettingsPublic(_Section):
    google_drive_api_key: SecretConfigured
    max_download_mb: int
    max_images_per_import: int


class AppSettingsPublic(_Section):
    """Vista de API: conserva toda la configuración sin revelar secretos."""

    general: GeneralSettings
    processing_defaults: ProcessOptions
    export: ExportSettings
    telegram: TelegramSettingsPublic
    notifications: NotificationSettings
    hot_folder: HotFolderSettings
    importers: ImporterSettingsPublic
    quality: QualitySettings
    pipeline: PipelineSettings


class TelegramTestResult(_Section):
    ok: Literal[True] = True
    sent: int


class UpscaleModelInfo(_Section):
    """Opción del selector de Ajustes > Proceso > modelo de ampliación."""

    id: UpscaleModel
    scale: int
    size_mb: int
    license: str
    installed: bool


SettingsSection = Literal[
    "general",
    "processing_defaults",
    "export",
    "telegram",
    "notifications",
    "hot_folder",
    "importers",
    "quality",
    "pipeline",
]

# Rutas "seccion.campo" de los secretos: se cifran en la BD y se enmascaran en la API.
SECRET_FIELDS: tuple[tuple[SettingsSection, str], ...] = (
    ("telegram", "bot_token"),
    ("importers", "google_drive_api_key"),
)
