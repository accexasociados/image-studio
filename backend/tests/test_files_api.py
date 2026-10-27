from fastapi.testclient import TestClient

from app.main import create_app


def test_file_traversal_is_not_an_internal_error() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/files/%2E%2E%2Foutside.png")

    assert response.status_code == 404
