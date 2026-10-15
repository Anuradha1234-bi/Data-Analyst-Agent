"""Dataset manager for caching, metadata extraction, and multi-dataset storage."""

from typing import Optional, Dict, Any, List
import pandas as pd

from models.dataset_metadata import DatasetMetadata


class DatasetManager:
    """Manages multi-dataset lifecycle, storage, and rich metadata extraction."""

    def __init__(self):
        self._datasets: Dict[str, pd.DataFrame] = {}
        self._original_datasets: Dict[str, pd.DataFrame] = {}
        self._cleaned_datasets: Dict[str, pd.DataFrame] = {}
        self._metadata_map: Dict[str, DatasetMetadata] = {}
        self._current_df: Optional[pd.DataFrame] = None
        self._metadata: Optional[DatasetMetadata] = None

    @property
    def has_dataset(self) -> bool:
        """Check if any dataset is currently held in memory."""
        return bool(self._datasets or self._current_df is not None)

    @property
    def metadata(self) -> Optional[DatasetMetadata]:
        """Return dataset metadata for active dataset."""
        return self._metadata

    @property
    def datasets(self) -> Dict[str, pd.DataFrame]:
        """Return all active datasets."""
        return self._datasets

    @property
    def original_datasets(self) -> Dict[str, pd.DataFrame]:
        """Return all untouched original datasets."""
        return self._original_datasets

    @property
    def cleaned_datasets(self) -> Dict[str, pd.DataFrame]:
        """Return all cleaned datasets."""
        return self._cleaned_datasets

    def add_dataset(self, df: pd.DataFrame, filename: str, file_type: str) -> DatasetMetadata:
        """Register a dataset into multi-dataset storage and extract rich metadata."""
        df_copy = df.copy(deep=True)
        self._datasets[filename] = df_copy
        self._original_datasets[filename] = df.copy(deep=True)
        self._cleaned_datasets[filename] = df.copy(deep=True)
        self._current_df = df_copy

        meta = self.extract_metadata(df_copy, filename, file_type)
        self._metadata_map[filename] = meta
        self._metadata = meta
        return meta

    def load_from_dataframe(self, df: pd.DataFrame, filename: str, file_type: str) -> DatasetMetadata:
        """Register a dataframe and generate metadata (backward-compatible)."""
        return self.add_dataset(df, filename, file_type)

    def get_dataset(self, filename: str) -> Optional[pd.DataFrame]:
        """Retrieve dataset by filename."""
        return self._datasets.get(filename)

    def get_metadata(self, filename: str) -> Optional[DatasetMetadata]:
        """Retrieve dataset metadata by filename."""
        return self._metadata_map.get(filename)

    def remove_dataset(self, filename: str) -> None:
        """Remove a dataset from storage."""
        self._datasets.pop(filename, None)
        self._original_datasets.pop(filename, None)
        self._cleaned_datasets.pop(filename, None)
        self._metadata_map.pop(filename, None)
        if self._datasets:
            first_name = next(iter(self._datasets.keys()))
            self._current_df = self._datasets[first_name]
            self._metadata = self._metadata_map.get(first_name)
        else:
            self._current_df = None
            self._metadata = None

    def clear(self) -> None:
        """Clear all datasets and metadata from memory."""
        self._datasets.clear()
        self._original_datasets.clear()
        self._cleaned_datasets.clear()
        self._metadata_map.clear()
        self._current_df = None
        self._metadata = None

    @staticmethod
    def extract_metadata(df: pd.DataFrame, filename: str, file_type: str) -> DatasetMetadata:
        """Extract comprehensive schema and semantic classification for a dataset."""
        numeric_cols = []
        categorical_cols = []
        datetime_cols = []
        possible_ids = []
        possible_targets = []
        dtypes_map = {}

        for col in df.columns:
            s = df[col]
            dtype_str = str(s.dtype)
            dtypes_map[col] = dtype_str

            col_lower = str(col).lower()

            if pd.api.types.is_numeric_dtype(s):
                numeric_cols.append(col)
                # Check if potential ID (high uniqueness, integer, or name ends in _id / id)
                if col_lower.endswith("_id") or col_lower == "id" or col_lower.endswith("id") or col_lower.endswith("_code"):
                    possible_ids.append(col)
                elif any(word in col_lower for word in ["amount", "revenue", "sales", "price", "total", "qty", "quantity", "cost", "score", "value", "profit", "salary", "balance"]):
                    possible_targets.append(col)
            elif pd.api.types.is_datetime64_any_dtype(s):
                datetime_cols.append(col)
            else:
                # String / Categorical
                if col_lower.endswith("_id") or col_lower == "id" or col_lower.endswith("id") or col_lower.endswith("_code"):
                    possible_ids.append(col)
                elif any(word in col_lower for word in ["status", "category", "type", "region", "country", "segment", "gender", "department"]):
                    categorical_cols.append(col)
                else:
                    categorical_cols.append(col)

        # Domain classification
        domain, desc = classify_dataset_domain(filename, df.columns.tolist(), numeric_cols, possible_ids)

        return DatasetMetadata(
            filename=filename,
            file_type=file_type,
            rows=len(df),
            columns=len(df.columns),
            missing_values=int(df.isna().sum().sum()),
            duplicates=int(df.duplicated().sum()),
            memory_usage_mb=float(df.memory_usage(deep=True).sum() / (1024 * 1024)),
            column_names=list(df.columns),
            data_types=dtypes_map,
            numeric_columns=numeric_cols,
            categorical_columns=categorical_cols,
            datetime_columns=datetime_cols,
            possible_id_columns=possible_ids,
            possible_target_columns=possible_targets,
            semantic_domain=domain,
            summary_description=desc,
        )


