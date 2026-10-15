from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Schema for health-check endpoint response."""

    status: str = Field(..., description="Service status", examples=["ok"])
    service: str = Field(..., description="Service name", examples=["AI Data Analyst Agent"])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "AI Data Analyst Agent",
            }
        }
    )
