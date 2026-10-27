from fastapi.testclient import TestClient

from app.main import create_app


def test_import_url_enqueues_import_job() -> None:
    with TestClient(create_app()) as client:
        batch = client.post("/api/v1/batches", json={"name": "Enlaces"}).json()
        response = client.post(
            f"/api/v1/batches/{batch['id']}/imports",
            json={"url": "https://example.com/photo.jpg"},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "queued"
