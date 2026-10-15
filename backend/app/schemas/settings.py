"""Pydantic schemas for System Settings and User Preferences."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class UserPreferencesResponse(BaseModel):
    """User-specific interface preferences and notification settings."""
    email_notifications: bool = False
    anomaly_alert_notifications: bool = False
    report_ready_notifications: bool = True
    cleaning_complete_notifications: bool = True
    theme: str = "light"
    default_anomaly_method: str = "both"
    default_iqr_multiplier: float = 1.5


class UserPreferencesUpdateRequest(BaseModel):
    """Payload to update user preferences."""
    email_notifications: Optional[bool] = None
    anomaly_alert_notifications: Optional[bool] = None
    report_ready_notifications: Optional[bool] = None
    cleaning_complete_notifications: Optional[bool] = None
    theme: Optional[str] = None
    default_anomaly_method: Optional[str] = None
    default_iqr_multiplier: Optional[float] = Field(None, ge=0.5, le=5.0)


class SystemSettingsResponse(BaseModel):
    """System-wide configuration viewable by users with sensitive data masked."""
    max_upload_size_mb: int = 50
    max_user_storage_mb: int = 500
    gemini_api_key_configured: bool = False
    gemini_api_key_masked: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    smtp_configured: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_from_email: str = ""
    smtp_tls: bool = True
    app_name: str = "AI Data Analyst Agent"
    app_env: str = "development"


class SystemSettingsUpdateRequest(BaseModel):
    """Admin payload to update system-wide settings."""
    max_upload_size_mb: Optional[int] = Field(None, ge=1, le=1024, description="Max upload size per dataset file (1-1024 MB)")
    max_user_storage_mb: Optional[int] = Field(None, ge=1, le=10240, description="Max total workspace storage per user (1-10240 MB)")
    gemini_api_key: Optional[str] = Field(None, description="Optional new Gemini API Key. If empty or None, keeps current key.")
    gemini_model: Optional[str] = Field(None, description="Default Gemini model identifier")


class WorkspaceStorageResponse(BaseModel):
    """User workspace storage metrics and quota consumption."""
    user_id: int
    used_storage_bytes: int
    used_storage_mb: float
    storage_quota_mb: float
    used_percentage: float
    dataset_count: int
    max_upload_size_mb: int
    quota_warning: bool = False


class SettingsOverviewResponse(BaseModel):
    """Aggregated settings payload returned to the settings page."""
    user_id: int
    username: str
    role: str
    is_admin: bool
    user_preferences: UserPreferencesResponse
    system_settings: SystemSettingsResponse
    workspace_storage: WorkspaceStorageResponse
    available_providers: List[Dict[str, Any]]
    notification_channels: List[Dict[str, Any]]


class TestGeminiKeyRequest(BaseModel):
    """Request to test Gemini API key connectivity."""
    api_key: Optional[str] = None  # If None, tests current active key


class TestGeminiKeyResponse(BaseModel):
    """Result of Gemini API key validation."""
    success: bool
    status: str
    message: str
    model: str


class TestNotificationResponse(BaseModel):
    """Result of notification channel test."""
    channel: str
    configured: bool
    status: str
    message: str
