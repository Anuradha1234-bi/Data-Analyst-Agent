from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.models.user import User
from app.schemas.dataset import (
    DatasetDeleteResponse,
    DatasetResponse,
    DatasetUploadResponse,
)
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and inspect dataset",
    description="Upload a CSV, XLSX, or XLS file. Enforces size limits, parses schema, and saves metadata.",
)
async def upload_dataset(
    file: UploadFile = File(..., description="Dataset file (.csv, .xlsx, .xls)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DatasetUploadResponse:
    """Upload and process dataset file for the authenticated user."""
    return await DatasetService.upload_dataset(
        db=db,
        user_id=current_user.id,
        file=file,
    )


@router.get(
    "",
    response_model=List[DatasetResponse],
    status_code=status.HTTP_200_OK,
    summary="List user datasets",
    description="Retrieve all dataset records belonging to the authenticated user.",
)
def list_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[DatasetResponse]:
    """List datasets owned by current user."""
    return DatasetService.get_user_datasets(db=db, user_id=current_user.id)


@router.get(
    "/{dataset_id}",
    response_model=DatasetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dataset metadata",
    description="Retrieve metadata for a specific dataset. User-isolated.",
)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DatasetResponse:
    """Get dataset by ID (isolated to owner)."""
    return DatasetService.get_user_dataset(
        db=db,
        user_id=current_user.id,
        dataset_id=dataset_id,
    )


@router.delete(
    "/{dataset_id}",
    response_model=DatasetDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete dataset",
    description="Remove dataset record and its physical stored file. User-isolated.",
)
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DatasetDeleteResponse:
    """Delete dataset owned by current user."""
    deleted_id = DatasetService.delete_user_dataset(
        db=db,
        user_id=current_user.id,
        dataset_id=dataset_id,
    )
    return DatasetDeleteResponse(
        message="Dataset deleted successfully",
        id=deleted_id,
    )
