"""Pydantic schemas for Multi-Dataset Analysis, Combined Overview, and Comparison."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.profiling import DatasetProfileResponse
from app.schemas.relationship import RelationshipItem


class MultiDatasetAnalysisRequest(BaseModel):
    """Request payload to analyze one or multiple datasets."""
    dataset_ids: List[int] = Field(
        ...,
        min_length=1,
        description="List of dataset IDs belonging to the authenticated user."
    )
    mode: Optional[str] = Field(
        default="all",
        description="Analysis mode: 'individual', 'combined', 'comparison', or 'all'."
    )
    settings: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional analysis configurations."
    )


class DatasetAnalysisError(BaseModel):
    """Error information for a dataset that failed to analyze."""
    dataset_id: int
    dataset_name: Optional[str] = None
    error: str


class DatasetSummaryItem(BaseModel):
    """High-level summary metrics for a single dataset in a multi-dataset view."""
    dataset_id: int
    name: str
    file_type: str
    rows: int
    columns: int
    total_cells: int
    missing_cells: int
    missing_percentage: float
    duplicate_rows: int
    duplicate_percentage: float
    file_size_bytes: int
    health_score: Optional[int] = None
    health_status: Optional[str] = None
    numeric_columns_count: int = 0
    categorical_columns_count: int = 0
    datetime_columns_count: int = 0


class CombinedOverview(BaseModel):
    """Combined summary metrics across all analyzed datasets."""
    total_datasets: int
    total_rows: int
    total_columns: int
    distinct_columns: Optional[int] = Field(default=None, description="Number of distinct schema column names across all datasets")
    total_cells: int
    total_missing_cells: int
    overall_missing_percentage: float
    total_duplicate_rows: int
    overall_duplicate_percentage: float
    dataset_summaries: List[DatasetSummaryItem] = Field(default_factory=list)


class ColumnPresenceDetail(BaseModel):
    """Presence and profiling summary of a column within a specific dataset."""
    dataset_id: int
    dataset_name: str
    data_type: str
    semantic_type: str
    missing_count: int
    missing_percentage: float
    unique_count: int
    unique_percentage: float


class ColumnComparisonItem(BaseModel):
    """Comparison record for a column across multiple datasets."""
    column_name: str
    normalized_name: str
    present_in_dataset_ids: List[int]
    present_in_dataset_names: List[str]
    is_shared: bool
    is_shared_across_all: bool
    dataset_details: Dict[str, ColumnPresenceDetail] = Field(default_factory=dict)
    type_compatible: bool = True
    type_mismatch_warning: Optional[str] = None


class DatasetComparisonResponse(BaseModel):
    """Detailed structural and schema comparison across selected datasets."""
    shared_columns: List[str] = Field(
        default_factory=list,
        description="Columns that appear in two or more datasets."
    )
    shared_across_all_columns: List[str] = Field(
        default_factory=list,
        description="Columns that appear in every selected dataset."
    )
    unique_columns: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mapping of dataset name to columns unique only to that dataset."
    )
    column_matrix: List[ColumnComparisonItem] = Field(
        default_factory=list,
        description="Matrix of all unique columns across datasets with presence and types."
    )
    type_mismatches: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of columns present in multiple datasets with incompatible types."
    )
    is_comparable: bool = Field(
        default=True,
        description="Whether datasets share enough columns or structure for meaningful comparison."
    )
    comparability_notes: str = Field(
        default="",
        description="Explanation of comparability or reasons why datasets cannot be compared."
    )


class MultiDatasetAnalysisResponse(BaseModel):
    """Unified response containing multi-file analysis, individual profiles, comparison, and relationships."""
    status: str = Field(
        ...,
        description="'success' if all succeeded, 'partial' if some failed, 'failed' if all failed."
    )
    message: str
    mode: str
    total_selected: int
    total_successful: int
    total_failed: int
    errors: List[DatasetAnalysisError] = Field(default_factory=list)
    individual_profiles: Dict[int, DatasetProfileResponse] = Field(
        default_factory=dict,
        description="Profiles indexed by dataset ID."
    )
    combined_overview: Optional[CombinedOverview] = None
    comparison: Optional[DatasetComparisonResponse] = None
    relationships: List[RelationshipItem] = Field(
        default_factory=list,
        description="Detected relationships across the analyzed datasets."
    )
    cross_dataset_insights: List[str] = Field(
        default_factory=list,
        description="Actionable, verified cross-dataset insights."
    )
