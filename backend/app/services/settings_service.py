"""Settings Service - Logic for System Configuration, User Preferences, and Workspace Quotas."""

import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.models.dataset import Dataset
from app.models.settings import SystemSetting, UserPreference
from app.schemas.settings import (
    UserPreferencesResponse,
    UserPreferencesUpdateRequest,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
    WorkspaceStorageResponse,
    SettingsOverviewResponse,
    TestGeminiKeyResponse,
    TestNotificationResponse,
)
from app.services.email_service import email_service


class SettingsService:
    """Service managing system configuration, secret masking, user preferences, and storage quotas."""

    @classmethod
    def get_or_create_user_preferences(cls, db: Session, user_id: int) -> UserPreference:
        """Retrieve existing user preferences or initialize defaults."""
        pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if not pref:
            pref = UserPreference(
                user_id=user_id,
                email_notifications=False,
                anomaly_alert_notifications=False,
                report_ready_notifications=True,
                cleaning_complete_notifications=True,
                theme="light",
                default_anomaly_method="both",
                default_iqr_multiplier=1.5,
            )
            db.add(pref)
            try:
                db.commit()
                db.refresh(pref)
            except Exception:
                db.rollback()
                pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        return pref

    @classmethod
    def get_system_setting(cls, db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve system setting value from database or return default."""
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting and setting.value is not None:
            return setting.value
        return default

    @classmethod
    def set_system_setting(
        cls, db: Session, key: str, value: str, user_id: int, description: Optional[str] = None
    ) -> SystemSetting:
        """Persist or update a system setting value."""
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not setting:
            setting = SystemSetting(
                key=key,
                value=value,
                description=description,
                updated_by=user_id,
            )
            db.add(setting)
        else:
            setting.value = value
            setting.updated_by = user_id
            setting.updated_at = datetime.now(timezone.utc)
            if description:
                setting.description = description

        db.commit()
        db.refresh(setting)
        return setting

    @classmethod
    def get_active_max_upload_size_mb(cls, db: Session) -> int:
        """Get effective max file upload size in MB (system setting overrides config)."""
        val = cls.get_system_setting(db, "max_upload_size_mb")
        if val is not None:
            try:
                return max(1, min(1024, int(val)))
            except (ValueError, TypeError):
                pass
        return settings.MAX_UPLOAD_SIZE_MB

    @classmethod
    def get_active_max_user_storage_mb(cls, db: Session) -> int:
        """Get effective total storage quota per user in MB."""
        val = cls.get_system_setting(db, "max_user_storage_mb")
        if val is not None:
            try:
                return max(1, min(10240, int(val)))
            except (ValueError, TypeError):
                pass
        return 500  # Default 500 MB per user workspace

    @classmethod
    def get_active_gemini_key(cls, db: Session) -> str:
        """Get active Gemini API key (database setting overrides .env)."""
        db_val = cls.get_system_setting(db, "gemini_api_key")
        if db_val and db_val.strip():
            return db_val.strip()
        return (os.getenv("GEMINI_API_KEY") or "").strip()

    @classmethod
    def mask_secret(cls, secret: Optional[str]) -> Optional[str]:
        """Safely mask secret key so it is never exposed in responses or logs."""
        if not secret or not secret.strip():
            return None
        cleaned = secret.strip()
        if len(cleaned) <= 8:
            return "••••••••"
        prefix = cleaned[:6]
        suffix = cleaned[-4:]
        return f"{prefix}...••••{suffix}"

    @classmethod
    def get_workspace_storage(cls, db: Session, user_id: int) -> WorkspaceStorageResponse:
        """Compute user's workspace storage consumption against active quota."""
        total_bytes = (
            db.query(func.coalesce(func.sum(Dataset.file_size_bytes), 0))
            .filter(Dataset.user_id == user_id)
            .scalar()
        ) or 0

        dataset_count = (
            db.query(func.count(Dataset.id))
            .filter(Dataset.user_id == user_id)
            .scalar()
        ) or 0

        quota_mb = cls.get_active_max_user_storage_mb(db)
        max_upload_mb = cls.get_active_max_upload_size_mb(db)
        used_mb = round(total_bytes / (1024 * 1024), 2)
        used_pct = min(100.0, round((used_mb / max(1.0, quota_mb)) * 100, 1))

        return WorkspaceStorageResponse(
            user_id=user_id,
            used_storage_bytes=int(total_bytes),
            used_storage_mb=used_mb,
            storage_quota_mb=float(quota_mb),
            used_percentage=used_pct,
            dataset_count=int(dataset_count),
            max_upload_size_mb=max_upload_mb,
            quota_warning=used_pct >= 85.0,
        )

    @classmethod
    def get_settings_overview(cls, db: Session, current_user: User) -> SettingsOverviewResponse:
        """Assemble complete settings overview for the current authenticated session."""
        pref = cls.get_or_create_user_preferences(db, current_user.id)
        storage = cls.get_workspace_storage(db, current_user.id)

        # Gemini settings
        raw_gemini_key = cls.get_active_gemini_key(db)
        gemini_configured = bool(raw_gemini_key and raw_gemini_key != "your_gemini_api_key_here")
        gemini_masked = cls.mask_secret(raw_gemini_key) if gemini_configured else None
        gemini_model = cls.get_system_setting(db, "gemini_model", "gemini-1.5-flash")

        # SMTP settings
        smtp_configured = email_service.is_smtp_configured()

        sys_settings = SystemSettingsResponse(
            max_upload_size_mb=cls.get_active_max_upload_size_mb(db),
            max_user_storage_mb=cls.get_active_max_user_storage_mb(db),
            gemini_api_key_configured=gemini_configured,
            gemini_api_key_masked=gemini_masked,
            gemini_model=gemini_model or "gemini-1.5-flash",
            smtp_configured=smtp_configured,
            smtp_host=settings.SMTP_HOST if settings.SMTP_HOST else "",
            smtp_port=settings.SMTP_PORT,
            smtp_from_email=settings.SMTP_FROM_EMAIL if settings.SMTP_FROM_EMAIL else "",
            smtp_tls=settings.SMTP_TLS,
            app_name=settings.PROJECT_NAME,
            app_env=settings.APP_ENV,
        )

        user_prefs = UserPreferencesResponse(
            email_notifications=pref.email_notifications,
            anomaly_alert_notifications=pref.anomaly_alert_notifications,
            report_ready_notifications=pref.report_ready_notifications,
            cleaning_complete_notifications=pref.cleaning_complete_notifications,
            theme=pref.theme or "light",
            default_anomaly_method=pref.default_anomaly_method or "both",
            default_iqr_multiplier=pref.default_iqr_multiplier or 1.5,
        )

        # Actual provider registry (only real, implemented integrations)
        available_providers = [
            {
                "id": "gemini",
                "name": "Google Gemini AI",
                "purpose": "Natural language query translation, conversational data analysis & AI insights",
                "configured": gemini_configured,
                "status": "Ready" if gemini_configured else "API Key Not Set",
                "type": "LLM / AI Model",
            },
            {
                "id": "smtp",
                "name": "SMTP Email Gateway",
                "purpose": "Password recovery links, notifications & system alerts",
                "configured": smtp_configured,
                "status": "Configured" if smtp_configured else "Unavailable (Development Mode)",
                "type": "Transactional Email",
            },
        ]

        # Notification channels registry
        notification_channels = [
            {
                "channel": "email",
                "name": "Email Notifications",
                "description": "Send alerts for data cleaning completion, anomaly warnings, and report readiness.",
                "available": smtp_configured,
                "status": "Active" if smtp_configured else "Unavailable (SMTP Unconfigured)",
                "reason": None if smtp_configured else "SMTP server is not configured in environment or settings.",
            },
            {
                "channel": "in_app",
                "name": "In-App Status Banners",
                "description": "Real-time UI status updates and completion toasts across active views.",
                "available": True,
                "status": "Active",
                "reason": None,
            },
        ]

        return SettingsOverviewResponse(
            user_id=current_user.id,
            username=current_user.username,
            role=current_user.role or "user",
            is_admin=(current_user.role == "admin"),
            user_preferences=user_prefs,
            system_settings=sys_settings,
            workspace_storage=storage,
            available_providers=available_providers,
            notification_channels=notification_channels,
        )

    @classmethod
    def update_user_preferences(
        cls, db: Session, current_user: User, req: UserPreferencesUpdateRequest
    ) -> UserPreferencesResponse:
        """Update authenticated user's individual settings."""
        pref = cls.get_or_create_user_preferences(db, current_user.id)

        if req.email_notifications is not None:
            pref.email_notifications = req.email_notifications
        if req.anomaly_alert_notifications is not None:
            pref.anomaly_alert_notifications = req.anomaly_alert_notifications
        if req.report_ready_notifications is not None:
            pref.report_ready_notifications = req.report_ready_notifications
        if req.cleaning_complete_notifications is not None:
            pref.cleaning_complete_notifications = req.cleaning_complete_notifications
        if req.theme is not None:
            pref.theme = req.theme
        if req.default_anomaly_method is not None:
            pref.default_anomaly_method = req.default_anomaly_method
        if req.default_iqr_multiplier is not None:
            pref.default_iqr_multiplier = req.default_iqr_multiplier

        pref.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(pref)

        return UserPreferencesResponse(
            email_notifications=pref.email_notifications,
            anomaly_alert_notifications=pref.anomaly_alert_notifications,
            report_ready_notifications=pref.report_ready_notifications,
            cleaning_complete_notifications=pref.cleaning_complete_notifications,
            theme=pref.theme,
            default_anomaly_method=pref.default_anomaly_method,
            default_iqr_multiplier=pref.default_iqr_multiplier,
        )

    @classmethod
    def update_system_settings(
        cls, db: Session, current_user: User, req: SystemSettingsUpdateRequest
    ) -> SystemSettingsResponse:
        """Apply system-wide configuration updates (restricted to administrators)."""
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative privileges required to modify system settings.",
            )

        if req.max_upload_size_mb is not None:
            cls.set_system_setting(
                db,
                "max_upload_size_mb",
                str(req.max_upload_size_mb),
                current_user.id,
                "Maximum upload size per dataset in MB",
            )

        if req.max_user_storage_mb is not None:
            cls.set_system_setting(
                db,
                "max_user_storage_mb",
                str(req.max_user_storage_mb),
                current_user.id,
                "Maximum storage quota per user in MB",
            )

        if req.gemini_api_key is not None:
            clean_key = req.gemini_api_key.strip()
            if clean_key:
                # Basic format sanity check for Gemini API key
                if len(clean_key) < 15:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid API key format. Gemini API keys are typically at least 20 characters.",
                    )
                cls.set_system_setting(
                    db,
                    "gemini_api_key",
                    clean_key,
                    current_user.id,
                    "Google Gemini API Key for LLM query planning & analysis",
                )

        if req.gemini_model is not None and req.gemini_model.strip():
            cls.set_system_setting(
                db,
                "gemini_model",
                req.gemini_model.strip(),
                current_user.id,
                "Default Gemini Model identifier",
            )

        # Assemble and return refreshed system settings with masked secrets
        raw_key = cls.get_active_gemini_key(db)
        gemini_configured = bool(raw_key and raw_key != "your_gemini_api_key_here")

        return SystemSettingsResponse(
            max_upload_size_mb=cls.get_active_max_upload_size_mb(db),
            max_user_storage_mb=cls.get_active_max_user_storage_mb(db),
            gemini_api_key_configured=gemini_configured,
            gemini_api_key_masked=cls.mask_secret(raw_key) if gemini_configured else None,
            gemini_model=cls.get_system_setting(db, "gemini_model", "gemini-1.5-flash") or "gemini-1.5-flash",
            smtp_configured=email_service.is_smtp_configured(),
            smtp_host=settings.SMTP_HOST if settings.SMTP_HOST else "",
            smtp_port=settings.SMTP_PORT,
            smtp_from_email=settings.SMTP_FROM_EMAIL if settings.SMTP_FROM_EMAIL else "",
            smtp_tls=settings.SMTP_TLS,
            app_name=settings.PROJECT_NAME,
            app_env=settings.APP_ENV,
        )

    @classmethod
    def test_gemini_key(
        cls, db: Session, current_user: User, test_key: Optional[str] = None
    ) -> TestGeminiKeyResponse:
        """Validate Gemini API key without leaking secret in exceptions."""
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative privileges required to validate API keys.",
            )

        key_to_test = (test_key or "").strip() or cls.get_active_gemini_key(db)
        if not key_to_test or key_to_test == "your_gemini_api_key_here":
            return TestGeminiKeyResponse(
                success=False,
                status="unconfigured",
                message="No Gemini API Key is configured. Please provide a valid Google Gemini API Key.",
                model="gemini-1.5-flash",
            )

        if len(key_to_test) < 15:
            return TestGeminiKeyResponse(
                success=False,
                status="invalid_format",
                message="API key format appears invalid (expected at least 20 characters).",
                model="gemini-1.5-flash",
            )

        # Perform a lightweight call to Google Gemini API
        try:
            import google.generativeai as genai
            genai.configure(api_key=key_to_test)
            model = genai.GenerativeModel("gemini-1.5-flash")
            # Quick health prompt
            response = model.generate_content("Ping", generation_config={"max_output_tokens": 5})
            if response and response.text:
                return TestGeminiKeyResponse(
                    success=True,
                    status="connected",
                    message="Successfully authenticated with Google Gemini API.",
                    model="gemini-1.5-flash",
                )
            return TestGeminiKeyResponse(
                success=True,
                status="connected",
                message="API Key verified and operational.",
                model="gemini-1.5-flash",
            )
        except Exception as e:
            err_str = str(e)
            if "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
                msg = "Google Gemini API rejected this key as invalid."
            elif "quota" in err_str.lower():
                msg = "Gemini API key is valid, but the account has exceeded quota."
            else:
                msg = f"Connection error when testing Gemini key: {err_str[:120]}"

            return TestGeminiKeyResponse(
                success=False,
                status="error",
                message=msg,
                model="gemini-1.5-flash",
            )

    @classmethod
    def test_notification(cls, db: Session, current_user: User) -> TestNotificationResponse:
        """Test notification channel readiness without displaying false success."""
        is_smtp = email_service.is_smtp_configured()
        if not is_smtp:
            return TestNotificationResponse(
                channel="email",
                configured=False,
                status="unavailable",
                message=(
                    "Email notification delivery is currently unavailable because the SMTP server "
                    "is not configured in environment or settings. In development mode, reset tokens "
                    "and alerts are routed to the server logs."
                ),
            )

        return TestNotificationResponse(
            channel="email",
            configured=True,
            status="ready",
            message=f"SMTP server is configured and ready at {settings.SMTP_HOST}:{settings.SMTP_PORT}.",
        )
