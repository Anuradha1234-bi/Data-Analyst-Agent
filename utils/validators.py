"""Validators utility - File inspection, size validation, and schema checks."""

from pathlib import Path
from typing import Tuple, Optional
import pandas as pd


class FileValidator:
    """Validates file upload constraints, extensions, and schema sanity."""

    MAX_FILE_SIZE_MB: int = 200
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

    @classmethod
    def validate_file_metadata(cls, filename: str, file_size_bytes: int) -> Tuple[bool, Optional[str]]:
        """Validate filename extension and maximum file size.

        Returns (is_valid, error_message).
        """
        if not filename or not filename.strip():
            return False, "No file selected. Please select a valid CSV, XLSX, or XLS file."

        suffix = Path(filename).suffix.lower()
        if suffix not in cls.ALLOWED_EXTENSIONS:
            return (
                False,
                f"Unsupported file format '{suffix}'. Supported formats: CSV, XLSX, XLS.",
            )

        if file_size_bytes <= 0:
            return False, "The uploaded file is empty (0 bytes). Please provide a file with data."

        size_mb = file_size_bytes / (1024 * 1024)
        if size_mb > cls.MAX_FILE_SIZE_MB:
            return (
                False,
                f"File size ({size_mb:.1f} MB) exceeds maximum allowed size ({cls.MAX_FILE_SIZE_MB} MB).",
            )

        return True, None

    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """Validate that parsed DataFrame contains columns and at least one row.

        Returns (is_valid, error_message).
        """
        if df is None:
            return False, "Unable to read dataset content."

        if df.shape[1] == 0:
            return False, "The uploaded dataset contains no columns. Please check that your file has a header row."

        if df.shape[0] == 0:
            return False, "The uploaded dataset contains no rows of data. Please provide a dataset with at least one record."

        return True, None
