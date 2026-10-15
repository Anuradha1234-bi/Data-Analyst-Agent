"""File Loader utility - Ingests CSV and XLSX workbooks with multi-encoding fallback."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union, BinaryIO
import io
import pandas as pd

from .validators import FileValidator


@dataclass
class LoadResult:
    """Result container for tabular file loading operations."""

    df: Optional[pd.DataFrame]
    filename: str
    file_type: str
    success: bool
    error_message: Optional[str] = None
    rows: int = 0
    columns: int = 0


class FileLoader:
    """Utility class for safely loading and validating tabular data."""

    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
    CSV_ENCODINGS = ["utf-8", "utf-8-sig", "latin1", "cp1252"]

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        """Check if file extension is supported."""
        suffix = Path(filename).suffix.lower()
        return suffix in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def load_file(
        cls,
        file_obj: Union[str, Path, BinaryIO],
        filename: str,
        file_size_bytes: int = 0,
    ) -> LoadResult:
        """Safely load CSV or Excel workbook (.xlsx, .xls) into a pandas DataFrame.

        Implements multi-encoding fallback for CSVs and comprehensive sanitization
        of all error conditions without leaking internal Python tracebacks.
        """
        suffix = Path(filename).suffix.lower()
        if suffix == ".csv":
            file_type = "CSV"
        elif suffix == ".xlsx":
            file_type = "XLSX"
        elif suffix == ".xls":
            file_type = "XLS"
        else:
            file_type = suffix.upper().replace(".", "")

        # 1. Validate file metadata (extension, non-empty, size)
        valid_meta, meta_err = FileValidator.validate_file_metadata(filename, file_size_bytes)
        if not valid_meta:
            return LoadResult(
                df=None,
                filename=filename,
                file_type=file_type,
                success=False,
                error_message=meta_err,
            )

        # 2. Dispatch loader by file format
        if suffix == ".csv":
            return cls._load_csv(file_obj, filename)
        elif suffix in (".xlsx", ".xls"):
            return cls._load_excel(file_obj, filename, suffix)
        else:
            return LoadResult(
                df=None,
                filename=filename,
                file_type=file_type,
                success=False,
                error_message=f"Unsupported file format '{suffix}'. Supported formats: CSV, XLSX, XLS.",
            )

    @classmethod
    def _load_csv(cls, file_obj: Union[str, Path, BinaryIO], filename: str) -> LoadResult:
        """Load CSV with multi-encoding fallback."""
        df: Optional[pd.DataFrame] = None
        last_error: Optional[str] = None

        # Read content bytes into memory buffer if file_obj is stream
        content_bytes: Optional[bytes] = None
        if hasattr(file_obj, "read"):
            try:
                # If stream has seek, reset to beginning first
                if hasattr(file_obj, "seek"):
                    file_obj.seek(0)
                content_bytes = file_obj.read()
                # Restore pointer
                if hasattr(file_obj, "seek"):
                    file_obj.seek(0)
            except Exception:
                return LoadResult(
                    df=None,
                    filename=filename,
                    file_type="CSV",
                    success=False,
                    error_message="Unable to read this CSV file. Please check that the file is accessible.",
                )

        # Try multiple encodings sequentially
        for encoding in cls.CSV_ENCODINGS:
            try:
                if content_bytes is not None:
                    buffer = io.BytesIO(content_bytes)
                    df = pd.read_csv(buffer, encoding=encoding)
                else:
                    df = pd.read_csv(file_obj, encoding=encoding)

                # If loaded successfully, break out of loop
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
            except pd.errors.EmptyDataError:
                return LoadResult(
                    df=None,
                    filename=filename,
                    file_type="CSV",
                    success=False,
                    error_message="The uploaded CSV file is empty. Please provide a file with data.",
                )
            except pd.errors.ParserError:
                return LoadResult(
                    df=None,
                    filename=filename,
                    file_type="CSV",
                    success=False,
                    error_message="The CSV file format is corrupted or malformed. Please check delimiter and row formatting.",
                )
            except Exception:
                last_error = "Unable to read this CSV file. Please check that the file is valid."

        if df is None:
            return LoadResult(
                df=None,
                filename=filename,
                file_type="CSV",
                success=False,
                error_message=last_error or "Unable to read this CSV file with supported encodings (UTF-8, Latin-1).",
            )

        # 3. Validate DataFrame structure (columns & rows)
        valid_df, df_err = FileValidator.validate_dataframe(df)
        if not valid_df:
            return LoadResult(
                df=None,
                filename=filename,
                file_type="CSV",
                success=False,
                error_message=df_err,
            )

        return LoadResult(
            df=df,
            filename=filename,
            file_type="CSV",
            success=True,
            error_message=None,
            rows=len(df),
            columns=len(df.columns),
        )

    @classmethod
    def _load_excel(cls, file_obj: Union[str, Path, BinaryIO], filename: str, suffix: str = ".xlsx") -> LoadResult:
        """Load Excel workbook with openpyxl (for .xlsx) or xlrd (for .xls) engine."""
        file_type = "XLS" if suffix.lower() == ".xls" else "XLSX"
        df = None
        last_error = None

        # Determine preferred engine order
        if suffix.lower() == ".xls":
            engines = ["xlrd", None]
        else:
            engines = ["openpyxl", None]

        for engine in engines:
            try:
                if hasattr(file_obj, "seek"):
                    file_obj.seek(0)
                if engine:
                    df = pd.read_excel(file_obj, engine=engine)
                else:
                    df = pd.read_excel(file_obj)
                if df is not None:
                    break
            except Exception as e:
                last_error = str(e)
                continue

        if df is None:
            return LoadResult(
                df=None,
                filename=filename,
                file_type=file_type,
                success=False,
                error_message=f"Unable to read this Excel file ({file_type}). Please ensure it is a valid, uncorrupted Excel workbook.",
            )

        # Validate DataFrame structure
        valid_df, df_err = FileValidator.validate_dataframe(df)
        if not valid_df:
            return LoadResult(
                df=None,
                filename=filename,
                file_type=file_type,
                success=False,
                error_message=df_err,
            )

        return LoadResult(
            df=df,
            filename=filename,
            file_type=file_type,
            success=True,
            error_message=None,
            rows=len(df),
            columns=len(df.columns),
        )
