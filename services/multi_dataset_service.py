"""Root proxy for MultiDatasetAnalysisService."""

import sys
from pathlib import Path

# Add backend directory to sys.path if not present
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.multi_dataset_service import (
    MultiDatasetAnalysisService,
    _normalize_name,
    _are_types_compatible,
)

__all__ = [
    "MultiDatasetAnalysisService",
    "_normalize_name",
    "_are_types_compatible",
]
