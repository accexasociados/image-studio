from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.options import LayerLines, Preset, ProcessOptions

BatchStatus = Literal["draft", "queued", "processing", "done", "failed", "cancelled"]
ImageSource = Literal["upload", "google_photos", "google_drive", "url", "telegram", "hot_folder"]
ImageStatus = Literal["pending", "processing", "done", "review", "failed", "approved"]
JobKind = Literal["process", "reprocess", "import"]
JobStatus = Literal["queued", "running", "done", "failed", "cancelled"]
EventType = Literal["batch.progress", "image.updated", "batch.finished", "import.progress"]


class _ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BatchCounts(BaseModel):
    total: int = 0
    done: int = 0
    review: int = 0
    failed: int = 0


class OutputFile(_ReadModel):
    preset: Preset
    path: str
    width: int
    height: int
    bytes: int
    variant: LayerLines = "keep"


class Batch(_ReadModel):
    id: str
    name: str
    status: BatchStatus
    default_options: ProcessOptions
    created_at: datetime
    finished_at: datetime | None = None
    counts: BatchCounts = Field(default_factory=BatchCounts)


class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    default_options: ProcessOptions = Field(default_factory=ProcessOptions)


class ImageItem(_ReadModel):
    id: str
    batch_id: str
    source: ImageSource
    source_ref: str | None = None
    original_path: str
    product_name: str | None = None
    sku: str | None = None
    options_override: ProcessOptions | None = None
    status: ImageStatus
    review_reasons: list[str] = Field(default_factory=list)
    outputs: list[OutputFile] = Field(default_factory=list)
    error: str | None = None
    mask_path: str | None = None


class ImageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: str | None = Field(default=None, max_length=200)
    sku: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    options_override: ProcessOptions | None = None


class Job(_ReadModel):
    id: str
    image_id: str | None = None
    batch_id: str | None = None
    kind: JobKind
    status: JobStatus
    attempts: int = 0
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Event(BaseModel):
    """Mensaje del canal SSE /api/v1/events."""

    type: EventType
    payload: dict[str, Any]


class ProcessResult(BaseModel):
    """Lo que devuelve pipeline.run.process_image."""

    outputs: list[OutputFile]
    mask_path: str | None = None
    review_reasons: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)


class GpuInfo(BaseModel):
    available: bool
    name: str | None = None
    vram_mb: int | None = None


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    pipeline_mode: Literal["real", "stub"]
    device: Literal["cuda", "cpu"]
    gpu: GpuInfo
