"""Data Cleaner utility - Primitives for missing values, deduplication, and schema normalization."""

from typing import List, Optional
import pandas as pd


class DataCleaner:
    """Helper utilities for foundational data cleaning tasks."""

    @staticmethod
    def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
        """Return DataFrame with duplicate rows removed."""
        return df.drop_duplicates().copy()

    @staticmethod
    def fill_missing(df: pd.DataFrame, strategy: str = "mean") -> pd.DataFrame:
        """Fill missing values according to specified strategy (placeholder foundation)."""
        df_copy = df.copy()
        if strategy == "drop":
            return df_copy.dropna()
        return df_copy
