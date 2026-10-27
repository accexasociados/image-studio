from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import BatchRow, ImageRow, JobRow
from app.db.session import get_sessionmaker
from app.main import create_app


def _create_batch(client: TestClient, name: str = "Dragones") -> dict[str, object]:
    response = client.post("/api/v1/batches", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_create_list_get_and_replace_default_options() -> None:
    with TestClient(create_app()) as client:
        created = _create_batch(client)
        batch_id = str(created["id"])

        assert created["status"] == "draft"
        assert created["counts"] == {"total": 0, "done": 0, "review": 0, "failed": 0}

        listed = client.get("/api/v1/batches")
        fetched = client.get(f"/api/v1/batches/{batch_id}")
        updated = client.put(
            f"/api/v1/batches/{batch_id}/default-options",
            json={"presets": ["storefront"], "layer_lines": "smooth", "smooth_strength": 20},
        )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [batch_id]
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Dragones"
    assert updated.status_code == 200
    assert updated.json()["default_options"]["presets"] == ["storefront"]
    assert updated.json()["default_options"]["layer_lines"] == "smooth"


def test_batch_counts_include_approved_images_as_done() -> None:
    with TestClient(create_app()) as client:
        batch_id = str(_create_batch(client)["id"])
        with get_sessionmaker()() as session:
            for position, image_status in enumerate(("done", "approved", "review", "failed", "pending")):
                session.add(
                    ImageRow(
                        batch_id=batch_id,
                        source="upload",
                        original_path=f"originals/{position}.png",
                        status=image_status,
                        position=position,
                    )
                )
            session.commit()

        response = client.get(f"/api/v1/batches/{batch_id}")

    assert response.status_code == 200
    assert response.json()["counts"] == {"total": 5, "done": 2, "review": 1, "failed": 1}


def test_cancel_batch_is_idempotent_and_cancels_queued_jobs() -> None:
    with TestClient(create_app()) as client:
        batch_id = str(_create_batch(client)["id"])
        with get_sessionmaker()() as session:
            session.add(JobRow(kind="import", status="queued", batch_id=batch_id))
            session.commit()

        first = client.post(f"/api/v1/batches/{batch_id}/cancel")
        second = client.post(f"/api/v1/batches/{batch_id}/cancel")

        with get_sessionmaker()() as session:
            job = session.scalar(select(JobRow).where(JobRow.batch_id == batch_id))

    assert first.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert first.json()["finished_at"] is not None
    assert second.status_code == 200
    assert job is not None
    assert job.status == "cancelled"
    assert job.finished_at is not None


def test_retry_failed_images_enqueues_new_jobs() -> None:
    with TestClient(create_app()) as client:
        batch_id = str(_create_batch(client)["id"])
        with get_sessionmaker()() as session:
            batch = session.get(BatchRow, batch_id)
            assert batch is not None
            batch.status = "failed"
            session.add_all(
                [
                    ImageRow(
                        batch_id=batch_id,
                        source="upload",
                        original_path="originals/failed.png",
                        status="failed",
                        error="falló",
                        review_reasons=["edge"],
                    ),
                    ImageRow(
                        batch_id=batch_id,
                        source="upload",
                        original_path="originals/done.png",
                        status="done",
                    ),
                ]
            )
            session.commit()

        response = client.post(f"/api/v1/batches/{batch_id}/retry-failed")

        with get_sessionmaker()() as session:
            images = session.scalars(
                select(ImageRow).where(ImageRow.batch_id == batch_id).order_by(ImageRow.original_path)
            ).all()
            jobs = session.scalars(select(JobRow).where(JobRow.batch_id == batch_id)).all()

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["counts"]["failed"] == 0
    failed_image = next(image for image in images if image.original_path.endswith("failed.png"))
    assert failed_image.status == "pending"
    assert failed_image.error is None
    assert failed_image.review_reasons == []
    assert len(jobs) == 1
    assert jobs[0].image_id == failed_image.id
    assert jobs[0].status == "queued"


def test_missing_batch_and_retry_without_failures_return_errors() -> None:
    with TestClient(create_app()) as client:
        missing = client.get("/api/v1/batches/does-not-exist")
        batch_id = str(_create_batch(client)["id"])
        no_failures = client.post(f"/api/v1/batches/{batch_id}/retry-failed")

    assert missing.status_code == 404
    assert no_failures.status_code == 409
