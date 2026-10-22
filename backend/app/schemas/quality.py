"""Data Quality Schemas - Pydantic models for data quality assessment."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DataQualitySummary(BaseModel):
    """High-level summary of dataset quality."""
    overall_status: str = Field(..., description="'Good', 'Needs Attention', or 'Poor'")
    quality_score: float = Field(..., description="0-100 deterministic quality score")
    total_rows: int
    total_columns: int
    total_cells: int
    missing_cells: int
    missing_percentage: float
    duplicate_rows: int
    duplicate_percentage: float
    has_duplicates: bool
    empty_rows: int
    empty_columns: int
    constant_columns_count: int
    near_constant_columns_count: int
    problematic_columns_count: int
    quality_issues_count: int
    status_message: str


class ColumnQuality(BaseModel):
    """Quality metrics and issue detection for a specific column."""
    column_name: str
    data_type: str
    inferred_type: str
    total_count: int
    missing_count: int
    missing_percentage: float
    unique_count: int
    unique_percentage: float
    is_constant: bool
    is_near_constant: bool
    is_empty: bool
    has_mixed_types: bool
    invalid_null_like_count: int
    issues: List[str]
    duplicate_constant_issue: str
    quality_status: str = Field(..., description="'Good', 'Warning', or 'Critical'")


class ColumnMissingInfo(BaseModel):
    column_name: str
    missing_count: int
    missing_percentage: float


class MissingValuesReport(BaseModel):
    total_missing_cells: int
    missing_percentage: float
    affected_columns_count: int
    columns_with_missing: List[ColumnMissingInfo]


class DuplicateRecordsReport(BaseModel):
    duplicate_rows: int
    duplicate_percentage: float
    has_duplicates: bool


class DataTypesReport(BaseModel):
    numeric_columns: List[str]
    categorical_columns: List[str]
    datetime_columns: List[str]
    boolean_columns: List[str]
    inconsistent_columns: List[Dict[str, Any]]


class EmptyRecordsReport(BaseModel):
    empty_rows_count: int
    empty_columns_count: int
    empty_column_names: List[str]


class ConstantColumnItem(BaseModel):
    column_name: str
    constant_value: Optional[str]
    percentage: float


class ConstantColumnsReport(BaseModel):
    constant_columns: List[ConstantColumnItem]
    near_constant_columns: List[ConstantColumnItem]


class NullLikeValueItem(BaseModel):
    column_name: str
    token: str
    count: int


class ConsistencyReport(BaseModel):
    mixed_type_columns: List[Dict[str, Any]]
    null_like_values_detected: List[NullLikeValueItem]
    formatting_issues_count: int


class DataQualityResponse(BaseModel):
    """Complete Data Quality diagnostic response."""
    dataset_id: int
    filename: str
    summary: DataQualitySummary
    columns: List[ColumnQuality]
    missing_report: MissingValuesReport
    duplicate_report: DuplicateRecordsReport
    types_report: DataTypesReport
    empty_report: EmptyRecordsReport
    constant_report: ConstantColumnsReport
    consistency_report: ConsistencyReport
    analyzed_at: str
    evaluated_version: Optional[str] = "original"
    has_cleaned: bool = False
