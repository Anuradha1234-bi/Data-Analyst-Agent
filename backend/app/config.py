"""Backend configuration module for AI Data Analyst Agent."""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Root of the project (ai-data-analyst-agent)
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Settings:
    """Application and environment configuration."""

    PROJECT_NAME: str = os.getenv("APP_NAME", "AI Data Analyst Agent")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    PROJECT_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"

    # Database Configuration (PostgreSQL supported, SQLite default for zero-friction setup)
    _env_db: str = os.getenv("DATABASE_URL", "")
    if not _env_db or _env_db == "sqlite:///./data_analyst.db" or _env_db == f"sqlite:///{PROJECT_ROOT.as_posix()}/data_analyst.db":
        DATABASE_URL: str = f"sqlite:///{BACKEND_DIR.as_posix()}/data_analyst.db"
    else:
        DATABASE_URL: str = _env_db

    # JWT Authentication & Security
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        os.getenv("JWT_SECRET_KEY", "super-secure-dev-secret-key-change-in-production-1234567890abcdef")
    )
    JWT_SECRET_KEY: str = SECRET_KEY  # Alias for backward compatibility
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # Password Reset & Email Configuration
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "20"))
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5174").rstrip("/")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@datanalyst.ai")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "AI Data Analyst Agent")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8002",
         "http://127.0.0.1:8002",
    ]

    # Storage Paths & Upload Limits
    UPLOAD_DIR: Path = PROJECT_ROOT / os.getenv("UPLOAD_DIR", "uploads")
    REPORTS_DIR: Path = PROJECT_ROOT / os.getenv("REPORTS_DIR", "reports")
    MODELS_DIR: Path = PROJECT_ROOT / os.getenv("MODELS_DIR", "models_storage")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    ALLOWED_EXTENSIONS: List[str] = [".csv", ".xlsx", ".xls"]

    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure necessary upload, report, and model directories exist."""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.MODELS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()

