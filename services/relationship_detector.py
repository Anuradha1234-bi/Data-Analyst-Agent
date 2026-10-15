"""Relationship Detector Service - Safe and Intelligent Cross-Dataset Linkage Engine.

Discovers, profiles, validates, and audits candidate join relationships across arbitrary
tabular datasets with multi-layer safeguards against CSV/index artifacts, ambiguity,
duplicate-key explosions, and semantic mismatches.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Set
from pathlib import Path
import re
import pandas as pd
import numpy as np

from models.relationship import Relationship, JoinAudit


class RelationshipDetector:
    """Discovers, validates, and scores relationships across multiple uploaded datasets."""

    # Common generic ID column names that can represent identifiers
    GENERIC_ID_NAMES = {
        "id", "code", "key", "number", "num", "no", "identifier", "pk", "fk", "idx"
    }

    # Internal pandas index artifacts that are NEVER real data columns
    INTERNAL_INDEX_NAMES = {
        "level_0", "level_1", "level_2", "__index_level_0__"
    }

    # Standard abbreviations mapped to canonical entity bases
    ABBREVIATION_MAP = {
        "cust": "customer",
        "emp": "employee",
        "dept": "department",
        "prod": "product",
        "cat": "category",
        "org": "organization",
        "acct": "account",
        "acc": "account",
        "usr": "user",
        "supp": "supplier",
        "vend": "vendor",
        "cli": "client",
        "ord": "order",
        "inv": "invoice",
        "item": "item",
        "num": "number",
        "nbr": "number",
        "no": "number",
        "txn": "transaction",
        "trans": "transaction",
        "loc": "location",
        "addr": "address",
        "qty": "quantity",
        "amt": "amount",
        "pct": "percentage",
    }

    # Recognized natural business domain keys and common join columns
    DOMAIN_NATURAL_KEYS = {
        "customer", "employee", "product", "department", "user", "order", "invoice",
        "account", "supplier", "vendor", "client", "item", "student", "store",
        "warehouse", "commodity", "crop", "sku", "isbn", "vin", "upc", "email", "phone",
        "code", "shared_key"
    }

    # Attributes that represent metrics, low-cardinality demographics, timestamps, or unstructured text
    # These must NOT be promoted to standalone entity join keys merely because names match.
    NON_RELATIONAL_ATTRIBUTES = {
        # Continuous numerical metrics & financial measures
        "income", "annual_income", "annual_income_inr", "salary", "amount", "revenue",
        "price", "cost", "tax", "total", "balance", "rate", "fee", "profit",
        "discount", "score", "weight", "height", "age", "quantity", "qty",
        "cgpa", "package", "duration", "hours", "units", "budget", "expenses",
        # Generic low-cardinality categorical dimensions
        "city", "state", "country", "status", "gender", "category", "type",
        "role", "region", "district", "zone", "zipcode", "postal_code", "pin_code",
        # Dates and timestamps
        "signup_date", "created_at", "updated_at", "creation_date", "modified_date",
        "birth_date", "dob", "timestamp", "datetime", "time", "login_time", "event_time", "date",
        # Descriptive text & person names
        "notes", "comment", "comments", "description", "desc", "remarks",
        "memo", "text", "message", "details", "summary", "notes_text", "address", "street",
        "customer_name", "client_name", "emp_name", "user_name"
    }

    NULL_STRINGS = {"", "nan", "null", "none", "na", "<na>", "n/a", "undefined", "nat"}

    @classmethod
    def _normalize_col_name(cls, col_name: str) -> str:
        """Normalize column name: lowercase, strip whitespace, replace non-alphanumeric with _."""
        if col_name is None:
            return ""
        s = str(col_name).strip().lower()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        return s.strip("_")

    @classmethod
    def _extract_clean_dataset_name(cls, dataset_name: str) -> str:
        """Strip system ID prefixes (e.g. '14::'), UUID hashes, and extensions from dataset names."""
        clean = re.sub(r"^\d+::", "", str(dataset_name))
        clean = re.sub(r"^[0-9a-fA-F]{16,32}_", "", clean)
        clean = re.sub(r"\.(csv|xlsx|xls)$", "", clean.lower())
        clean = re.sub(r"[^a-z0-9]+", "_", clean).strip("_")
        return clean

    DESCRIPTIVE_TEXT_NAMES = {
        "notes", "comment", "comments", "description", "desc", "remarks",
        "memo", "text", "message", "details", "summary", "notes_text"
    }

    @classmethod
    def _extract_entity_and_concept(cls, col_name: str, dataset_name: str) -> Tuple[str, bool]:
        """Extract canonical domain concept and whether it is an explicit identifier."""
        norm = cls._normalize_col_name(col_name)
        if not norm:
            return "", False

        ds_clean = cls._extract_clean_dataset_name(dataset_name)
        ds_singular = re.sub(r"s$", "", ds_clean)

        # 1. Generic ID column (e.g., 'id', 'pk')
        if norm in cls.GENERIC_ID_NAMES:
            return ds_singular or "id", True

        # 2. Suffix patterns: customer_id, cust_id, order_no, product_code
        id_match = re.match(r"^(.+?)[_-]?(id|code|key|no|num|number)$", norm)
        if id_match:
            prefix = id_match.group(1).rstrip("_")
            mapped_prefix = cls.ABBREVIATION_MAP.get(prefix, prefix)
            return f"{mapped_prefix}_id", True

        # 3. Prefix patterns: id_customer
        id_prefix_match = re.match(r"^(id|code|key|no|num)[_-](.+)$", norm)
        if id_prefix_match:
            suffix = id_prefix_match.group(2).lstrip("_")
            mapped_suffix = cls.ABBREVIATION_MAP.get(suffix, suffix)
            return f"{mapped_suffix}_id", True

        # 4. Name patterns: customer_name, EmployeeName, student_name, full_name
        name_match = re.match(r"^(.+?)[_-]?(name|fullname)$", norm)
        if name_match:
            return "name", False

        # 5. Email patterns: user_email, emp_email
        email_match = re.match(r"^(.+?)[_-]?(email|mail)$", norm)
        if email_match:
            return "email", False

        # 6. Abbreviation direct match
        if norm in cls.ABBREVIATION_MAP:
            return cls.ABBREVIATION_MAP[norm], False

        return norm, False

    @classmethod
    def is_artifact_column(cls, col_name: str, series: Optional[pd.Series] = None) -> bool:
        """Check if column is an artifact (e.g. pandas internal index, completely empty).

        Does NOT blindly discard 'Unnamed' columns if they contain actual data values.
        """
        if col_name is None:
            return True
        norm = cls._normalize_col_name(col_name)
        if not norm:
            return True

        # Strictly internal pandas index names
        if norm in cls.INTERNAL_INDEX_NAMES:
            return True

        if series is not None:
            val = series.dropna()
            if val.empty:
                return True
            # Check if all empty strings
            if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
                if val.astype(str).str.strip().eq("").all():
                    return True
            # Check if column is strictly an auto-generated sequential 0..N-1 integer index
            if norm.startswith("unnamed") or norm in ("index", "row_id", "row_num"):
                if pd.api.types.is_numeric_dtype(series) and not val.empty:
                    arr = val.values
                    if len(arr) > 2 and (arr == np.arange(arr[0], arr[0] + len(arr))).all():
                        return True
        return False

    @classmethod
    def is_non_relational_attribute(cls, col_name: str) -> bool:
        """Check if column is a measure, demographic dimension, timestamp, or unstructured text.

        These attributes must NOT be automatically promoted to standalone join keys.
        """
        if col_name is None:
            return True
        norm = cls._normalize_col_name(col_name)
        if not norm:
            return True
        if norm in cls.NON_RELATIONAL_ATTRIBUTES or norm in cls.DESCRIPTIVE_TEXT_NAMES:
            return True
        if norm.endswith("_name") or norm == "name":
            return True
        if norm.endswith("_date") or norm.endswith("date") or norm.endswith("_time") or norm.endswith("time"):
            return True
        return False

    @classmethod
    def detect_all_relationships(cls, datasets: Dict[str, pd.DataFrame]) -> List[Relationship]:
        """Inspect all pairs of datasets and discover candidate relationships with safeguards."""
        relationships: List[Relationship] = []
        filenames = list(datasets.keys())

        if len(filenames) < 2:
            return []

        # Pre-cache normalized values and unique sets per column across all datasets
        col_cache: Dict[Tuple[str, str], Tuple[Optional[pd.Series], Set[Any], int, int, bool]] = {}
        for ds_name, df in datasets.items():
            for col in df.columns:
                series = df[col]
                is_art = cls.is_artifact_column(col, series) or cls.is_non_relational_attribute(col)
                if is_art:
                    col_cache[(ds_name, str(col))] = (None, set(), 0, 0, True)
                    continue
                norm = series.map(cls._normalize_key).dropna()
                null_count = int(len(series) - len(norm))
                s_unique = set(norm.unique())
                dup_count = int(norm.duplicated().sum())
                col_cache[(ds_name, str(col))] = (norm, s_unique, null_count, dup_count, False)

        # Compare every unique unordered pair of datasets
        for i in range(len(filenames)):
            for j in range(i + 1, len(filenames)):
                ds_a_name = filenames[i]
                ds_b_name = filenames[j]
                df_a = datasets[ds_a_name]
                df_b = datasets[ds_b_name]

                pair_relationships = cls._detect_pair_relationships(
                    ds_a_name, df_a, ds_b_name, df_b, col_cache=col_cache
                )
                relationships.extend(pair_relationships)

        # Flag and group ambiguous relationships between same dataset pairs
        cls._resolve_ambiguities(relationships)

        return relationships

    @classmethod
    def detect_relationships(cls, datasets: Dict[str, pd.DataFrame]) -> List[Relationship]:
        """Convenience alias for detect_all_relationships."""
        return cls.detect_all_relationships(datasets)

    @classmethod
    def _detect_pair_relationships(
        cls,
        name_a: str,
        df_a: pd.DataFrame,
        name_b: str,
        df_b: pd.DataFrame,
        col_cache: Optional[Dict] = None,
    ) -> List[Relationship]:
        """Detect candidate relationships between two specific DataFrames."""
        candidates: List[Relationship] = []

        for col_a in df_a.columns:
            ca = col_cache.get((name_a, str(col_a))) if col_cache else None
            if ca and ca[4]:  # is_artifact or non_relational
                continue
            elif not ca and (cls.is_artifact_column(col_a, df_a[col_a]) or cls.is_non_relational_attribute(col_a)):
                continue

            # Constant column check
            val_a = df_a[col_a].dropna()
            if val_a.nunique() < 2 and len(val_a) >= 2:
                continue

            for col_b in df_b.columns:
                cb = col_cache.get((name_b, str(col_b))) if col_cache else None
                if cb and cb[4]:
                    continue
                elif not cb and (cls.is_artifact_column(col_b, df_b[col_b]) or cls.is_non_relational_attribute(col_b)):
                    continue

                # Fast disjoint set check: if columns share zero keys, reject in nanoseconds
                if ca and cb and not (ca[1] & cb[1]):
                    continue

                val_b = df_b[col_b].dropna()
                if val_b.nunique() < 2 and len(val_b) >= 2:
                    continue

                # 2. Type compatibility check
                type_compat, type_reason, s_dtype, t_dtype = cls._check_type_compatibility(
                    df_a[col_a], df_b[col_b]
                )
                if not type_compat:
                    continue

                # 3. Semantic / name compatibility check
                sem_match, sem_reason, name_score = cls._check_semantic_compatibility(
                    str(col_a), name_a, str(col_b), name_b
                )
                if not sem_match:
                    continue

                # 4. Calculate value metrics and overlap
                metrics = cls._calculate_column_metrics(
                    df_a[col_a], df_b[col_b],
                    name_a=name_a, col_a=str(col_a),
                    name_b=name_b, col_b=str(col_b),
                    cached_a=ca,
                    cached_b=cb,
                )

                # Must have at least 1 matching key value
                if metrics["matching_values_count"] == 0:
                    continue

                # When datasets have multiple records, reject isolated single-value coincidence
                if metrics["matching_values_count"] < 2 and min(len(val_a), len(val_b)) > 1:
                    continue

                overlap_pct = metrics["overlap_pct"]

                # Discard candidate if both sides have virtually zero overlap (< 5%)
                if overlap_pct < 5.0 and name_score < 30.0:
                    continue

                cardinality = metrics.get("cardinality", "Unknown")

                # 5. Evaluate confidence score, join risk, & generate warnings
                confidence, confidence_score, conf_label, join_risk, conf_reasons, warnings = cls._evaluate_confidence(
                    str(col_a), str(col_b), cardinality, metrics, sem_reason, name_score, type_compat
                )

                is_candidate_rel = bool(confidence_score < 70.0 or cardinality == "Many-to-Many")

                rel = Relationship(
                    source_dataset=name_a,
                    source_column=str(col_a),
                    target_dataset=name_b,
                    target_column=str(col_b),
                    data_type_compatible=type_compat,
                    source_dtype=s_dtype,
                    target_dtype=t_dtype,
                    value_overlap_pct=overlap_pct,
                    source_unique=metrics["source_unique"],
                    target_unique=metrics["target_unique"],
                    source_null_pct=metrics["source_null_pct"],
                    target_null_pct=metrics["target_null_pct"],
                    source_duplicates_count=metrics["source_dup_count"],
                    target_duplicates_count=metrics["target_dup_count"],
                    relationship_type=cardinality,
                    confidence=confidence,
                    confidence_reasons=conf_reasons,
                    warning_messages=warnings,
                    join_risk=join_risk,
                    cardinality=cardinality,
                    cardinality_symbol=metrics.get("cardinality_symbol", "N:M"),
                    direction=metrics.get("direction", ""),
                    matching_values_count=metrics.get("matching_values_count", 0),
                    unmatched_source_count=metrics.get("unmatched_source_count", 0),
                    unmatched_target_count=metrics.get("unmatched_target_count", 0),
                    source_null_count=metrics.get("source_null_count", 0),
                    target_null_count=metrics.get("target_null_count", 0),
                    source_pk_fk_hint=metrics.get("source_pk_fk_hint", ""),
                    target_pk_fk_hint=metrics.get("target_pk_fk_hint", ""),
                    cardinality_explanation=metrics.get("cardinality_explanation", ""),
                    safe_for_join=metrics.get("safe_for_join", True),
                    is_candidate=is_candidate_rel,
                )
                rel.confidence_score = confidence_score
                rel.estimated_inner_join_rows = metrics.get("estimated_inner_join_rows", 0)
                rel.estimated_left_join_rows = metrics.get("estimated_left_join_rows", 0)
                rel.join_expansion_factor = metrics.get("join_expansion_factor", 1.0)
                candidates.append(rel)

        return candidates

    @classmethod
    def _check_semantic_compatibility(
        cls,
        col_a: str,
        ds_a: str,
        col_b: str,
        ds_b: str,
    ) -> Tuple[bool, str, float]:
        """Verify whether two columns represent the same conceptual entity or candidate key.

        Returns (compatible: bool, reason: str, name_similarity_score: float).
        """
        norm_a = cls._normalize_col_name(col_a)
        norm_b = cls._normalize_col_name(col_b)

        # Reject non-relational attributes (measures, low-cardinality demographics, timestamps, descriptive text)
        if norm_a in cls.NON_RELATIONAL_ATTRIBUTES or norm_b in cls.NON_RELATIONAL_ATTRIBUTES:
            return False, f"Attribute ('{col_a}') is a measure, demographic dimension, or timestamp, not an entity join key", 0.0

        if norm_a in cls.DESCRIPTIVE_TEXT_NAMES or norm_b in cls.DESCRIPTIVE_TEXT_NAMES:
            return False, f"Descriptive text column ('{col_a}') is not a join key", 0.0

        concept_a, is_id_a = cls._extract_entity_and_concept(col_a, ds_a)
        concept_b, is_id_b = cls._extract_entity_and_concept(col_b, ds_b)

        # Exact normalized match: 'Customer ID' ↔ 'customer_id' ↔ 'CUSTOMER_ID'
        if norm_a == norm_b:
            if is_id_a or is_id_b or norm_a in cls.GENERIC_ID_NAMES:
                return True, f"Matching identifier column ('{col_a}' <-> '{col_b}')", 35.0
            if norm_a in cls.DOMAIN_NATURAL_KEYS:
                return True, f"Matching natural domain key ('{col_a}' <-> '{col_b}')", 32.0
            return True, f"Matching column name ('{col_a}' <-> '{col_b}')", 25.0

        # Concept match: 'cust_id' ↔ 'customer_id', 'emp_no' ↔ 'employee_id'
        if concept_a and concept_a == concept_b:
            return True, f"Normalized concept match ('{concept_a}')", 30.0

        # Foreign Key to Primary Key pattern: orders.customer_id vs customers.id
        clean_ds_a = cls._extract_clean_dataset_name(ds_a)
        clean_ds_b = cls._extract_clean_dataset_name(ds_b)

        if is_id_a and norm_b in cls.GENERIC_ID_NAMES:
            fk_base = concept_a.replace("_id", "")
            if fk_base in clean_ds_b or clean_ds_b.startswith(fk_base):
                return True, f"Foreign key '{col_a}' links to primary key of '{ds_b}'", 28.0

        if is_id_b and norm_a in cls.GENERIC_ID_NAMES:
            fk_base = concept_b.replace("_id", "")
            if fk_base in clean_ds_a or clean_ds_a.startswith(fk_base):
                return True, f"Primary key of '{ds_a}' links to foreign key '{col_b}'", 28.0

        # Both are generic IDs: id ↔ id
        if norm_a in cls.GENERIC_ID_NAMES and norm_b in cls.GENERIC_ID_NAMES:
            return True, f"Matching generic identifier columns ('{col_a}' <-> '{col_b}')", 22.0

        # Natural business domain keys: e.g. state, district, market, commodity, email, date
        if norm_a in cls.DOMAIN_NATURAL_KEYS and norm_b in cls.DOMAIN_NATURAL_KEYS:
            if norm_a == norm_b:
                return True, f"Matching natural domain key ('{col_a}')", 32.0

        # Related identifier patterns: user_id vs client_id
        if is_id_a and is_id_b:
            clean_a = norm_a.replace("_id", "").replace("_code", "").replace("_num", "")
            clean_b = norm_b.replace("_id", "").replace("_code", "").replace("_num", "")
            if len(clean_a) >= 3 and len(clean_b) >= 3 and (clean_a in clean_b or clean_b in clean_a):
                return True, f"Related identifier concept ('{col_a}' <-> '{col_b}')", 24.0

        # Candidate fallback for value profiling
        return False, f"Different column names ('{col_a}' vs '{col_b}')", 10.0

    @classmethod
    def _check_type_compatibility(
        cls,
        series_a: pd.Series,
        series_b: pd.Series,
    ) -> Tuple[bool, str, str, str]:
        """Verify datatype compatibility, allowing safe numerical-to-string normalization."""
        dtype_a = str(series_a.dtype)
        dtype_b = str(series_b.dtype)

        is_num_a = pd.api.types.is_numeric_dtype(series_a)
        is_num_b = pd.api.types.is_numeric_dtype(series_b)

        if is_num_a and is_num_b:
            return True, "Compatible numeric types", dtype_a, dtype_b

        is_str_a = pd.api.types.is_string_dtype(series_a) or pd.api.types.is_object_dtype(series_a)
        is_str_b = pd.api.types.is_string_dtype(series_b) or pd.api.types.is_object_dtype(series_b)

        if is_str_a and is_str_b:
            return True, "Compatible text/categorical types", dtype_a, dtype_b

        # Datetime compatibility
        is_dt_a = pd.api.types.is_datetime64_any_dtype(series_a)
        is_dt_b = pd.api.types.is_datetime64_any_dtype(series_b)
        if is_dt_a and is_dt_b:
            return True, "Compatible datetime types", dtype_a, dtype_b

        # Safe convertible normalization (e.g. integer 101 <-> string "101")
        if (is_num_a and is_str_b) or (is_str_a and is_num_b):
            str_series = series_b if is_str_b else series_a
            sample = str_series.dropna().astype(str).str.strip().head(50)
            if not sample.empty:
                numeric_count = sample.map(lambda v: v.replace(".", "", 1).replace("-", "", 1).isdigit()).sum()
                if numeric_count / len(sample) >= 0.7:
                    return True, "Safely convertible numeric-string types", dtype_a, dtype_b
            return False, "Incompatible types: text values cannot convert to numbers", dtype_a, dtype_b

        return False, f"Incompatible types ({dtype_a} vs {dtype_b})", dtype_a, dtype_b

    @classmethod
    def _normalize_key(cls, val: Any) -> Optional[str]:
        """Normalize a key value to string for fair, deterministic matching across types."""
        if pd.isna(val):
            return None
        if isinstance(val, (float, np.floating)):
            if float(val).is_integer():
                return str(int(val))
            return str(val).strip()
        s = str(val).strip()
        if s.lower() in cls.NULL_STRINGS:
            return None
        try:
            f = float(s)
            if f.is_integer() and "." in s:
                return str(int(f))
        except (ValueError, OverflowError):
            pass
        return s.lower()

    @classmethod
    def _calculate_column_metrics(
        cls,
        series_a: pd.Series,
        series_b: pd.Series,
        name_a: str = "Dataset A",
        col_a: str = "col_a",
        name_b: str = "Dataset B",
        col_b: str = "col_b",
        cached_a: Optional[Tuple] = None,
        cached_b: Optional[Tuple] = None,
    ) -> Dict[str, Any]:
        """Calculate uniqueness, nulls, duplicates, and normalized value overlap percentage on matching keys."""
        n_a = len(series_a)
        n_b = len(series_b)

        if cached_a is not None and cached_a[0] is not None:
            norm_a, set_a, null_count_a, source_dup_count, _ = cached_a
        else:
            norm_a = series_a.map(cls._normalize_key).dropna()
            set_a = set(norm_a.unique())
            null_count_a = int(n_a - len(norm_a))
            source_dup_count = int(norm_a.duplicated().sum())

        if cached_b is not None and cached_b[0] is not None:
            norm_b, set_b, null_count_b, target_dup_count, _ = cached_b
        else:
            norm_b = series_b.map(cls._normalize_key).dropna()
            set_b = set(norm_b.unique())
            null_count_b = int(n_b - len(norm_b))
            target_dup_count = int(norm_b.duplicated().sum())

        null_pct_a = round((null_count_a / n_a * 100.0) if n_a > 0 else 0.0, 1)
        null_pct_b = round((null_count_b / n_b * 100.0) if n_b > 0 else 0.0, 1)

        matching_keys = set_a.intersection(set_b)
        matching_values_count = len(matching_keys)
        unmatched_a = len(set_a - matching_keys)
        unmatched_b = len(set_b - matching_keys)

        min_set_size = min(len(set_a), len(set_b))
        overlap_pct = round((matching_values_count / min_set_size * 100.0) if min_set_size > 0 else 0.0, 1)

        clean_ds_a = cls._extract_clean_dataset_name(name_a)
        clean_ds_b = cls._extract_clean_dataset_name(name_b)

        if matching_values_count == 0:
            return {
                "source_null_pct": null_pct_a,
                "target_null_pct": null_pct_b,
                "source_null_count": null_count_a,
                "target_null_count": null_count_b,
                "source_unique": (source_dup_count == 0),
                "target_unique": (target_dup_count == 0),
                "source_unique_count": len(set_a),
                "target_unique_count": len(set_b),
                "source_dup_count": source_dup_count,
                "target_dup_count": target_dup_count,
                "overlap_pct": 0.0,
                "matching_values_count": 0,
                "unmatched_source_count": len(set_a),
                "unmatched_target_count": len(set_b),
                "cardinality": "Unknown",
                "cardinality_symbol": "?",
                "direction": f"{clean_ds_a}.{col_a} ? {clean_ds_b}.{col_b}",
                "cardinality_explanation": "No matching keys found between datasets.",
                "safe_for_join": False,
                "source_pk_fk_hint": "No Match",
                "target_pk_fk_hint": "No Match",
                "estimated_inner_join_rows": 0,
                "estimated_left_join_rows": n_a,
                "join_expansion_factor": 0.0,
                "matching_dups_source": 0,
                "matching_dups_target": 0,
            }

        # Deterministic key frequencies and join simulation on matching keys
        vc_a = norm_a.value_counts()
        vc_b = norm_b.value_counts()

        matched_rows_a = int(sum(vc_a[k] for k in matching_keys))
        matched_rows_b = int(sum(vc_b[k] for k in matching_keys))

        matching_dups_a = int(sum(vc_a[k] - 1 for k in matching_keys if vc_a[k] > 1))
        matching_dups_b = int(sum(vc_b[k] - 1 for k in matching_keys if vc_b[k] > 1))

        est_inner_rows = int(sum(vc_a[k] * vc_b[k] for k in matching_keys))
        unmatched_rows_a = int(n_a - matched_rows_a)
        est_left_rows = int(est_inner_rows + unmatched_rows_a)
        expansion_factor = round((est_inner_rows / max(1, n_a)), 2)

        a_is_unique = (matching_dups_a == 0)
        b_is_unique = (matching_dups_b == 0)

        # Overall column uniqueness
        source_unique = (source_dup_count == 0)
        target_unique = (target_dup_count == 0)

        if a_is_unique and b_is_unique:
            cardinality = "One-to-One"
            symbol = "1:1"
            direction = f"{clean_ds_a}.{col_a} <-> {clean_ds_b}.{col_b}"
            explanation = "Each record in Dataset A corresponds to at most one record in Dataset B and vice versa. Non-null keys are unique on both sides."
            src_pk_hint = "Candidate Unique Key"
            tgt_pk_hint = "Candidate Unique Key"
            safe_for_join = True
        elif a_is_unique and not b_is_unique:
            cardinality = "One-to-Many"
            symbol = "1:N"
            direction = f"{clean_ds_a}.{col_a} -> {clean_ds_b}.{col_b}"
            explanation = (
                f"One record in Dataset A can match multiple records in Dataset B (1:N structure). "
                f"Keys are unique in {clean_ds_a} and repeat {matching_dups_b} time(s) across matching records in {clean_ds_b}. "
                f"Estimated {est_inner_rows} rows in INNER JOIN."
            )
            src_pk_hint = "Candidate Unique Key (1-side)"
            tgt_pk_hint = "Repeated Key (N-side)"
            safe_for_join = True
        elif not a_is_unique and b_is_unique:
            cardinality = "Many-to-One"
            symbol = "N:1"
            direction = f"{clean_ds_a}.{col_a} -> {clean_ds_b}.{col_b}"
            explanation = (
                f"Multiple records in Dataset A match a single unique record in Dataset B (N:1 structure). "
                f"Keys repeat {matching_dups_a} time(s) in {clean_ds_a} referencing unique keys in {clean_ds_b}. "
                f"Estimated {est_inner_rows} rows in INNER JOIN."
            )
            src_pk_hint = "Repeated Key (N-side)"
            tgt_pk_hint = "Candidate Unique Key (1-side)"
            safe_for_join = True
        else:
            cardinality = "Many-to-Many"
            symbol = "M:N"
            direction = f"{clean_ds_a}.{col_a} <-> {clean_ds_b}.{col_b}"
            explanation = (
                f"The join key repeats in both datasets ({matching_dups_a} duplicate(s) in {clean_ds_a}, "
                f"{matching_dups_b} duplicate(s) in {clean_ds_b}). "
                f"Joining on this column will cause row multiplication (Cartesian product on repeated keys, "
                f"estimated {est_inner_rows} rows in INNER JOIN, {expansion_factor}x factor)."
            )
            src_pk_hint = "Repeated Join Key"
            tgt_pk_hint = "Repeated Join Key"
            safe_for_join = False

        return {
            "source_null_pct": null_pct_a,
            "target_null_pct": null_pct_b,
            "source_null_count": null_count_a,
            "target_null_count": null_count_b,
            "source_unique": a_is_unique,
            "target_unique": b_is_unique,
            "source_col_unique": source_unique,
            "target_col_unique": target_unique,
            "source_unique_count": len(set_a),
            "target_unique_count": len(set_b),
            "source_dup_count": source_dup_count,
            "target_dup_count": target_dup_count,
            "overlap_pct": overlap_pct,
            "matching_values_count": matching_values_count,
            "unmatched_source_count": unmatched_a,
            "unmatched_target_count": unmatched_b,
            "cardinality": cardinality,
            "cardinality_symbol": symbol,
            "direction": direction,
            "cardinality_explanation": explanation,
            "safe_for_join": safe_for_join,
            "source_pk_fk_hint": src_pk_hint,
            "target_pk_fk_hint": tgt_pk_hint,
            "estimated_inner_join_rows": est_inner_rows,
            "estimated_left_join_rows": est_left_rows,
            "join_expansion_factor": expansion_factor,
            "matching_dups_source": matching_dups_a,
            "matching_dups_target": matching_dups_b,
        }

    @classmethod
    def _evaluate_confidence(
        cls,
        col_a: str,
        col_b: str,
        cardinality: str,
        metrics: Dict[str, Any],
        sem_reason: str,
        name_score: float,
        type_compat: bool,
    ) -> Tuple[str, float, str, str, List[str], List[str]]:
        """Score confidence level (HIGH, MEDIUM, LOW), numeric score (0-100), join risk, reasons, and warnings."""
        conf_reasons: List[str] = [sem_reason]
        warnings: List[str] = []

        overlap = metrics["overlap_pct"]
        source_nulls = metrics["source_null_pct"]
        target_nulls = metrics["target_null_pct"]
        source_null_count = metrics["source_null_count"]
        target_null_count = metrics["target_null_count"]
        unmatched_a = metrics["unmatched_source_count"]
        unmatched_b = metrics["unmatched_target_count"]

        # 1. Base Score calculation
        # Name similarity: up to 35 pts
        # Overlap: up to 40 pts
        # Type compatibility: 15 pts
        # Key structure: 10 pts for unique key on at least one side
        overlap_score = min(40.0, (overlap / 100.0) * 40.0)
        type_score = 15.0 if type_compat else 0.0
        key_score = 10.0 if cardinality in ("One-to-One", "One-to-Many", "Many-to-One") else 0.0

        calc_score = round(name_score + overlap_score + type_score + key_score, 1)

        # Deduct score for excessive nulls (> 20%)
        max_null = max(source_nulls, target_nulls)
        if max_null > 20.0:
            calc_score = max(10.0, calc_score - 15.0)

        calc_score = min(99.0, max(5.0, calc_score))

        # Warnings for nulls
        if source_null_count > 0:
            warnings.append(f"{source_null_count} null value(s) ({source_nulls}%) in source column '{col_a}'.")
        if target_null_count > 0:
            warnings.append(f"{target_null_count} null value(s) ({target_nulls}%) in target column '{col_b}'.")

        # Warnings for unmatched rows
        if unmatched_a > 0:
            warnings.append(f"{unmatched_a} unique key(s) in source dataset have no matching record in target.")
        if unmatched_b > 0:
            warnings.append(f"{unmatched_b} unique key(s) in target dataset have no matching record in source.")

        # Duplicate key & Cardinality assessment
        if cardinality == "Many-to-Many":
            est_inner = metrics.get("estimated_inner_join_rows", 0)
            exp_factor = metrics.get("join_expansion_factor", 1.0)
            matching_dups_a = metrics.get("matching_dups_source", 0)
            matching_dups_b = metrics.get("matching_dups_target", 0)

            warnings.append(
                f"Many-to-Many warning: Duplicate key values exist in both datasets ({matching_dups_a} in source, {matching_dups_b} in target). "
                f"Joining on this key will multiply rows (estimated {est_inner} rows in INNER JOIN, {exp_factor}x factor)."
            )
            if exp_factor > 1.5:
                join_risk = "High Risk — Unsafe Many-to-Many (Row Multiplication Risk)"
                confidence = "LOW"
                conf_label = "Candidate Relationship (Unsafe Join)"
                conf_reasons.append(f"Non-unique keys on both sides ({exp_factor}x row multiplication risk)")
            else:
                join_risk = "Moderate Risk — Minor Key Duplication (M:N)"
                if calc_score >= 70.0 and max_null <= 20.0:
                    confidence = "MEDIUM"
                    conf_label = "Possible Relationship (Minor Duplication)"
                    conf_reasons.append(f"High key overlap ({overlap}%) with minor duplicate keys ({est_inner} rows estimated)")
                else:
                    confidence = "LOW"
                    conf_label = "Candidate Relationship"
                    conf_reasons.append("Non-unique keys on both sides")
        elif cardinality == "One-to-One":
            join_risk = "Low Risk — Safe 1:1 Linkage"
            if calc_score >= 70.0 and max_null <= 20.0:
                confidence = "HIGH"
                conf_label = "Strong Relationship"
                conf_reasons.append(f"Strong 1:1 value overlap ({overlap}%) with verified unique keys")
            elif calc_score >= 40.0:
                confidence = "MEDIUM"
                conf_label = "Possible Relationship"
                conf_reasons.append(f"Moderate 1:1 value overlap ({overlap}%)")
            else:
                confidence = "LOW"
                conf_label = "Candidate Relationship"
                conf_reasons.append(f"Low value overlap ({overlap}%)")
        elif cardinality in ("One-to-Many", "Many-to-One"):
            join_risk = "Low Risk — Safe Primary-Foreign Key Join"
            if calc_score >= 70.0 and max_null <= 20.0:
                confidence = "HIGH"
                conf_label = "Strong Relationship"
                conf_reasons.append(f"Strong key overlap ({overlap}%) with verified Primary-Foreign Key structure")
            elif calc_score >= 40.0:
                confidence = "MEDIUM"
                conf_label = "Possible Relationship"
                conf_reasons.append(f"Moderate value overlap ({overlap}%)")
            else:
                confidence = "LOW"
                conf_label = "Candidate Relationship"
                conf_reasons.append(f"Low value overlap ({overlap}%)")
        else:
            join_risk = "Medium Risk — Uncertain Linkage"
            confidence = "LOW"
            conf_label = "Candidate Relationship"
            conf_reasons.append("Uncertain relationship cardinality or insufficient matching keys")

        return confidence, calc_score, conf_label, join_risk, conf_reasons, warnings

    @classmethod
    def _resolve_ambiguities(cls, relationships: List[Relationship]) -> None:
        """Identify multiple possible join keys between the same pair of datasets."""
        pair_groups: Dict[Tuple[str, str], List[Relationship]] = {}
        for rel in relationships:
            key = tuple(sorted([rel.source_dataset, rel.target_dataset]))
            pair_groups.setdefault(key, []).append(rel)

        for (ds1, ds2), rels in pair_groups.items():
            if len(rels) > 1:
                clean_ds1 = cls._extract_clean_dataset_name(ds1)
                clean_ds2 = cls._extract_clean_dataset_name(ds2)
                ambig_id = f"{clean_ds1} <-> {clean_ds2}"

                for r in rels:
                    r.is_ambiguous = True
                    r.ambiguity_group = ambig_id
                    r.confidence_reasons.append("Multiple candidate keys detected between these datasets")

                # Recommend the best candidate (highest overlap, ID naming, uniqueness)
                def _score_key(r: Relationship) -> float:
                    score = r.value_overlap_pct
                    if r.relationship_type in ("One-to-One", "Many-to-One", "One-to-Many"):
                        score += 30.0
                    col_s = r.source_column.lower()
                    col_t = r.target_column.lower()
                    if "_id" in col_s or "_id" in col_t or col_s in cls.GENERIC_ID_NAMES:
                        score += 50.0
                    elif col_s in cls.DOMAIN_NATURAL_KEYS:
                        score += 20.0
                    if col_s == col_t:
                        score += 15.0
                    return score

                best_rel = max(rels, key=_score_key)
                for r in rels:
                    if r is best_rel:
                        r.is_recommended = True
                        r.is_candidate = False
                    else:
                        r.is_recommended = False
                        r.is_candidate = True

    # =========================================================================
    # SAFE EXECUTION & ROW EXPLOSION SAFEGUARD
    # =========================================================================

    @classmethod
    def execute_safe_join(
        cls,
        left_df: pd.DataFrame,
        left_name: str,
        left_key: str,
        right_df: pd.DataFrame,
        right_name: str,
        right_key: str,
        how: str = "inner",
        confidence: str = "HIGH",
        user_confirmed: bool = False,
    ) -> Tuple[bool, Optional[pd.DataFrame], JoinAudit, Optional[str]]:
        """Safely execute a join with row explosion protection and full audit logging."""
        rows_before = len(left_df)

        # 1. Safeguard: Check keys exist
        if left_key not in left_df.columns:
            audit = JoinAudit(
                left_dataset=left_name,
                left_key=left_key,
                right_dataset=right_name,
                right_key=right_key,
                join_type=how,
                confidence=confidence,
                overlap_percentage=0.0,
                rows_before=rows_before,
                rows_after=0,
                status="REJECTED_MISSING_KEY",
                notes=f"Key '{left_key}' not found in {left_name}",
            )
            return False, None, audit, f"Key '{left_key}' does not exist in dataset '{left_name}'."

        if right_key not in right_df.columns:
            audit = JoinAudit(
                left_dataset=left_name,
                left_key=left_key,
                right_dataset=right_name,
                right_key=right_key,
                join_type=how,
                confidence=confidence,
                overlap_percentage=0.0,
                rows_before=rows_before,
                rows_after=0,
                status="REJECTED_MISSING_KEY",
                notes=f"Key '{right_key}' not found in {right_name}",
            )
            return False, None, audit, f"Key '{right_key}' does not exist in dataset '{right_name}'."

        # 2. Check for unsafe duplicate keys (Many-to-Many)
        dup_left = left_df[left_key].dropna().duplicated().any()
        dup_right = right_df[right_key].dropna().duplicated().any()
        if dup_left and dup_right and not user_confirmed:
            audit = JoinAudit(
                left_dataset=left_name,
                left_key=left_key,
                right_dataset=right_name,
                right_key=right_key,
                join_type=how,
                confidence=confidence,
                overlap_percentage=0.0,
                rows_before=rows_before,
                rows_after=rows_before,
                status="REJECTED_DUPLICATE_KEYS",
                notes="Blocked unconfirmed Many-to-Many join with duplicate keys on both sides",
            )
            err_msg = (
                f"Warning: The join keys '{left_key}' and '{right_key}' contain duplicate values in both datasets. "
                "This may create a many-to-many join and increase the number of rows. Join cancelled until the relationship is confirmed."
            )
            return False, None, audit, err_msg

        # 3. Normalize join keys if types differ (e.g. int vs string)
        left_col = left_df[left_key]
        right_col = right_df[right_key]
        temp_left = left_df.copy()
        temp_right = right_df.copy()

        if pd.api.types.is_numeric_dtype(left_col) and (pd.api.types.is_string_dtype(right_col) or pd.api.types.is_object_dtype(right_col)):
            temp_right[right_key] = pd.to_numeric(temp_right[right_key], errors="coerce")
        elif pd.api.types.is_numeric_dtype(right_col) and (pd.api.types.is_string_dtype(left_col) or pd.api.types.is_object_dtype(left_col)):
            temp_left[left_key] = pd.to_numeric(temp_left[left_key], errors="coerce")

        # 4. Perform candidate merge
        try:
            merged = pd.merge(
                temp_left,
                temp_right,
                left_on=left_key,
                right_on=right_key,
                how=how,
                suffixes=("", f"_{Path(right_name).stem}"),
            )
        except Exception as e:
            audit = JoinAudit(
                left_dataset=left_name,
                left_key=left_key,
                right_dataset=right_name,
                right_key=right_key,
                join_type=how,
                confidence=confidence,
                overlap_percentage=0.0,
                rows_before=rows_before,
                rows_after=0,
                status="ERROR",
                notes=str(e),
            )
            return False, None, audit, f"Merge execution error: {str(e)}"

        rows_after = len(merged)
        row_ratio = rows_after / max(1, rows_before)

        # 5. Row Explosion Protection Check
        if rows_after > int(rows_before * 1.05) and not user_confirmed:
            audit = JoinAudit(
                left_dataset=left_name,
                left_key=left_key,
                right_dataset=right_name,
                right_key=right_key,
                join_type=how,
                confidence=confidence,
                overlap_percentage=100.0,
                rows_before=rows_before,
                rows_after=rows_after,
                row_ratio=row_ratio,
                status="REJECTED_ROW_EXPLOSION",
                notes=f"Row count expanded from {rows_before} to {rows_after} ({row_ratio:.2f}x)",
            )
            err_msg = (
                f"Row explosion detected: Join caused rows to multiply from {rows_before} to {rows_after} ({row_ratio:.2f}x). "
                "Join rejected to prevent cartesian product corruption."
            )
            return False, None, audit, err_msg

        # Successful join audit
        audit = JoinAudit(
            left_dataset=left_name,
            left_key=left_key,
            right_dataset=right_name,
            right_key=right_key,
            join_type=how,
            confidence=confidence,
            overlap_percentage=100.0,
            rows_before=rows_before,
            rows_after=rows_after,
            row_ratio=row_ratio,
            status="SUCCESS",
            notes="Safe join executed successfully",
        )
        return True, merged, audit, None
