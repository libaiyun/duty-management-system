from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.schemas.response import ApiResponse, ok
from app.services.health import get_health_status

router = APIRouter()


@router.get("/health", response_model=ApiResponse[HealthResponse])
def health_check() -> ApiResponse[HealthResponse]:
    return ok(get_health_status())
