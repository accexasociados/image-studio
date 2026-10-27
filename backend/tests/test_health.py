from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_mode_and_runs_migrations() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["pipeline_mode"] == "stub"
    assert set(body["gpu"]) == {"available", "name", "vram_mb"}


def test_openapi_exposes_contracts() -> None:
    with TestClient(create_app()) as client:
        schema = client.get("/api/v1/openapi.json").json()
    assert "Health" in schema["components"]["schemas"]
