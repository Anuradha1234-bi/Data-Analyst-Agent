"""SQLAlchemy User Model."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """User database table representation with security and isolation."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), default="user", nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # User isolation relationships
    datasets = relationship("Dataset", back_populates="owner", cascade="all, delete-orphan")
    analyses = relationship("AnalysisHistory", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        # Ensure backward compatibility between username <-> full_name / email
        if not kwargs.get("username"):
            email_val = kwargs.get("email", "")
            base = email_val.split("@")[0] if "@" in email_val else email_val
            kwargs["username"] = (base or kwargs.get("full_name") or "user")[:50]
        if not kwargs.get("full_name"):
            kwargs["full_name"] = kwargs.get("username", "User")
        # Ensure backward compatibility between hashed_password <-> password_hash
        pwd_hash = kwargs.get("password_hash") or kwargs.get("hashed_password")
        if pwd_hash:
            kwargs["password_hash"] = pwd_hash
            kwargs["hashed_password"] = pwd_hash
        if not kwargs.get("role"):
            kwargs["role"] = "user"
        if "is_active" not in kwargs:
            kwargs["is_active"] = True
        super().__init__(**kwargs)

    @property
    def name(self) -> str:
        """Compatibility property for code referencing user.name."""
        return self.full_name or self.username or "User"

    @name.setter
    def name(self, val: str) -> None:
        self.full_name = val

    @property
    def effective_password_hash(self) -> str:
        """Return whichever password hash is populated."""
        return self.password_hash or self.hashed_password or ""

