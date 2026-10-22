"""Settings Router - Application configuration, user preferences, API key management, and quotas."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.schemas.settings import (
    SettingsOverviewResponse,
    UserPreferencesResponse,
    UserPreferencesUpdateRequest,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
    WorkspaceStorageResponse,
    TestGeminiKeyRequest,
    TestGeminiKeyResponse,
    TestNotificationResponse,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=SettingsOverviewResponse)
@router.get("/", response_model=SettingsOverviewResponse)
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full settings overview, user preferences, storage metrics, and provider status."""
    return SettingsService.get_settings_overview(db=db, current_user=current_user)


@router.put("/user-preferences", response_model=UserPreferencesResponse)
def update_user_preferences(
    payload: UserPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update individual user settings and notification subscriptions."""
    return SettingsService.update_user_preferences(
        db=db, current_user=current_user, req=payload
    )


@router.put("/system", response_model=SystemSettingsResponse)
def update_system_settings(
    payload: SystemSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update system-wide configuration and storage quotas (Administrators only)."""
    return SettingsService.update_system_settings(
        db=db, current_user=current_user, req=payload
    )


@router.post("/test-gemini", response_model=TestGeminiKeyResponse)
def test_gemini_key(
    payload: TestGeminiKeyRequest = TestGeminiKeyRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Safely validate Google Gemini API Key connectivity (Administrators only)."""
    return SettingsService.test_gemini_key(
        db=db, current_user=current_user, test_key=payload.api_key
    )


@router.post("/test-notification", response_model=TestNotificationResponse)
def test_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check notification channel readiness without displaying false success states."""
    return SettingsService.test_notification(db=db, current_user=current_user)


@router.get("/storage", response_model=WorkspaceStorageResponse)
def get_workspace_storage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's workspace storage consumption against active quota."""
    return SettingsService.get_workspace_storage(db=db, user_id=current_user.id)
