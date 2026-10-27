from collections.abc import Callable, Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.contracts import AppSettings, OutputFile, ProcessOptions, ProcessResult
from app.db.models import BatchRow, ImageRow, JobRow, OutputRow
from app.db.session import get_sessionmaker
from app.events import EventPublisher, get_event_store
from app.main import create_app
from app.queue import get_job_queue
from app.queue.worker import ImageProcessor, PipelineProcessor, Worker
from app.storage import get_storage


def _image_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (20, 10), "red").save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def queued_image() -> Iterator[tuple[str, str, str]]:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Worker"}).json()["id"]
        image_id = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("Dragón rojo.png", _image_bytes(), "image/png")},
        ).json()[0]["id"]
        with get_sessionmaker()() as session:
            job = session.query(JobRow).filter_by(image_id=image_id).one()
            job_id = job.id
        yield batch_id, image_id, job_id


def _worker(
    processor: ImageProcessor,
    *,
    release_memory: Callable[[], None] = lambda: None,
    publisher: EventPublisher | None = None,
) -> Worker:
    return Worker(
        worker_id="test-worker",
        queue=get_job_queue(),
        storage=get_storage(),
        processor=processor,
        release_memory=release_memory,
        publisher=publisher,
    )


def _successful_result(out_dir: Path, base_name: str) -> ProcessResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{base_name}.webp"
    path.write_bytes(b"resultado")
    return ProcessResult(
        outputs=[
            OutputFile(
                preset="storefront",
                path=str(path),
                width=20,
                height=20,
                bytes=path.stat().st_size,
            )
        ]
    )


def test_worker_processes_stub_and_persists_relative_outputs(
    queued_image: tuple[str, str, str],
) -> None:
    batch_id, image_id, job_id = queued_image
    worker = _worker(PipelineProcessor())

    assert worker.run_once() is True
    assert worker.run_once() is False

    with get_sessionmaker()() as session:
        image = session.get(ImageRow, image_id)
        batch = session.get(BatchRow, batch_id)
        job = session.get(JobRow, job_id)
        outputs = session.query(OutputRow).filter_by(image_id=image_id).all()
    assert image is not None and image.status == "done"
    assert batch is not None and batch.status == "done" and batch.finished_at is not None
    assert job is not None and job.status == "done"
    assert len(outputs) == 2
    assert all(not Path(output.path).is_absolute() for output in outputs)
    assert all(get_storage().exists(output.path) for output in outputs)


class _OomOnceProcessor:
    def __init__(self) -> None:
        self.tile_sizes: list[int] = []

    def __call__(
        self,
        input_path: Path,
        options: ProcessOptions,
        out_dir: Path,
        *,
        base_name: str,
        mask_override: Path | None,
        settings: AppSettings,
    ) -> ProcessResult:
        del input_path, options, mask_override
        self.tile_sizes.append(settings.pipeline.tile_size)
        if len(self.tile_sizes) == 1:
            raise RuntimeError("CUDA out of memory")
        return _successful_result(out_dir, base_name)


def test_worker_releases_vram_and_retries_with_smaller_tiles(
    queued_image: tuple[str, str, str],
) -> None:
    _batch_id, image_id, job_id = queued_image
    processor = _OomOnceProcessor()
    releases: list[bool] = []

    assert _worker(processor, release_memory=lambda: releases.append(True)).run_once() is True

    assert processor.tile_sizes == [512, 256]
    assert releases == [True]
    with get_sessionmaker()() as session:
        image = session.get(ImageRow, image_id)
        job = session.get(JobRow, job_id)
    assert image is not None and image.status == "done"
    assert job is not None and job.status == "done" and job.attempts == 1


class _FailingProcessor:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self,
        input_path: Path,
        options: ProcessOptions,
        out_dir: Path,
        *,
        base_name: str,
        mask_override: Path | None,
        settings: AppSettings,
    ) -> ProcessResult:
        del input_path, options, out_dir, base_name, mask_override, settings
        self.calls += 1
        raise RuntimeError("fallo del proceso")


def test_worker_retries_twice_then_marks_image_failed(
    queued_image: tuple[str, str, str],
) -> None:
    batch_id, image_id, job_id = queued_image
    processor = _FailingProcessor()
    worker = _worker(processor)

    for _attempt in range(3):
        assert worker.run_once() is True

    with get_sessionmaker()() as session:
        image = session.get(ImageRow, image_id)
        batch = session.get(BatchRow, batch_id)
        job = session.get(JobRow, job_id)
    assert processor.calls == 3
    assert image is not None and image.status == "failed" and image.error == "fallo del proceso"
    assert batch is not None and batch.status == "failed" and batch.finished_at is not None
    assert job is not None and job.status == "failed" and job.attempts == 3


def test_worker_marks_review_results(queued_image: tuple[str, str, str]) -> None:
    _batch_id, image_id, _job_id = queued_image

    def processor(
        input_path: Path,
        options: ProcessOptions,
        out_dir: Path,
        *,
        base_name: str,
        mask_override: Path | None,
        settings: AppSettings,
    ) -> ProcessResult:
        del input_path, options, mask_override, settings
        result = _successful_result(out_dir, base_name)
        return result.model_copy(update={"review_reasons": ["touching_border"]})

    assert _worker(processor).run_once() is True

    with get_sessionmaker()() as session:
        image = session.get(ImageRow, image_id)
    assert image is not None
    assert image.status == "review"
    assert image.review_reasons == ["touching_border"]


def test_worker_publishes_progress_and_completion_events(
    queued_image: tuple[str, str, str],
) -> None:
    _batch_id, _image_id, _job_id = queued_image
    store = get_event_store()

    assert _worker(PipelineProcessor(), publisher=store).run_once() is True

    events = store.read_after(0)
    assert [stored.event.type for stored in events] == [
        "image.updated",
        "batch.progress",
        "image.updated",
        "batch.progress",
        "batch.finished",
    ]
    assert events[0].event.payload["status"] == "processing"
    assert events[-1].event.payload["status"] == "done"
