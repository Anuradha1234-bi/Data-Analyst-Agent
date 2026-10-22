"""FastAPI router for multiple dataset relationship discovery, review, and safe joins."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.auth.dependencies import get_current_user
from app.schemas.relationship import (
    RelationshipDetectRequest,
    RelationshipDetectResponse,
    RelationshipStatusUpdateRequest,
    JoinPreviewRequest,
    JoinPreviewResponse,
    JoinApplyRequest,
    JoinApplyResponse,
)
from app.services.relationship_service import RelationshipService

router = APIRouter(prefix="/relationships", tags=["Dataset Relationships & Joins"])


def _get_user_dataset(dataset_id: int, user: User, db: Session) -> Dataset:
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found.",
        )
    return dataset


@router.get("/status")
def relationships_status(current_user: User = Depends(get_current_user)):
    """Check relationship detection service health."""
    return {"status": "ready", "module": "relationships"}


@router.post("/detect", response_model=RelationshipDetectResponse)
def detect_relationships(
    request: RelationshipDetectRequest = RelationshipDetectRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Discover relationships between selected or all uploaded datasets for current user."""
    query = db.query(Dataset).filter(Dataset.user_id == current_user.id)
    if request.dataset_ids:
        query = query.filter(Dataset.id.in_(request.dataset_ids))

    datasets = query.all()
    return RelationshipService.detect_relationships(datasets)


@router.get("/", response_model=RelationshipDetectResponse)
def get_all_relationships(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Discover relationships among all uploaded datasets for current user."""
    datasets = db.query(Dataset).filter(Dataset.user_id == current_user.id).all()
    return RelationshipService.detect_relationships(datasets)


@router.post("/status", status_code=status.HTTP_200_OK)
def update_relationship_status(
    request: RelationshipStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """User review action: accept, reject, or ignore a suggested relationship."""
    valid_statuses = ("ACCEPTED", "REJECTED", "IGNORED", "PENDING")
    if request.status.upper() not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{request.status}'. Allowed: {valid_statuses}",
        )
    return {
        "relationship_id": request.relationship_id,
        "status": request.status.upper(),
        "message": f"Relationship marked as {request.status.upper()}.",
    }


@router.post("/join-preview", response_model=JoinPreviewResponse)
def preview_join(
    request: JoinPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simulate join execution and return row counts, matching stats, schema, and sample rows."""
    left_ds = _get_user_dataset(request.left_dataset_id, current_user, db)
    right_ds = _get_user_dataset(request.right_dataset_id, current_user, db)

    return RelationshipService.preview_join(
        left_dataset=left_ds,
        left_column=request.left_column,
        right_dataset=right_ds,
        right_column=request.right_column,
        join_type=request.join_type,
        limit=request.limit,
    )


@router.post("/join-apply", response_model=JoinApplyResponse)
def apply_join(
    request: JoinApplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute join upon user confirmation, persist derived dataset, and register in database."""
    left_ds = _get_user_dataset(request.left_dataset_id, current_user, db)
    right_ds = _get_user_dataset(request.right_dataset_id, current_user, db)

    return RelationshipService.apply_join(
        left_dataset=left_ds,
        left_column=request.left_column,
        right_dataset=right_ds,
        right_column=request.right_column,
        join_type=request.join_type,
        custom_dataset_name=request.custom_dataset_name,
        user_confirmed=request.user_confirmed,
        current_user=current_user,
        db=db,
    )
