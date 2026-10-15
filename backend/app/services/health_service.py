from app.core.config import settings
from app.schemas.health import HealthResponse


class HealthService:
    """Service handling system status and health checks."""

    @staticmethod
    def get_health_status() -> HealthResponse:
        """Return the current service health status."""
        return HealthResponse(
            status="ok",
            service=settings.APP_NAME,
        )
