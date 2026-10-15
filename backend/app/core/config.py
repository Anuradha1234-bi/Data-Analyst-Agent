import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    APP_NAME: str = "AI Data Analyst Agent"
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    API_PREFIX: str = "/api"

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{(Path(__file__).resolve().parent.parent.parent / 'backend' / 'data_analyst.db').as_posix()}")

    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        os.getenv("SECRET_KEY", "super-secure-dev-secret-key-change-in-production-1234567890abcdef")
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Dataset Upload & Storage
    MAX_UPLOAD_SIZE_MB: int = 50
    STORAGE_DIR: str = "storage"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MAX_UPLOAD_SIZE_MB to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def dataset_storage_path(self) -> Path:
        """Resolve absolute path to datasets storage directory."""
        # Relative to backend root
        backend_root = Path(__file__).resolve().parent.parent.parent
        storage_path = backend_root / self.STORAGE_DIR / "datasets"
        storage_path.mkdir(parents=True, exist_ok=True)
        return storage_path

    @property
    def cors_origins(self) -> List[str]:
        """Compute allowed CORS origins including the configured FRONTEND_URL."""
        origins = [
            self.FRONTEND_URL.rstrip("/"),
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        unique_origins = []
        for origin in origins:
            if origin not in unique_origins:
                unique_origins.append(origin)
        return unique_origins


settings = Settings()
