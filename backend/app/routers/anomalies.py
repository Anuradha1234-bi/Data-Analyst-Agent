"""Anomaly & Outlier Detection Router."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.schemas.anomaly import (
    AnomalyDetectRequest,
    AnomalyDetectResponse,
    NumericColumnsResponse,
)
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection"])


@router.get("/status")
def anomalies_status(current_user: User = Depends(get_current_user)):
    """Check anomaly detection service readiness."""
    return {"status": "ready", "module": "anomalies"}


@router.get("/{dataset_id}/columns", response_model=NumericColumnsResponse)
def get_dataset_numeric_columns(
    dataset_id: int,
    version: str = Query("original", description="Dataset version: 'original' or 'cleaned'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve suitable numerical columns available for outlier detection."""
    return AnomalyService.get_numeric_columns(
        db=db,
        current_user=current_user,
        dataset_id=dataset_id,
        version=version,
    )


@router.post("/detect", response_model=AnomalyDetectResponse)
@router.post("/run", response_model=AnomalyDetectResponse)
def detect_dataset_anomalies(
    request: AnomalyDetectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute univariate IQR, multivariate Isolation Forest, or combined anomaly detection."""
    return AnomalyService.detect_anomalies(
        db=db,
        current_user=current_user,
        request=request,
    )
