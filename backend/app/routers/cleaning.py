"""Data Cleaning Router - Endpoints for dataset sanitization, previewing, and versioning."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.auth.dependencies import get_current_user
from app.schemas.cleaning import (
    CleaningOperationsRequest,
    CleaningOverviewResponse,
    CleaningPreviewResponse,
    CleaningApplyResponse,
    CleaningHistoryItem,
    ColumnValueSummaryResponse,
    CategoryInconsistenciesResponse,
    DateInspectionResponse,
    CleaningDashboardSummaryResponse,
    CleaningValidationReport,
    BulkPreviewResponse,
    DatasetVersionItem,
    CleaningReportResponse,
    SmartSuggestionsResponse,
    ConsistencyChecksResponse,
    CustomConsistencyRuleRequest,
    CustomConsistencyRuleResponse,
    VersionComparisonResponse,
)
from app.services.cleaning_service import DataCleaningService

router = APIRouter(prefix="/cleaning", tags=["Data Cleaning"])


def _get_user_dataset(dataset_id: int, user: User, db: Session) -> Dataset:
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )
    return dataset


@router.get("/status")
def cleaning_status(current_user: User = Depends(get_current_user)):
    """Check cleaning service readiness."""
    return {"status": "ready", "module": "cleaning"}


@router.get("/{dataset_id}", response_model=CleaningOverviewResponse)
@router.get("/{dataset_id}/overview", response_model=CleaningOverviewResponse)
def get_cleaning_overview(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve cleaning options, column diagnostics, and duplicate/empty previews for a dataset."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_cleaning_overview(dataset, db)


@router.get("/{dataset_id}/column-summary", response_model=ColumnValueSummaryResponse)
def get_column_value_summary(
    dataset_id: int,
    column: str = Query(..., description="Column name to inspect unique values and frequencies"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve unique values, frequencies, and percentages for a specific column."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_column_value_summary(dataset, column)


@router.get("/{dataset_id}/category-inconsistencies", response_model=CategoryInconsistenciesResponse)
def get_category_inconsistencies(
    dataset_id: int,
    column: str = Query(..., description="Categorical column to detect inconsistent value clusters"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Identify similar/equivalent categorical values (e.g. Male, male, MALE, M) for user-defined mapping."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.detect_category_clusters(dataset, column)


@router.get("/{dataset_id}/date-inspection", response_model=DateInspectionResponse)
def inspect_date_column(
    dataset_id: int,
    column: str = Query(..., description="Column to inspect date formats and parseable count"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Inspect date column parsing, format detection, and invalid values."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.inspect_date_column(dataset, column)


@router.post("/{dataset_id}/preview", response_model=CleaningPreviewResponse)
def preview_cleaning_operations(
    dataset_id: int,
    operations: CleaningOperationsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compute dry-run transformation metrics without modifying file on disk."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.preview_cleaning(dataset, operations)


@router.post("/{dataset_id}/apply", response_model=CleaningApplyResponse)
def apply_cleaning_operations(
    dataset_id: int,
    operations: CleaningOperationsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Apply cleaning operations, create versioned cleaned file, and record audit history."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.apply_cleaning(dataset, operations, current_user, db)


@router.get("/{dataset_id}/history", response_model=List[CleaningHistoryItem])
def get_dataset_cleaning_history(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve history of cleaning operations applied to this dataset."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_cleaning_history(dataset, db)


@router.get("/{dataset_id}/download")
def download_cleaned_dataset(
    dataset_id: int,
    format: str = Query("csv", description="Export format: csv or excel"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the cleaned version of the dataset in CSV or Excel format."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    if not dataset.has_cleaned or not dataset.cleaned_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cleaned version available for this dataset.",
        )

    content_or_path, filename, media_type = DataCleaningService.export_cleaned_dataset(dataset, format)

    if isinstance(content_or_path, (bytes, bytearray)):
        return Response(
            content=content_or_path,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return FileResponse(
        path=str(content_or_path),
        filename=filename,
        media_type=media_type,
    )


@router.post("/{dataset_id}/reset")
def reset_cleaned_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset cleaned dataset state back to original."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    DataCleaningService.reset_cleaning(dataset, db)
    return {"success": True, "message": "Cleaned dataset reset successfully."}


# =============================================================================
# Phase 4: Professional Workflow, Dashboard, Validation, & Reports
# =============================================================================

@router.get("/{dataset_id}/dashboard-summary", response_model=CleaningDashboardSummaryResponse)
def get_dataset_dashboard_summary(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch compact cleaning dashboard summary with quality score and status."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_dashboard_summary(dataset, db)


@router.get("/{dataset_id}/validation", response_model=CleaningValidationReport)
def get_dataset_validation_report(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run Before vs After hygiene checks and return validation report."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_validation_report(dataset, db)


@router.post("/{dataset_id}/bulk-preview", response_model=BulkPreviewResponse)
def preview_bulk_cleaning_operations(
    dataset_id: int,
    operations: CleaningOperationsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview chained operations in logical execution order with impact metrics."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.bulk_preview(dataset, operations)


@router.post("/{dataset_id}/bulk-apply", response_model=CleaningApplyResponse)
def apply_bulk_cleaning_operations(
    dataset_id: int,
    operations: CleaningOperationsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atomically apply all queued cleaning operations and create version snapshot."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.apply_cleaning(dataset, operations, current_user, db)


@router.get("/{dataset_id}/versions", response_model=List[DatasetVersionItem])
def get_dataset_version_timeline(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch timeline of dataset versions from Original to latest Cleaned."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_version_timeline(dataset, db)


@router.post("/{dataset_id}/versions/{version_tag}/restore")
def restore_dataset_version(
    dataset_id: int,
    version_tag: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restore dataset to any historical version or back to Original."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.restore_version(dataset, version_tag, current_user, db)


@router.get("/{dataset_id}/report", response_model=CleaningReportResponse)
def get_cleaning_report(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate structured cleaning report with operations log, validation, and score."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.generate_cleaning_report(dataset, db)


@router.get("/{dataset_id}/report/download")
def download_cleaning_report(
    dataset_id: int,
    format: str = Query("markdown", description="Report format: markdown, csv, or json"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the comprehensive cleaning report in Markdown, CSV, or JSON format."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    content, filename, media_type = DataCleaningService.export_cleaning_report(dataset, format, db)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{dataset_id}/original-preview")
def get_original_dataset_preview(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve sample preview of the original uploaded dataset (Previous CSV)."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_original_preview(dataset)


# =============================================================================
# Phase 5: Smart Cleaning Suggestions & Data Consistency Checks
# =============================================================================

@router.get("/{dataset_id}/suggestions", response_model=SmartSuggestionsResponse)
def get_smart_cleaning_suggestions(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve intelligent, data-driven cleaning recommendations grouped by priority."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_smart_suggestions(dataset)


@router.get("/{dataset_id}/consistency", response_model=ConsistencyChecksResponse)
def get_data_consistency_checks(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate cross-column relationships, date order, and identifier consistency."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.get_consistency_checks(dataset)


@router.post("/{dataset_id}/consistency/custom-rule", response_model=CustomConsistencyRuleResponse)
def evaluate_custom_consistency_rule(
    dataset_id: int,
    rule: CustomConsistencyRuleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a user-defined cross-column validation rule."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.evaluate_custom_rule(dataset, rule)


@router.get("/{dataset_id}/versions/compare", response_model=VersionComparisonResponse)
def compare_dataset_versions(
    dataset_id: int,
    v1: str = Query("Original", description="First version tag (e.g. Original)"),
    v2: str = Query("Cleaned v1", description="Second version tag (e.g. Cleaned v1)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compare structural metrics and hygiene scores between two dataset versions."""
    dataset = _get_user_dataset(dataset_id, current_user, db)
    return DataCleaningService.compare_versions(dataset, v1, v2, db)


