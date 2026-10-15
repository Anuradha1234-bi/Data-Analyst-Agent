"""Pydantic schemas for multiple dataset relationship detection and joins."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RelationshipDetectRequest(BaseModel):
    """Request to detect relationships among specific or all datasets."""
    dataset_ids: Optional[List[int]] = Field(
        default=None,
        description="List of dataset IDs to analyze. If None or empty, analyzes all user datasets.",
    )


class RelationshipItem(BaseModel):
    """Detailed metadata for a detected relationship between two dataset columns."""
    id: str = Field(..., description="Unique identifier for this column relationship")
    source_dataset_id: int
    source_dataset_name: str
    source_column: str
    source_dtype: str
    source_unique_count: int
    source_null_count: int
    source_null_pct: float
    source_is_pk_candidate: bool
    source_is_fk_candidate: bool

    target_dataset_id: int
    target_dataset_name: str
    target_column: str
    target_dtype: str
    target_unique_count: int
    target_null_count: int
    target_null_pct: float
    target_is_pk_candidate: bool
    target_is_fk_candidate: bool

    data_type_compatible: bool
    matching_values_count: int
    value_overlap_pct: float
    relationship_type: str = Field(
        ...,
        description="One-to-One, One-to-Many, Many-to-One, Many-to-Many, or Unknown",
    )
    confidence: str = Field(..., description="HIGH, MEDIUM, or LOW")
    confidence_score: float = Field(..., description="Calculated score from 0.0 to 100.0")
    confidence_label: str = Field(
        ...,
        description="Strong Relationship, Possible Relationship, or Weak / Uncertain",
    )
    confidence_reasons: List[str] = Field(default_factory=list)
    warning_messages: List[str] = Field(default_factory=list)
    is_ambiguous: bool = False
    ambiguity_group: Optional[str] = None
    is_recommended: bool = False
    user_status: str = Field(
        default="PENDING",
        description="PENDING, ACCEPTED, REJECTED, or IGNORED",
    )
    join_risk: str = ""

    # Enhanced cardinality & direction fields
    cardinality: Optional[str] = Field(default=None, description="One-to-One, One-to-Many, Many-to-One, Many-to-Many, or Unknown")
    cardinality_symbol: Optional[str] = Field(default=None, description="1:1, 1:N, N:1, N:M, or ?")
    direction: Optional[str] = Field(default=None, description="Relationship direction e.g. Customers.customer_id → Orders.customer_id")
    unmatched_values_source: Optional[int] = Field(default=0, description="Count of unmatched keys in Dataset A")
    unmatched_values_target: Optional[int] = Field(default=0, description="Count of unmatched keys in Dataset B")
    source_pk_fk_hint: Optional[str] = Field(default=None, description="Key role classification (e.g. Candidate Unique Key or Repeated Join Key)")
    target_pk_fk_hint: Optional[str] = Field(default=None, description="Key role classification (e.g. Candidate Unique Key or Repeated Join Key)")
    cardinality_explanation: Optional[str] = Field(default=None, description="Detailed plain-English explanation of relationship cardinality")
    safe_for_join: Optional[bool] = Field(default=True, description="Whether this relationship is safe to join without row multiplication")
    is_candidate: Optional[bool] = Field(default=False, description="Whether this is a plausible candidate relationship")

    # Compatibility and join simulation fields
    source_dataset: Optional[str] = Field(default=None, description="Alias for source_dataset_name")
    target_dataset: Optional[str] = Field(default=None, description="Alias for target_dataset_name")
    source_unique: Optional[bool] = Field(default=None, description="Whether source matching keys are strictly unique")
    target_unique: Optional[bool] = Field(default=None, description="Whether target matching keys are strictly unique")
    overlap_score: Optional[float] = Field(default=None, description="Alias for value_overlap_pct")
    confidence_pct: Optional[float] = Field(default=None, description="Percentage confidence score 0.0 to 100.0")
    estimated_inner_join_rows: Optional[int] = Field(default=None, description="Calculated inner join row count")
    estimated_left_join_rows: Optional[int] = Field(default=None, description="Calculated left join row count")
    join_expansion_factor: Optional[float] = Field(default=None, description="Inner join rows divided by source rows")
    unmatched_source_count: Optional[int] = Field(default=0, description="Alias for unmatched_values_source")
    unmatched_target_count: Optional[int] = Field(default=0, description="Alias for unmatched_values_target")


class RelationshipDetectResponse(BaseModel):
    """Response returned after discovering relationships."""
    total_detected: int
    analyzed_datasets_count: int
    relationships: List[RelationshipItem]
    scan_summary: Optional[Dict[str, Any]] = Field(default=None, description="Detailed audit of datasets and columns evaluated during scan")
    message: Optional[str] = Field(default=None, description="Summary or explanation of detection result")


class RelationshipStatusUpdateRequest(BaseModel):
    """User action to accept, reject, or ignore a relationship."""
    relationship_id: str
    status: str = Field(..., description="ACCEPTED, REJECTED, IGNORED, or PENDING")


class JoinPreviewRequest(BaseModel):
    """Request to generate a dry-run join preview."""
    left_dataset_id: int
    left_column: str
    right_dataset_id: int
    right_column: str
    join_type: str = Field(default="inner", description="inner, left, right, or outer")
    limit: int = Field(default=10, ge=1, le=50)


class JoinPreviewResponse(BaseModel):
    """Dry-run preview metrics and sample output rows."""
    left_dataset_name: str
    right_dataset_name: str
    left_column: str
    right_column: str
    join_type: str
    left_total_rows: int
    right_total_rows: int
    estimated_resulting_rows: int
    matching_rows_count: int
    unmatched_left_rows: int
    unmatched_right_rows: int
    resulting_columns: List[str]
    sample_rows: List[Dict[str, Any]]
    warnings: List[str] = Field(default_factory=list)
    is_many_to_many: bool = False
    row_explosion_risk: bool = False


class JoinApplyRequest(BaseModel):
    """Request to execute a confirmed join and create a derived dataset."""
    left_dataset_id: int
    left_column: str
    right_dataset_id: int
    right_column: str
    join_type: str = Field(default="inner", description="inner, left, right, or outer")
    custom_dataset_name: Optional[str] = None
    user_confirmed: bool = Field(
        default=True,
        description="User must explicitly confirm the join operation",
    )


class JoinApplyResponse(BaseModel):
    """Response confirming creation of the new derived dataset."""
    success: bool
    message: str
    derived_dataset_id: int
    derived_dataset_name: str
    rows: int
    columns: int
    source_dataset_a: str
    source_dataset_b: str
    join_key: str
    join_type: str
    file_path: str
