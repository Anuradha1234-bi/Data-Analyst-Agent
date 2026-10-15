"""Relationship and Join Audit data models for multi-dataset cross-file analysis.

Provides type annotations and validation containers for detected relationships,
ambiguity resolution, confidence scoring, and join audit logging.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional


@dataclass
class Relationship:
    """Represents a validated or candidate relationship between two tabular datasets."""

    source_dataset: str
    source_column: str
    target_dataset: str
    target_column: str
    data_type_compatible: bool = True
    source_dtype: str = "object"
    target_dtype: str = "object"
    value_overlap_pct: float = 100.0
    source_unique: bool = False
    target_unique: bool = True
    source_null_pct: float = 0.0
    target_null_pct: float = 0.0
    source_duplicates_count: int = 0
    target_duplicates_count: int = 0
    relationship_type: str = "Many-to-One"  # "One-to-One", "Many-to-One", "One-to-Many", "Many-to-Many"
    confidence: str = "HIGH"  # "HIGH", "MEDIUM", "LOW"
    confidence_reasons: List[str] = field(default_factory=list)
    warning_messages: List[str] = field(default_factory=list)
    is_ambiguous: bool = False
    ambiguity_group: Optional[str] = None
    is_recommended: bool = False
    confirmed_by_user: bool = False
    join_risk: str = "Low Risk — Safe Foreign-to-Primary Key Linkage"

    cardinality: str = "Many-to-Many"
    cardinality_symbol: str = "N:M"
    direction: str = ""
    matching_values_count: int = 0
    unmatched_source_count: int = 0
    unmatched_target_count: int = 0
    source_null_count: int = 0
    target_null_count: int = 0
    source_pk_fk_hint: str = ""
    target_pk_fk_hint: str = ""
    cardinality_explanation: str = ""
    safe_for_join: bool = True
    is_candidate: bool = False

    @property
    def uniqueness_summary(self) -> str:
        """Clear human-readable uniqueness summary for UI display."""
        s_u = "Unique" if self.source_unique else f"Duplicated ({self.source_duplicates_count:,} dups)"
        t_u = "Unique" if self.target_unique else f"Duplicated ({self.target_duplicates_count:,} dups)"
        return f"Source: {s_u} • Target: {t_u}"

    @property
    def key_id(self) -> str:
        """Unique deterministic identifier for this relationship pair."""
        return f"{self.source_dataset}::{self.source_column}<->{self.target_dataset}::{self.target_column}"

    @property
    def display_name(self) -> str:
        """User-friendly display string."""
        return f"{self.source_dataset}.{self.source_column} ↔ {self.target_dataset}.{self.target_column}"

    @property
    def is_compatible(self) -> bool:
        return self.data_type_compatible

    @property
    def uniqueness_source(self) -> bool:
        return self.source_unique

    @property
    def uniqueness_target(self) -> bool:
        return self.target_unique

    @property
    def null_pct_source(self) -> float:
        return self.source_null_pct

    @property
    def null_pct_target(self) -> float:
        return self.target_null_pct

    @property
    def duplicate_keys_source(self) -> bool:
        return self.source_duplicates_count > 0

    @property
    def duplicate_keys_target(self) -> bool:
        return self.target_duplicates_count > 0



@dataclass
class JoinAudit:
    """Immutable audit record for cross-file joins performed by the agent."""

    left_dataset: str
    left_key: str
    right_dataset: str
    right_key: str
    join_type: str
    confidence: str
    overlap_percentage: float
    rows_before: int
    rows_after: int
    status: str = "SUCCESS"  # "SUCCESS", "REJECTED_ROW_EXPLOSION", "REJECTED_DUPLICATE_KEYS", "REJECTED_AMBIGUOUS"
    row_ratio: float = 1.0
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit entry to dictionary format matching specification."""
        return {
            "left_dataset": self.left_dataset,
            "left_key": self.left_key,
            "right_dataset": self.right_dataset,
            "right_key": self.right_key,
            "join_type": self.join_type,
            "confidence": self.confidence,
            "overlap_percentage": round(self.overlap_percentage, 1),
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "row_ratio": round(self.row_ratio, 2),
            "status": self.status,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }
