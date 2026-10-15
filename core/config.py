"""Central configuration module for AI Data Analyst Agent.

Handles environment variables, directory paths, and runtime settings.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables if .env exists
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """Application configuration container."""

    # Project metadata
    APP_NAME: str = os.getenv("APP_NAME", "AI Data Analyst Agent")
    TAGLINE: str = "Upload your data. Ask questions. Get real analysis."
    SUBTITLE: str = "Turn raw data into decisions with AI-powered analysis."
    VERSION: str = "0.1.0-phase0"

    # Environment
    ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # API Keys (Foundation only - no calls made in Phase 0)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Paths
    ROOT_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "data")
    REPORTS_DIR: Path = BASE_DIR / os.getenv("REPORTS_DIR", "reports")
    ASSETS_DIR: Path = BASE_DIR / "assets"

    # UI Theme constants (Light AI Analytics Dashboard Theme)
    PRIMARY_ACCENT: str = "#2563EB"
    BG_LIGHT: str = "#F8FAFC"
    BG_DARK: str = "#F8FAFC"  # Backwards compatibility
    SURFACE_LIGHT: str = "#FFFFFF"
    SURFACE_DARK: str = "#FFFFFF"  # Backwards compatibility
    BORDER_COLOR: str = "#E2E8F0"
    SIDEBAR_COLOR: str = "#0F172A"

    def ensure_directories(self) -> None:
        """Ensure necessary runtime directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def is_api_key_configured(self) -> bool:
        """Check if Gemini API key is provided and not a placeholder."""
        key = self.GEMINI_API_KEY.strip()
        return bool(key and key != "your_gemini_api_key_here")


# Global singleton instance
config = AppConfig()
config.ensure_directories()