def classify_dataset_domain(
    filename: str,
    columns: List[str],
    numeric_cols: List[str],
    id_cols: List[str],
) -> tuple[str, str]:
    """Classify the semantic nature of a dataset dynamically based on columns, values, and name."""
    cols_lower = [str(c).lower() for c in columns]
    all_text = f"{filename.lower()} {' '.join(cols_lower)}"

    # Score clusters
    scores = {
        "Sales / Transaction Dataset": sum(1 for k in ["sale", "order", "invoice", "trans", "amount", "revenue", "qty", "quantity", "price", "discount", "bill"] if k in all_text),
        "Customer / User Dataset": sum(1 for k in ["customer", "client", "user", "email", "phone", "address", "segment", "gender", "age", "account", "member"] if k in all_text),
        "Product / Catalog Dataset": sum(1 for k in ["product", "item", "sku", "catalog", "unit_price", "brand", "category", "inventory", "stock", "description"] if k in all_text),
        "Regional / Geographic Dataset": sum(1 for k in ["region", "country", "state", "city", "zone", "territory", "zip", "postal", "location", "geo", "area"] if k in all_text),
        "Human Resources / Employee Dataset": sum(1 for k in ["emp", "staff", "salary", "department", "hire", "job", "designation", "manager", "payroll"] if k in all_text),
        "Academic / Education Dataset": sum(1 for k in ["student", "course", "grade", "mark", "exam", "score", "attendance", "teacher", "enroll", "class"] if k in all_text),
        "Financial / Accounting Dataset": sum(1 for k in ["balance", "ledger", "debit", "credit", "asset", "liability", "expense", "budget", "tax"] if k in all_text),
        "Healthcare / Clinical Dataset": sum(1 for k in ["patient", "doctor", "diagnosis", "hospital", "treatment", "medicine", "dose", "clinical"] if k in all_text),
    }

    best_domain = max(scores, key=scores.get)
    if scores[best_domain] > 0:
        desc = f"Contains {len(columns)} attributes relating to {best_domain.lower().replace(' dataset', '')} operations."
        return best_domain, desc

    # Structural fallback
    if len(id_cols) > 0 and len(numeric_cols) > 2:
        return "Operational Tabular Dataset", f"Tabular entity dataset with {len(columns)} features and {len(id_cols)} key identifier(s)."
    return "General Tabular Dataset", f"Ingested dataset with {len(columns)} attributes."
