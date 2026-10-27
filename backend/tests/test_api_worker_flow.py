from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.queue import get_job_queue
from app.queue.worker import PipelineProcessor, Worker
from app.storage import get_storage


def _source_image() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (24, 16), "#c24b31").save(stream, format="PNG")
    return stream.getvalue()


def test_upload_worker_approval_and_download_flow() -> None:
    """Recorre el camino principal usando HTTP, BD temporal, cola SQLite y pipeline stub."""
    with TestClient(create_app()) as client:
        batch = client.post("/api/v1/batches", json={"name": "Flujo integral"})
        assert batch.status_code == 201
        batch_id = batch.json()["id"]

        uploaded = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("pieza.png", _source_image(), "image/png")},
        )
        assert uploaded.status_code == 201
        image_id = uploaded.json()[0]["id"]
        metadata = client.patch(f"/api/v1/images/{image_id}", json={"sku": "PIEZA-001"})
        assert metadata.status_code == 200

        worker = Worker(
            worker_id="integration-test",
            queue=get_job_queue(),
            storage=get_storage(),
            processor=PipelineProcessor(),
            release_memory=lambda: None,
        )
        assert worker.run_once() is True
        assert worker.run_once() is False

        processed = client.get(f"/api/v1/images/{image_id}")
        assert processed.status_code == 200
        assert processed.json()["status"] == "done"
        assert {output["preset"] for output in processed.json()["outputs"]} == {
            "storefront",
            "instagram_feed",
        }

        approved = client.post(f"/api/v1/images/{image_id}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        downloaded = client.get(f"/api/v1/batches/{batch_id}/download/storefront.zip")

    assert downloaded.status_code == 200
    with ZipFile(BytesIO(downloaded.content)) as archive:
        assert archive.namelist() == ["PIEZA-001.webp"]
        with Image.open(BytesIO(archive.read("PIEZA-001.webp"))) as result:
            assert result.size == (2000, 2000)
            assert result.format == "WEBP"
