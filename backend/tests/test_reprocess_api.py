from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.db.models import ImageRow, JobRow, OutputRow
from app.db.session import get_sessionmaker
from app.main import create_app
from app.queue import get_job_queue
from app.queue.worker import PipelineProcessor, Worker
from app.storage import get_storage


def _png_bytes(size: tuple[int, int] = (20, 10), mode: str = "RGB") -> bytes:
    stream = BytesIO()
    color: str | int = "red" if mode == "RGB" else 255
    Image.new(mode, size, color).save(stream, format="PNG")
    return stream.getvalue()


def _worker() -> Worker:
    return Worker(
        worker_id="reprocess-test",
        queue=get_job_queue(),
        storage=get_storage(),
        processor=PipelineProcessor(),
        release_memory=lambda: None,
    )


def _processed_image(client: TestClient) -> tuple[str, str]:
    batch_id = client.post("/api/v1/batches", json={"name": "Reproceso"}).json()["id"]
    image_id = client.post(
        f"/api/v1/batches/{batch_id}/images",
        files={"files": ("pieza.png", _png_bytes(), "image/png")},
    ).json()[0]["id"]
    assert _worker().run_once() is True
    return batch_id, image_id


def test_reprocess_with_new_options_preserves_previous_versions() -> None:
    with TestClient(create_app()) as client:
        _batch_id, image_id = _processed_image(client)
        response = client.post(
            f"/api/v1/images/{image_id}/reprocess",
            json={"presets": ["instagram_square"], "shadow": "soft"},
        )
        assert _worker().run_once() is True
        final = client.get(f"/api/v1/images/{image_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["options_override"]["presets"] == ["instagram_square"]
    assert final.json()["status"] == "done"
    with get_sessionmaker()() as session:
        outputs = session.scalars(
            select(OutputRow).where(OutputRow.image_id == image_id).order_by(OutputRow.version)
        ).all()
        jobs = session.scalars(select(JobRow).where(JobRow.image_id == image_id)).all()
    assert [output.version for output in outputs] == [1, 1, 2]
    assert [job.kind for job in jobs] == ["process", "reprocess"]


def test_mask_is_normalized_stored_and_used_for_reprocessing() -> None:
    with TestClient(create_app()) as client:
        _batch_id, image_id = _processed_image(client)
        response = client.put(
            f"/api/v1/images/{image_id}/mask",
            files={"file": ("mask.png", _png_bytes(mode="L"), "image/png")},
        )
        mask_key = response.json()["mask_path"]
        assert _worker().run_once() is True
        final = client.get(f"/api/v1/images/{image_id}").json()

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert mask_key.endswith(".png")
    assert get_storage().exists(mask_key)
    with Image.open(get_storage().local_path(mask_key)) as mask:
        assert mask.mode == "L"
        assert mask.size == (20, 10)
    assert final["status"] == "done"
    assert final["mask_path"] == mask_key


def test_invalid_mask_dimensions_do_not_enqueue_reprocess() -> None:
    with TestClient(create_app()) as client:
        _batch_id, image_id = _processed_image(client)
        response = client.put(
            f"/api/v1/images/{image_id}/mask",
            files={"file": ("mask.png", _png_bytes((5, 5), "L"), "image/png")},
        )

    assert response.status_code == 422
    with get_sessionmaker()() as session:
        image = session.get(ImageRow, image_id)
        jobs = session.scalars(select(JobRow).where(JobRow.image_id == image_id)).all()
    assert image is not None and image.status == "done" and image.mask_path is None
    assert [job.kind for job in jobs] == ["process"]


def test_pending_image_cannot_be_reprocessed() -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Pendiente"}).json()["id"]
        image_id = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("pieza.png", _png_bytes(), "image/png")},
        ).json()[0]["id"]
        response = client.post(f"/api/v1/images/{image_id}/reprocess")

    assert response.status_code == 409
