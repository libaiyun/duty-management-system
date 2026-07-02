from app.core.metadata import APP_VERSION, SERVICE_NAME
from app.services.health import get_health_status


def test_health_service_returns_expected_status() -> None:
    status = get_health_status()

    assert status.status == "ok"
    assert status.service == SERVICE_NAME
    assert status.version == APP_VERSION


def test_health_endpoint_returns_ok(api_client) -> None:
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "code": "OK",
        "message": "success",
        "data": {
            "status": "ok",
            "service": SERVICE_NAME,
            "version": APP_VERSION,
        },
        "trace_id": body["trace_id"],
    }
    assert body["trace_id"]
