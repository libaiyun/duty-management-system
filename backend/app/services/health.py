from app.core.metadata import APP_VERSION, SERVICE_NAME
from app.schemas.health import HealthResponse


def get_health_status() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=APP_VERSION,
    )
