"""Prediction & Forecasting API Router."""

from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.prediction import (
    AnalyzeDatasetRequest,
    AnalyzeDatasetResponse,
    PredictionRunDetailResponse,
    PredictionRunSummaryResponse,
    PredictionTrainRequest,
    PredictNewDataResponse,
)
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/prediction", tags=["Prediction & Forecasting"])


@router.get("/status")
def prediction_status(current_user: User = Depends(get_current_user)):
    """Check prediction service readiness."""
    return {
        "status": "ready",
        "module": "prediction",
        "supported_tasks": ["regression", "classification", "time_series_forecast"],
    }


@router.get("/models")
def get_candidate_models(current_user: User = Depends(get_current_user)):
    """Retrieve catalog of all supported machine learning algorithms and metadata."""
    return PredictionService.get_candidate_models_catalog()


@router.post("/analyze", response_model=AnalyzeDatasetResponse)
def analyze_dataset_for_prediction(
    request: AnalyzeDatasetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Inspect dataset, detect candidate target and datetime columns, and audit leakage."""
    return PredictionService.analyze_dataset(db=db, user=current_user, request=request)


@router.post("/train", response_model=PredictionRunDetailResponse)
def train_prediction_model(
    request: PredictionTrainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute model training on validation partitions, prevent leakage, and persist run."""
    return PredictionService.train_model(db=db, user=current_user, request=request)


@router.get("/runs", response_model=List[PredictionRunSummaryResponse])
def list_prediction_runs(
    dataset_id: Optional[int] = Query(None, description="Filter runs by dataset ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve list of saved prediction runs for the authenticated user."""
    return PredictionService.get_user_runs(db=db, user=current_user, dataset_id=dataset_id)


@router.get("/runs/{run_id}", response_model=PredictionRunDetailResponse)
def get_prediction_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full validation metrics, predictions, and feature importance for a run."""
    return PredictionService.get_run_detail(db=db, user=current_user, run_id=run_id)


@router.delete("/runs/{run_id}")
def delete_prediction_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a saved prediction run and remove stored model artifact."""
    return PredictionService.delete_run(db=db, user=current_user, run_id=run_id)


@router.get("/runs/{run_id}/export/csv")
def download_predictions_csv(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download predictions and uncertainty bounds as a CSV file."""
    csv_content, filename = PredictionService.export_predictions_csv(
        db=db, user=current_user, run_id=run_id
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/runs/{run_id}/export/report")
def download_evaluation_report(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download comprehensive model evaluation and performance report in Markdown format."""
    report_content, filename = PredictionService.export_evaluation_report(
        db=db, user=current_user, run_id=run_id
    )
    return Response(
        content=report_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/runs/{run_id}/predict", response_model=PredictNewDataResponse)
def predict_on_new_data(
    run_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Score uploaded new tabular CSV or Excel data against a trained model pipeline."""
    return PredictionService.predict_new_data(
        db=db, user=current_user, run_id=run_id, file=file
    )
