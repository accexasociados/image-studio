"""Contratos compartidos: fuente de verdad de la API y del proceso de imagen.
Cambiarlos exige una nota en "Registro de cambios de contrato" de PLAN_EJECUCION.md."""

from app.contracts.models import (
    Batch,
    BatchCounts,
    BatchCreate,
    BatchStatus,
    Event,
    EventType,
    GpuInfo,
    Health,
    ImageItem,
    ImageSource,
    ImageStatus,
    ImageUpdate,
    Job,
    JobKind,
    JobStatus,
    OutputFile,
    ProcessResult,
)
from app.contracts.options import LayerLines, Preset, ProcessOptions, ShadowMode, UpscaleFactor
from app.contracts.presets import PRESETS, OutputFormat, PresetSpec
from app.contracts.settings import (
    SECRET_FIELDS,
    AppSettings,
    AppSettingsPublic,
    SettingsSection,
    TelegramTestResult,
)

__all__ = [
    "PRESETS",
    "SECRET_FIELDS",
    "AppSettings",
    "AppSettingsPublic",
    "Batch",
    "BatchCounts",
    "BatchCreate",
    "BatchStatus",
    "Event",
    "EventType",
    "GpuInfo",
    "Health",
    "ImageItem",
    "ImageSource",
    "ImageStatus",
    "ImageUpdate",
    "Job",
    "JobKind",
    "JobStatus",
    "LayerLines",
    "OutputFile",
    "OutputFormat",
    "Preset",
    "PresetSpec",
    "ProcessOptions",
    "ProcessResult",
    "SettingsSection",
    "ShadowMode",
    "TelegramTestResult",
    "UpscaleFactor",
]
