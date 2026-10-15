"""Dataset metadata model for multi-dataset profiling and tracking."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class DatasetMetadata:
    """Rich metadata container for loaded tabular datasets."""

    filename: str
    file_type: str
    rows: int = 0
    columns: int = 0
    missing_values: int = 0
    duplicates: int = 0
    memory_usage_mb: float = 0.0
    column_names: List[str] = field(default_factory=list)
    data_types: Dict[str, str] = field(default_factory=dict)
    numeric_columns: List[str] = field(default_factory=list)
    categorical_columns: List[str] = field(default_factory=list)
    datetime_columns: List[str] = field(default_factory=list)
    possible_id_columns: List[str] = field(default_factory=list)
    possible_target_columns: List[str] = field(default_factory=list)
    semantic_domain: str = "General Tabular Dataset"
    summary_description: str = ""
