"""SQLAlchemy models for System Settings and User Preferences."""

from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class SystemSetting(Base):
    """System-wide configuration parameters managed by administrators."""

    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(Integer, nullable=True)


class UserPreference(Base):
    """Per-user application preferences and notification settings."""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    email_notifications = Column(Boolean, default=False, nullable=False)
    anomaly_alert_notifications = Column(Boolean, default=False, nullable=False)
    report_ready_notifications = Column(Boolean, default=True, nullable=False)
    cleaning_complete_notifications = Column(Boolean, default=True, nullable=False)
    theme = Column(String(20), default="light", nullable=False)
    default_anomaly_method = Column(String(30), default="both", nullable=False)
    default_iqr_multiplier = Column(Float, default=1.5, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", backref="preferences")
