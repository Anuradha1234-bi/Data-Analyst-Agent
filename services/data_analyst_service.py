"""Root proxy for DataAnalystService."""

import sys
from pathlib import Path

# Add backend directory to sys.path if not present
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.data_analyst_service import DataAnalystService

__all__ = ["DataAnalystService"]
