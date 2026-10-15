from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    """Structured error details."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Any] = Field(default=None, description="Detailed validation or trace items")


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    status: str = Field(default="error", description="Indicates failed request status")
    error: ErrorDetail


class StandardResponse(BaseModel, Generic[DataT]):
    """Generic wrapper for structured API responses."""

    status: str = Field(default="ok", description="Status string")
    data: Optional[DataT] = Field(default=None, description="Payload data")
    message: Optional[str] = Field(default=None, description="Informational message")
