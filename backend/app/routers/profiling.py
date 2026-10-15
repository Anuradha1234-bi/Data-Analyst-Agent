from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.dataset import Dataset
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.schemas.profiling import DatasetProfileResponse
from app.schemas.analysis import (
    MultiDatasetAnalysisRequest,
    MultiDatasetAnalysisResponse,
)
from app.services.profiling_service import ProfilingService
from app.services.multi_dataset_service import MultiDatasetAnalysisService

router = APIRouter(prefix="/profiling", tags=["Data Profiling"])


@router.get("/status")
def profiling_status(current_user: User = Depends(get_current_user)):
    """Check profiling service readiness."""
    return {"status": "ready", "module": "profiling"}


@router.post("/batch", response_model=MultiDatasetAnalysisResponse)
@router.post("/multi", response_model=MultiDatasetAnalysisResponse)
def batch_profile_datasets(
    request: MultiDatasetAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Profile multiple datasets in a single batch request with partial error tolerance."""
    return MultiDatasetAnalysisService.analyze_datasets(
        dataset_ids=request.dataset_ids,
        mode=request.mode or "all",
        settings=request.settings,
        current_user=current_user,
        db=db,
    )


@router.get("/batch", response_model=MultiDatasetAnalysisResponse)
@router.get("/multi", response_model=MultiDatasetAnalysisResponse)
def get_batch_profile_datasets(
    dataset_ids: str = Query(..., description="Comma-separated dataset IDs"),
    mode: str = Query("all", description="Analysis mode"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Profile multiple datasets via GET request with comma-separated IDs."""
    ids = [int(x.strip()) for x in dataset_ids.split(",") if x.strip().isdigit()]
    return MultiDatasetAnalysisService.analyze_datasets(
        dataset_ids=ids,
        mode=mode,
        settings={},
        current_user=current_user,
        db=db,
    )


@router.get("/{dataset_id}", response_model=DatasetProfileResponse)
@router.post("/{dataset_id}", response_model=DatasetProfileResponse)
def get_dataset_profile_by_id(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve comprehensive statistical and data hygiene profile for a dataset."""
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )
    return ProfilingService.get_dataset_profile(dataset)
