"""Dataset Profiler Service - Multi-dataset profiling, hygiene diagnostics, and semantic classification."""

from typing import Dict, Any, List, Optional
import pandas as pd

from agents.profiler import ProfilerAgent, ProfileResult, profile_dataset
from core.dataset_manager import DatasetManager, classify_dataset_domain
from models.dataset_metadata import DatasetMetadata


class DatasetProfilerService:
    """Service orchestrating profiling, data hygiene checks, and semantic metadata extraction."""

    @classmethod
    def profile_single_dataset(cls, df: pd.DataFrame) -> ProfileResult:
        """Profile a single dataset using the established ProfilerAgent."""
        return profile_dataset(df)

    @classmethod
    def profile_all(cls, datasets: Dict[str, pd.DataFrame]) -> Dict[str, ProfileResult]:
        """Profile all uploaded datasets independently without cross-contamination."""
        profiles: Dict[str, ProfileResult] = {}
        for name, df in datasets.items():
            profiles[name] = profile_dataset(df)
        return profiles

    @classmethod
    def extract_dataset_metadata(
        cls, df: pd.DataFrame, filename: str, file_type: str
    ) -> DatasetMetadata:
        """Extract rich metadata including semantic domain classification."""
        return DatasetManager.extract_metadata(df, filename, file_type)

    @classmethod
    def get_multi_dataset_summary(cls, datasets: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Calculate aggregated multi-dataset dashboard metrics."""
        total_files = len(datasets)
        total_rows = sum(len(df) for df in datasets.values())
        total_cols = sum(len(df.columns) for df in datasets.values())
        total_missing = sum(int(df.isna().sum().sum()) for df in datasets.values())
        total_dups = sum(int(df.duplicated().sum()) for df in datasets.values())

        files_summary = []
        for name, df in datasets.items():
            files_summary.append({
                "filename": name,
                "rows": len(df),
                "columns": len(df.columns),
                "missing": int(df.isna().sum().sum()),
                "duplicates": int(df.duplicated().sum()),
            })

        return {
            "total_files": total_files,
            "total_rows": total_rows,
            "total_columns": total_cols,
            "total_missing": total_missing,
            "total_duplicates": total_dups,
            "files": files_summary,
        }
