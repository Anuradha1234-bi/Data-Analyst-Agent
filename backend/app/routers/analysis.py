"""Analysis Router - Natural Language Querying, Multi-Dataset Analysis, and History."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.schemas.analysis import (
    MultiDatasetAnalysisRequest,
    MultiDatasetAnalysisResponse,
)
from app.schemas.analyst import (
    AnalysisAskRequest,
    AnalysisAskResponse,
    SuggestedQuestionsResponse,
    AnalysisHistoryListResponse,
)
from app.services.multi_dataset_service import MultiDatasetAnalysisService
from app.services.data_analyst_service import DataAnalystService

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/status")
def analysis_status(current_user: User = Depends(get_current_user)):
    """Check analysis service readiness."""
    return {"status": "ready", "module": "analysis"}


@router.get("/modes")
def get_supported_analysis_modes(current_user: User = Depends(get_current_user)):
    """Return available analysis modes and documentation."""
    return {
        "modes": [
            {
                "id": "individual",
                "label": "Individual Dataset Analysis",
                "description": "Deep-dive statistical profiling, data hygiene, and distribution analysis per dataset.",
            },
            {
                "id": "combined",
                "label": "Combined Multi-Dataset Overview",
                "description": "Aggregated summary of row counts, column counts, missing values, duplicates, and relational links across all selected datasets.",
            },
            {
                "id": "comparison",
                "label": "Multi-Dataset Comparison",
                "description": "Cross-dataset schema comparison, shared vs. unique attributes, type compatibility matrix, and comparability assessment.",
            },
            {
                "id": "all",
                "label": "Complete Multi-Dataset Analysis",
                "description": "Executes individual profiling, combined metrics, schema comparison, and relationship discovery in one unified pass.",
            },
        ]
    }


# =========================================================================
# PHASE 8: NATURAL LANGUAGE DATA ANALYST (ASK ANALYST)
# =========================================================================

@router.post("/ask", response_model=AnalysisAskResponse)
@router.post("/query", response_model=AnalysisAskResponse)
def ask_analytical_question(
    request: AnalysisAskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute evidence-grounded natural language analysis on a selected dataset."""
    return DataAnalystService.ask_question(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.get("/suggested-questions/{dataset_id}", response_model=SuggestedQuestionsResponse)
@router.get("/suggested/{dataset_id}", response_model=SuggestedQuestionsResponse)
def get_suggested_questions(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate valid, contextual questions based on the dataset's actual schema and data types."""
    return DataAnalystService.get_suggested_questions(
        dataset_id=dataset_id,
        current_user=current_user,
        db=db,
    )


@router.get("/history", response_model=AnalysisHistoryListResponse)
def get_analysis_history(
    dataset_id: Optional[int] = Query(None, description="Optional dataset filter"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve audit history of previously executed analytical questions."""
    return DataAnalystService.get_query_history(
        dataset_id=dataset_id,
        limit=limit,
        current_user=current_user,
        db=db,
    )


@router.delete("/history/{history_id}")
def delete_analysis_history_item(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a single query from the analytical audit trail."""
    return DataAnalystService.delete_history_item(
        history_id=history_id,
        current_user=current_user,
        db=db,
    )


@router.post("/history/clear")
def clear_analysis_history(
    dataset_id: Optional[int] = Query(None, description="Optional dataset filter to clear"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear analytical question history for the current user."""
    return DataAnalystService.clear_history(
        dataset_id=dataset_id,
        current_user=current_user,
        db=db,
    )


@router.post("/context/clear")
def clear_conversational_context(
    dataset_id: int = Query(..., description="Dataset ID to reset session context for"),
    current_user: User = Depends(get_current_user),
):
    """Reset bounded conversational memory for the dataset to start a new analytical thread."""
    from query.context_manager import ConversationContextManager
    ConversationContextManager.clear_context(current_user.id, dataset_id)
    return {"success": True, "message": "Conversational memory reset successfully."}


# =========================================================================
# MULTI-DATASET PROFILING & COMPARISON
# =========================================================================

@router.post("/multi", response_model=MultiDatasetAnalysisResponse)
@router.post("/multi-dataset", response_model=MultiDatasetAnalysisResponse)
def analyze_multiple_datasets(
    request: MultiDatasetAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze one or multiple selected datasets simultaneously with partial failure tolerance."""
    return MultiDatasetAnalysisService.analyze_datasets(
        dataset_ids=request.dataset_ids,
        mode=request.mode or "all",
        settings=request.settings,
        current_user=current_user,
        db=db,
    )


@router.get("/multi", response_model=MultiDatasetAnalysisResponse)
@router.get("/multi-dataset", response_model=MultiDatasetAnalysisResponse)
def get_analyze_multiple_datasets(
    dataset_ids: str = Query(..., description="Comma-separated dataset IDs"),
    mode: str = Query("all", description="Analysis mode"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze multiple datasets via GET request with comma-separated IDs."""
    ids = [int(x.strip()) for x in dataset_ids.split(",") if x.strip().isdigit()]
    return MultiDatasetAnalysisService.analyze_datasets(
        dataset_ids=ids,
        mode=mode,
        settings={},
        current_user=current_user,
        db=db,
    )


@router.post("/compare", response_model=MultiDatasetAnalysisResponse)
def compare_datasets(
    request: MultiDatasetAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dedicated endpoint to compare schemas and attributes across 2+ selected datasets."""
    return MultiDatasetAnalysisService.analyze_datasets(
        dataset_ids=request.dataset_ids,
        mode="comparison",
        settings=request.settings,
        current_user=current_user,
        db=db,
    )
