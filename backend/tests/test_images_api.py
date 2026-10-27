from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select

from app.db.models import ImageRow, JobRow
from app.db.session import get_sessionmaker
from app.main import create_app
from app.storage import get_storage


def _image_bytes(format_name: str = "PNG", color: str = "red") -> bytes:
    stream = BytesIO()
    Image.new("RGB", (20, 10), color).save(stream, format=format_name)
    return stream.getvalue()


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return stream.getvalue()


def _create_batch(client: TestClient) -> str:
    response = client.post("/api/v1/batches", json={"name": "Lote de prueba"})
    assert response.status_code == 201
    return str(response.json()["id"])


def test_upload_images_stores_content_enqueues_jobs_and_lists_them() -> None:
    with TestClient(create_app()) as client:
        batch_id = _create_batch(client)
        response = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files=[
                ("files", ("dragon.jpg", _image_bytes("JPEG"), "image/jpeg")),
                ("files", ("pieza.png", _image_bytes("PNG", "blue"), "image/png")),
            ],
        )
        listed = client.get(f"/api/v1/batches/{batch_id}/images")
        batch = client.get(f"/api/v1/batches/{batch_id}")

        with get_sessionmaker()() as session:
            job_count = session.scalar(
                select(func.count()).select_from(JobRow).where(JobRow.batch_id == batch_id)
            )

    assert response.status_code == 201
    uploaded = response.json()
    assert [image["source_ref"] for image in uploaded] == ["dragon.jpg", "pieza.png"]
    assert uploaded[0]["original_path"].endswith(".jpg")
    assert uploaded[1]["original_path"].endswith(".png")
    assert all(get_storage().exists(image["original_path"]) for image in uploaded)
    assert listed.status_code == 200
    assert [image["id"] for image in listed.json()] == [image["id"] for image in uploaded]
    assert batch.json()["status"] == "queued"
    assert batch.json()["counts"]["total"] == 2
    assert job_count == 2


def test_upload_zip_uses_real_image_format_and_ignores_metadata() -> None:
    archive = _zip_bytes(
        {
            "carpeta/uno.dat": _image_bytes("WEBP"),
            "dos.jpeg": _image_bytes("JPEG"),
            "__MACOSX/._dos.jpeg": b"metadata",
            ".DS_Store": b"metadata",
        }
    )
    with TestClient(create_app()) as client:
        batch_id = _create_batch(client)
        response = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("fotos.zip", archive, "application/zip")},
        )

    assert response.status_code == 201
    uploaded = response.json()
    assert [image["source_ref"] for image in uploaded] == ["uno.dat", "dos.jpeg"]
    assert uploaded[0]["original_path"].endswith(".webp")
    assert uploaded[1]["original_path"].endswith(".jpg")


def test_invalid_file_rolls_back_database_and_saved_files() -> None:
    with TestClient(create_app()) as client:
        batch_id = _create_batch(client)
        response = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files=[
                ("files", ("valida.png", _image_bytes(), "image/png")),
                ("files", ("falsa.png", b"no es una imagen", "image/png")),
            ],
        )
        listed = client.get(f"/api/v1/batches/{batch_id}/images")

    assert response.status_code == 415
    assert listed.json() == []
    storage_root = get_storage().local_path(f"batches/{batch_id}/originals")
    assert not storage_root.exists() or not any(storage_root.iterdir())


def test_zip_with_more_than_200_images_is_rejected_atomically() -> None:
    image = _image_bytes()
    archive = _zip_bytes({f"{index}.png": image for index in range(201)})
    with TestClient(create_app()) as client:
        batch_id = _create_batch(client)
        response = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("demasiadas.zip", archive, "application/zip")},
        )
        listed = client.get(f"/api/v1/batches/{batch_id}/images")

    assert response.status_code == 413
    assert listed.json() == []


def test_update_image_supports_partial_changes_and_explicit_null() -> None:
    with TestClient(create_app()) as client:
        batch_id = _create_batch(client)
        uploaded = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("pieza.png", _image_bytes(), "image/png")},
        ).json()[0]
        image_id = uploaded["id"]

        named = client.patch(
            f"/api/v1/images/{image_id}",
            json={"product_name": "Dragón", "sku": "DRG-01"},
        )
        overridden = client.patch(
            f"/api/v1/images/{image_id}",
            json={"options_override": {"presets": ["instagram_square"], "shadow": "soft"}},
        )
        cleared = client.patch(f"/api/v1/images/{image_id}", json={"sku": None})

    assert named.status_code == 200
    assert named.json()["product_name"] == "Dragón"
    assert named.json()["sku"] == "DRG-01"
    assert overridden.json()["options_override"]["presets"] == ["instagram_square"]
    assert cleared.json()["sku"] is None
    assert cleared.json()["product_name"] == "Dragón"


def test_approve_requires_a_processed_image_and_is_idempotent() -> None:
    with TestClient(create_app()) as client:
        batch_id = _create_batch(client)
        image_id = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("pieza.png", _image_bytes(), "image/png")},
        ).json()[0]["id"]

        pending = client.post(f"/api/v1/images/{image_id}/approve")
        with get_sessionmaker()() as session:
            row = session.get(ImageRow, image_id)
            assert row is not None
            row.status = "review"
            session.commit()
        approved = client.post(f"/api/v1/images/{image_id}/approve")
        repeated = client.post(f"/api/v1/images/{image_id}/approve")

    assert pending.status_code == 409
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "approved"
