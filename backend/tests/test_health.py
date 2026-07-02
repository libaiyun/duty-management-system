from fastapi.testclient import TestClient

from app.core.metadata import APP_VERSION, SERVICE_NAME
from app.main import create_app
from app.services.health import get_health_status


def test_health_service_returns_expected_status() -> None:
    status = get_health_status()

    assert status.status == "ok"
    assert status.service == SERVICE_NAME
    assert status.version == APP_VERSION


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": "OK",
        "message": "success",
        "data": {
            "status": "ok",
            "service": SERVICE_NAME,
            "version": APP_VERSION,
        },
    }
