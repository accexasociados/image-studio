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
from app.importers.direct_url import DownloadedImage
from app.main import create_app
from app.queue import get_job_queue
from app.queue import worker as worker_module
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
        background: object = None,
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
        background: object = None,
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
        background: object = None,
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


def test_worker_import_failure_marks_batch_failed_and_publishes_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Import failure"}).json()["id"]
    with get_sessionmaker()() as session:
        batch = session.get(BatchRow, batch_id)
        assert batch is not None
        batch.status = "queued"
        session.commit()
    job = get_job_queue().enqueue(
        "import", batch_id=batch_id, payload={"url": "https://example.com/image.png"}
    )

    monkeypatch.setattr(
        worker_module,
        "download_image",
        lambda _url, **_kwargs: (_ for _ in ()).throw(RuntimeError("download failed")),
    )
    events = get_event_store()

    assert _worker(PipelineProcessor(), publisher=events).run_once() is True

    with get_sessionmaker()() as session:
        batch = session.get(BatchRow, batch_id)
        row = session.get(JobRow, job.id)
    assert batch is not None and batch.status == "failed"
    assert row is not None and row.status == "failed"
    finished = [event for event in events.read_after(0) if event.event.type == "batch.finished"]
    assert finished and finished[-1].event.payload["batch_id"] == batch_id
    assert finished[-1].event.payload["status"] == "failed"


def test_worker_import_persists_image_and_completes_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Import success"}).json()["id"]
    job = get_job_queue().enqueue(
        "import", batch_id=batch_id, payload={"url": "https://example.com/image.png"}
    )
    monkeypatch.setattr(
        worker_module,
        "download_image",
        lambda _url, **_kwargs: DownloadedImage(
            data=_image_bytes(), filename="image.png", media_type="image/png"
        ),
    )

    assert _worker(PipelineProcessor(), publisher=get_event_store()).run_once() is True

    with get_sessionmaker()() as session:
        images = session.query(ImageRow).filter_by(batch_id=batch_id).all()
        row = session.get(JobRow, job.id)
    assert len(images) == 1
    assert row is not None and row.status == "done"


def test_worker_import_failure_cleans_saved_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Import cleanup"}).json()["id"]
    job = get_job_queue().enqueue(
        "import", batch_id=batch_id, payload={"url": "https://photos.google.com/share/test"}
    )

    def broken_album(_url: str, **_kwargs: object) -> Iterator[DownloadedImage]:
        yield DownloadedImage(data=_image_bytes(), filename="first.png", media_type="image/png")
        raise RuntimeError("second image failed")

    monkeypatch.setattr(worker_module, "download_album", broken_album)
    assert _worker(PipelineProcessor()).run_once() is True

    with get_sessionmaker()() as session:
        images = session.query(ImageRow).filter_by(batch_id=batch_id).all()
        row = session.get(JobRow, job.id)
    assert images == []
    assert row is not None and row.status == "failed"
    root = get_storage().local_path(f"batches/{batch_id}")
    assert not root.exists() or not any(path.is_file() for path in root.rglob("*"))


def test_cancelled_batch_job_is_terminal_and_never_requeued(
    queued_image: tuple[str, str, str],
) -> None:
    batch_id, _image_id, job_id = queued_image
    with get_sessionmaker()() as session:
        batch = session.get(BatchRow, batch_id)
        assert batch is not None
        batch.status = "cancelled"
        session.commit()

    assert _worker(PipelineProcessor()).run_once() is True
    with get_sessionmaker()() as session:
        job = session.get(JobRow, job_id)
        assert job is not None
        assert job.status == "cancelled"


def test_cancellation_during_processing_stays_cancelled(
    queued_image: tuple[str, str, str],
) -> None:
    batch_id, image_id, job_id = queued_image

    def processor(
        input_path: Path,
        options: ProcessOptions,
        out_dir: Path,
        *,
        base_name: str,
        mask_override: Path | None,
        background: object = None,
        settings: AppSettings,
    ) -> ProcessResult:
        del input_path, options, mask_override, settings
        with get_sessionmaker()() as session:
            batch = session.get(BatchRow, batch_id)
            assert batch is not None
            batch.status = "cancelled"
            session.commit()
        return _successful_result(out_dir, base_name)

    assert _worker(processor).run_once() is True
    with get_sessionmaker()() as session:
        batch = session.get(BatchRow, batch_id)
        image = session.get(ImageRow, image_id)
        job = session.get(JobRow, job_id)
    assert batch is not None and batch.status == "cancelled"
    assert image is not None and image.status == "pending"
    assert job is not None and job.status == "cancelled"


def test_worker_album_import_keeps_photo_order(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Album order"}).json()["id"]
    get_job_queue().enqueue("import", batch_id=batch_id, payload={"url": "https://photos.app.goo.gl/abc"})

    def album(_url: str, **_kwargs: object) -> Iterator[DownloadedImage]:
        for name in ("a.png", "b.png", "c.png"):
            yield DownloadedImage(data=_image_bytes(), filename=name, media_type="image/png")

    monkeypatch.setattr(worker_module, "download_album", album)
    assert _worker(PipelineProcessor()).run_once() is True

    with get_sessionmaker()() as session:
        images = session.query(ImageRow).filter_by(batch_id=batch_id).order_by(ImageRow.position).all()
    order = [(image.source_ref, image.position) for image in images]
    assert order == [("a.png", 0), ("b.png", 1), ("c.png", 2)]
