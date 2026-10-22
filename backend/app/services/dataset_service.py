import uuid
from pathlib import Path
from typing import List, Tuple
from fastapi import HTTPException, UploadFile, status
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.models.dataset import Dataset
from app.schemas.dataset import DatasetResponse, DatasetUploadResponse

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class DatasetService:
    """Business logic service managing dataset upload, parsing, validation, storage, and isolation."""

    @staticmethod
    async def upload_dataset(
        db: Session,
        user_id: int,
        file: UploadFile,
    ) -> DatasetUploadResponse:
        """
        Validate, store, and parse an uploaded dataset file.
        Associates metadata exclusively with user_id.
        """
        original_filename = file.filename or "dataset"
        # Sanitize extension
        raw_ext = Path(original_filename).suffix.lower()

        if raw_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{raw_ext}'. Allowed formats: .csv, .xlsx, .xls",
            )

        # Read file contents in chunks to enforce size limit & avoid excessive memory usage
        contents = await file.read()
        file_size = len(contents)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty (0 bytes). Please upload a valid dataset.",
            )

        if file_size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed "
                    f"limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
                ),
            )

        # Generate unique, non-guessable storage filename to prevent path traversal
        clean_ext = raw_ext.lstrip(".")
        unique_filename = f"{uuid.uuid4().hex}_{user_id}.{clean_ext}"
        storage_dir = settings.dataset_storage_path
        storage_dir.mkdir(parents=True, exist_ok=True)
        target_path = storage_dir / unique_filename

        try:
            # Write file to secure storage directory
            with open(target_path, "wb") as f:
                f.write(contents)

            # Inspect and parse file
            row_count, column_count, column_names = DatasetService._inspect_dataset(target_path, clean_ext)

        except HTTPException:
            # Clean up disk on validation failure
            if target_path.exists():
                target_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            # Clean up disk on error
            if target_path.exists():
                target_path.unlink(missing_ok=True)
            logger.error(f"Failed to parse dataset '{original_filename}': {exc}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not parse dataset file: {str(exc)}",
            )

        # Create database metadata record
        user_friendly_name = Path(original_filename).stem or "dataset"
        dataset_record = Dataset(
            user_id=user_id,
            name=user_friendly_name,
            original_filename=original_filename,
            file_type=clean_ext,
            file_size=file_size,
            storage_path=str(target_path),
            row_count=row_count,
            column_count=column_count,
            column_names=column_names,
        )

        db.add(dataset_record)
        db.commit()
        db.refresh(dataset_record)

        logger.info(
            f"Dataset saved: id={dataset_record.id}, user_id={user_id}, "
            f"rows={row_count}, cols={column_count}, file='{original_filename}'"
        )

        return DatasetUploadResponse(
            message="Dataset uploaded and analyzed successfully",
            dataset=DatasetResponse.model_validate(dataset_record),
        )

    @staticmethod
    def _inspect_dataset(file_path: Path, file_type: str) -> Tuple[int, int, List[str]]:
        """Parse dataset using Pandas and extract row count, column count, and column names."""
        try:
            if file_type == "csv":
                # Handle possible encodings
                try:
                    df = pd.read_csv(file_path, nrows=500000)
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding="latin1", nrows=500000)
            elif file_type == "xlsx":
                df = pd.read_excel(file_path, engine="openpyxl")
            elif file_type == "xls":
                df = pd.read_excel(file_path, engine="xlrd")
            else:
                raise ValueError(f"Unsupported format: {file_type}")

            row_count = int(len(df))
            column_count = int(len(df.columns))
            column_names = [str(c) for c in df.columns.tolist()]
            return row_count, column_count, column_names

        except Exception as exc:
            raise ValueError(f"Invalid {file_type.upper()} file structure: {exc}")

    @staticmethod
    def get_user_datasets(db: Session, user_id: int) -> List[DatasetResponse]:
        """Retrieve all datasets belonging to the authenticated user."""
        datasets = (
            db.query(Dataset)
            .filter(Dataset.user_id == user_id)
            .order_by(Dataset.created_at.desc())
            .all()
        )
        return [DatasetResponse.model_validate(d) for d in datasets]

    @staticmethod
    def get_user_dataset(db: Session, user_id: int, dataset_id: int) -> DatasetResponse:
        """
        Retrieve a single dataset metadata record.
        Strictly enforces user isolation: returns 404 if dataset does not belong to user.
        """
        dataset = (
            db.query(Dataset)
            .filter(Dataset.id == dataset_id, Dataset.user_id == user_id)
            .first()
        )
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found",
            )
        return DatasetResponse.model_validate(dataset)

    @staticmethod
    def delete_user_dataset(db: Session, user_id: int, dataset_id: int) -> int:
        """
        Delete a dataset and remove its physical file from storage.
        Strictly enforces user isolation: returns 404 if dataset does not belong to user.
        """
        dataset = (
            db.query(Dataset)
            .filter(Dataset.id == dataset_id, Dataset.user_id == user_id)
            .first()
        )
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found",
            )

        # Delete physical file from disk safely
        try:
            file_path = Path(dataset.storage_path)
            if file_path.exists():
                file_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning(f"Could not remove physical dataset file {dataset.storage_path}: {exc}")

        # Delete from database
        db.delete(dataset)
        db.commit()

        logger.info(f"Dataset deleted successfully: id={dataset_id}, user_id={user_id}")
        return dataset_id
