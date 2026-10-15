from fastapi import APIRouter, status
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Check the operational health and readiness of the AI Data Analyst backend service.",
)
async def get_health() -> HealthResponse:
    """Retrieve system health status."""
    return HealthService.get_health_status()
