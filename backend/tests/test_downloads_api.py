from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.db.models import ImageRow, OutputRow
from app.db.session import get_sessionmaker
from app.main import create_app
from app.storage import get_storage


def _zip_entries(response_content: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(response_content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _seed_outputs(batch_id: str) -> None:
    storage = get_storage()
    with get_sessionmaker()() as session:
        images = [
            ImageRow(
                batch_id=batch_id,
                source="web",
                original_path=f"batches/{batch_id}/originals/{index}.png",
                product_name=f"Producto {index}",
                sku="SKU/único" if index < 2 else None,
                status="approved" if index < 2 else "done",
                position=index,
            )
            for index in range(3)
        ]
        session.add_all(images)
        session.flush()
        for index, image in enumerate(images):
            old_key = f"batches/{batch_id}/outputs/{image.id}/v1/old.webp"
            current_key = f"batches/{batch_id}/outputs/{image.id}/v2/current.webp"
            feed_key = f"batches/{batch_id}/outputs/{image.id}/v2/feed.jpg"
            storage.save_bytes(old_key, b"old")
            storage.save_bytes(current_key, f"webp-{index}".encode())
            storage.save_bytes(feed_key, f"jpg-{index}".encode())
            session.add_all(
                [
                    OutputRow(
                        image_id=image.id,
                        preset="storefront",
                        variant="keep",
                        path=old_key,
                        width=10,
                        height=10,
                        bytes=3,
                        version=1,
                    ),
                    OutputRow(
                        image_id=image.id,
                        preset="storefront",
                        variant="keep",
                        path=current_key,
                        width=20,
                        height=20,
                        bytes=6,
                        version=2,
                    ),
                    OutputRow(
                        image_id=image.id,
                        preset="instagram_feed",
                        variant="keep",
                        path=feed_key,
                        width=10,
                        height=12,
                        bytes=5,
                        version=2,
                    ),
                ]
            )
        session.commit()


def test_download_defaults_to_approved_latest_outputs_and_unique_sku_names() -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Lote dragón"}).json()["id"]
        _seed_outputs(batch_id)

        response = client.get(f"/api/v1/batches/{batch_id}/download/storefront.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="Lote_dragon-storefront.zip"' in response.headers["content-disposition"]
    assert int(response.headers["content-length"]) == len(response.content)
    assert _zip_entries(response.content) == {
        "SKU_unico.webp": b"webp-0",
        "SKU_unico_2.webp": b"webp-1",
    }


def test_download_can_include_all_images_and_uses_preset_extension() -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Todos"}).json()["id"]
        _seed_outputs(batch_id)

        response = client.get(
            f"/api/v1/batches/{batch_id}/download/instagram_feed.zip",
            params={"approved_only": "false"},
        )

    assert response.status_code == 200
    assert _zip_entries(response.content) == {
        "SKU_unico.jpg": b"jpg-0",
        "SKU_unico_2.jpg": b"jpg-1",
        "Producto_2.jpg": b"jpg-2",
    }


def test_download_reports_missing_batch_empty_selection_and_missing_file() -> None:
    with TestClient(create_app()) as client:
        missing = client.get("/api/v1/batches/missing/download/storefront.zip")
        batch_id = client.post("/api/v1/batches", json={"name": "Vacío"}).json()["id"]
        empty = client.get(f"/api/v1/batches/{batch_id}/download/storefront.zip")

        with get_sessionmaker()() as session:
            image = ImageRow(
                batch_id=batch_id,
                source="web",
                original_path="originals/missing.png",
                status="approved",
            )
            session.add(image)
            session.flush()
            session.add(
                OutputRow(
                    image_id=image.id,
                    preset="storefront",
                    variant="keep",
                    path="outputs/missing.webp",
                    width=10,
                    height=10,
                    bytes=1,
                )
            )
            session.commit()
        stale = client.get(f"/api/v1/batches/{batch_id}/download/storefront.zip")

    assert missing.status_code == 404
    assert empty.status_code == 404
    assert stale.status_code == 409


def test_download_rejects_unknown_preset() -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Preset"}).json()["id"]
        response = client.get(f"/api/v1/batches/{batch_id}/download/unknown.zip")

    assert response.status_code == 422
