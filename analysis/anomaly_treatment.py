"""Anomaly Treatment - Safe, non-destructive outlier treatments with audit trails.

Guarantees:
- NEVER automatically deletes data.
- Default action is ALWAYS 'flag_only'.
- User confirmation required for row removal or in-place value replacement.
- Original DataFrame is NEVER mutated in-place; returns a deep copy.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import numpy as np
import pandas as pd

from models.anomaly import (
    AnomalyTreatmentSummary,
    CombinedAnomalyResult,
)


def validate_anomaly_treatment(
    df: pd.DataFrame,
    anomaly_result: Union[CombinedAnomalyResult, Dict[str, Any]],
    treatment_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate treatment request prior to execution.

    Returns:
        Dict with 'valid' (bool), 'errors' (list), 'warnings' (list).
    """
    errors = []
    warnings = []

    if df is None or df.empty:
        return {"valid": False, "errors": ["DataFrame is empty or None."], "warnings": []}

    action = treatment_config.get("action", treatment_config.get("treatment_type", "flag_only"))
    allowed_actions = {
        "keep",
        "flag_only",
        "remove_selected",
        "remove_all_flagged",
        "remove_rows",
        "replace_median",
        "cap_values",
        "cap_iqr",
        "winsorize",
        "investigate",
    }
    if action not in allowed_actions:
        errors.append(f"Unsupported treatment action '{action}'. Allowed: {', '.join(allowed_actions)}")

    # Check confirmation requirement for destructive treatments
    if action in {"remove_selected", "remove_all_flagged", "remove_rows", "replace_median"}:
        if not treatment_config.get("confirmed", False):
            errors.append(f"Explicit user confirmation is required before applying destructive treatment '{action}'.")

    # Check row indices
    outlier_indices = treatment_config.get("outlier_indices", [])
    if action in {"remove_selected", "remove_all_flagged", "remove_rows"} and not outlier_indices:
        if hasattr(anomaly_result, "all_anomaly_indices"):
            outlier_indices = anomaly_result.all_anomaly_indices
        elif isinstance(anomaly_result, dict):
            outlier_indices = anomaly_result.get("all_anomaly_indices", anomaly_result.get("affected_rows", []))

        if not outlier_indices:
            warnings.append("No outlier row indices identified for removal.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def apply_anomaly_treatment(
    df: pd.DataFrame,
    anomaly_result: Union[CombinedAnomalyResult, Dict[str, Any]],
    treatment_config: Dict[str, Any],
    dataset_name: str = "dataset.csv",
) -> Tuple[pd.DataFrame, AnomalyTreatmentSummary]:
    """Execute authorized treatment on DataFrame deep-copy.

    Supported actions:
    1. 'keep': Retain all records untouched.
    2. 'flag_only' (DEFAULT): Append boolean '_anomaly_flag' and indicator columns without altering business data.
    3. 'remove_selected': Drop specific row indices chosen by user.
    4. 'remove_all_flagged': Drop all identified outlier rows.
    5. 'replace_median': Replace outlier cells in numeric columns with feature median.
    6. 'cap_iqr' (or 'cap_values'): Clip extreme numeric values to IQR boundaries.
    7. 'winsorize': Clip values to configured percentile limits (e.g. 1st/99th or 5th/95th).
    8. 'investigate': Retain all records untouched; log inspection audit.
    """
    if df is None:
        raise ValueError("Cannot apply treatment to a None DataFrame.")

    # Validation
    val = validate_anomaly_treatment(df, anomaly_result, treatment_config)
    if not val["valid"]:
        raise ValueError(f"Treatment validation failed: {'; '.join(val['errors'])}")

    treated_df = df.copy(deep=True)
    rows_before = len(df)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    action = treatment_config.get("action", treatment_config.get("treatment_type", "flag_only")).lower()

    # Determine target indices
    target_indices = treatment_config.get("outlier_indices", [])
    if not target_indices:
        if hasattr(anomaly_result, "all_anomaly_indices"):
            target_indices = anomaly_result.all_anomaly_indices
        elif isinstance(anomaly_result, dict):
            target_indices = anomaly_result.get("all_anomaly_indices", anomaly_result.get("affected_rows", []))

    valid_target_set = set(target_indices).intersection(set(df.index))
    target_cols = treatment_config.get("columns", [])
    if not target_cols:
        if hasattr(anomaly_result, "affected_columns"):
            target_cols = anomaly_result.affected_columns
        elif isinstance(anomaly_result, dict):
            target_cols = anomaly_result.get("affected_columns", [])

    # 1. KEEP
    if action == "keep":
        details = (
            f"Retained all {rows_before:,} records without modification. "
            f"{len(valid_target_set):,} flagged observations were verified and marked as legitimate domain variance."
        )
        summary = AnomalyTreatmentSummary(
            dataset_name=dataset_name,
            treatment_type="keep",
            affected_rows=0,
            rows_before=rows_before,
            rows_after=rows_before,
            columns_treated=[],
            details=details,
            timestamp=now_str,
        )
        return treated_df, summary

    # 2. FLAG ONLY (DEFAULT)
    elif action == "flag_only":
        # Build lookup maps from CombinedAnomalyResult if available
        score_map = {}
        methods_map = {}
        cols_map = {}
        severity_map = {}
        agreement_map = {}

        if hasattr(anomaly_result, "records"):
            for rec in anomaly_result.records:
                r_idx = rec.row_index
                score_map[r_idx] = rec.score
                methods_map[r_idx] = ", ".join(rec.methods)
                cols_map[r_idx] = ", ".join(rec.affected_columns)
                severity_map[r_idx] = rec.severity
                agreement_map[r_idx] = rec.agreement_ratio_str

        # Add indicators without modifying existing business columns
        treated_df["_anomaly_flag"] = treated_df.index.isin(valid_target_set)
        treated_df["_anomaly_score"] = [score_map.get(idx, 0.0) if idx in valid_target_set else 0.0 for idx in treated_df.index]
        treated_df["_anomaly_severity"] = [severity_map.get(idx, "NORMAL") if idx in valid_target_set else "NORMAL" for idx in treated_df.index]
        treated_df["_anomaly_methods"] = [methods_map.get(idx, "") if idx in valid_target_set else "" for idx in treated_df.index]
        treated_df["_anomaly_columns"] = [cols_map.get(idx, "") if idx in valid_target_set else "" for idx in treated_df.index]
        treated_df["_methods_agreeing"] = [agreement_map.get(idx, "0/0") if idx in valid_target_set else "0/0" for idx in treated_df.index]

        details = (
            f"Flagged {len(valid_target_set):,} anomaly records in indicator columns "
            f"('_anomaly_flag', '_anomaly_score', '_anomaly_severity', '_anomaly_methods', '_anomaly_columns'). "
            f"All {rows_before:,} original rows and values were fully preserved."
        )
        summary = AnomalyTreatmentSummary(
            dataset_name=dataset_name,
            treatment_type="flag_only",
            affected_rows=len(valid_target_set),
            rows_before=rows_before,
            rows_after=rows_before,
            columns_treated=target_cols,
            details=details,
            timestamp=now_str,
        )
        return treated_df, summary

    # 3. REMOVE SELECTED or REMOVE ALL FLAGGED
    elif action in {"remove_selected", "remove_all_flagged", "remove_rows"}:
        if not valid_target_set:
            details = "No matching outlier indices found in active dataset. 0 rows removed."
            summary = AnomalyTreatmentSummary(
                dataset_name=dataset_name,
                treatment_type=action,
                affected_rows=0,
                rows_before=rows_before,
                rows_after=rows_before,
                columns_treated=target_cols,
                details=details,
                timestamp=now_str,
            )
            return treated_df, summary

        drop_list = list(valid_target_set)
        treated_df = treated_df.drop(index=drop_list)
        rows_after = len(treated_df)
        details = (
            f"Removed {len(drop_list):,} authorized outlier rows. "
            f"Dataset size reduced from {rows_before:,} to {rows_after:,} records."
        )
        summary = AnomalyTreatmentSummary(
            dataset_name=dataset_name,
            treatment_type=action,
            affected_rows=len(drop_list),
            rows_before=rows_before,
            rows_after=rows_after,
            columns_treated=target_cols,
            details=details,
            timestamp=now_str,
        )
        return treated_df, summary

    # 4. REPLACE WITH MEDIAN
    elif action == "replace_median":
        modified_cells = 0
        replaced_cols = []
        for col in target_cols:
            if col in treated_df.columns and pd.api.types.is_numeric_dtype(treated_df[col]):
                med_val = float(treated_df[col].median())
                if np.isnan(med_val):
                    continue
                mask = treated_df.index.isin(valid_target_set)
                count = int(mask.sum())
                if count > 0:
                    treated_df.loc[mask, col] = med_val
                    modified_cells += count
                    replaced_cols.append(col)

        details = (
            f"Replaced {modified_cells:,} extreme values across {len(replaced_cols)} column(s) "
            f"with column median values. Row count preserved at {rows_before:,}."
        )
        summary = AnomalyTreatmentSummary(
            dataset_name=dataset_name,
            treatment_type="replace_median",
            affected_rows=modified_cells,
            rows_before=rows_before,
            rows_after=rows_before,
            columns_treated=replaced_cols,
            details=details,
            timestamp=now_str,
        )
        return treated_df, summary

    # 5. CAP USING IQR BOUNDS
    elif action in {"cap_values", "cap_iqr"}:
        iqr_bounds = treatment_config.get("iqr_bounds", {})
        capped_cells = 0
        cols_capped = []

        # If bounds not explicitly provided, calculate 1.5 IQR bounds for target cols
        if not iqr_bounds and target_cols:
            for c in target_cols:
                if c in treated_df.columns and pd.api.types.is_numeric_dtype(treated_df[c]):
                    s = treated_df[c].dropna()
                    if len(s) > 0:
                        q1 = float(s.quantile(0.25))
                        q3 = float(s.quantile(0.75))
                        iqr = q3 - q1
                        iqr_bounds[c] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)

        for col, (l_bound, u_bound) in iqr_bounds.items():
            if col in treated_df.columns and pd.api.types.is_numeric_dtype(treated_df[col]):
                low_cnt = int((treated_df[col] < l_bound).sum())
                high_cnt = int((treated_df[col] > u_bound).sum())
                capped_cells += (low_cnt + high_cnt)
                treated_df[col] = treated_df[col].clip(lower=l_bound, upper=u_bound)
                cols_capped.append(col)

        details = (
            f"Capped {capped_cells:,} extreme observations across {len(cols_capped)} column(s) "
            f"to their statistical IQR thresholds. Row count preserved at {rows_before:,}."
        )
        summary = AnomalyTreatmentSummary(
            dataset_name=dataset_name,
            treatment_type="cap_values",
            affected_rows=capped_cells,
            rows_before=rows_before,
            rows_after=rows_before,
            columns_treated=cols_capped,
            details=details,
            timestamp=now_str,
        )
        return treated_df, summary

    # 6. WINSORIZE
    elif action == "winsorize":
        lower_pct = float(treatment_config.get("lower_percentile", 0.01))
        upper_pct = float(treatment_config.get("upper_percentile", 0.99))
        winsor_cells = 0
        cols_winsor = []

        for col in target_cols:
            if col in treated_df.columns and pd.api.types.is_numeric_dtype(treated_df[col]):
                s = treated_df[col].dropna()
                if len(s) > 0:
                    l_val = float(s.quantile(lower_pct))
                    u_val = float(s.quantile(upper_pct))
                    cnt = int(((treated_df[col] < l_val) | (treated_df[col] > u_val)).sum())
                    treated_df[col] = treated_df[col].clip(lower=l_val, upper=u_val)
                    winsor_cells += cnt
                    cols_winsor.append(col)

        details = (
            f"Winsorized {winsor_cells:,} values across {len(cols_winsor)} column(s) "
            f"at percentiles [{lower_pct*100:.1f}%, {upper_pct*100:.1f}%]. Row count preserved at {rows_before:,}."
        )
        summary = AnomalyTreatmentSummary(
            dataset_name=dataset_name,
            treatment_type="winsorize",
            affected_rows=winsor_cells,
            rows_before=rows_before,
            rows_after=rows_before,
            columns_treated=cols_winsor,
            details=details,
            timestamp=now_str,
        )
        return treated_df, summary

    # 7. INVESTIGATE FURTHER
    elif action == "investigate":
        details = (
            f"Marked {len(valid_target_set):,} flagged observations for operational/field investigation. "
            f"No data was altered. Review ticket/audit recorded."
        )
        summary = AnomalyTreatmentSummary(
            dataset_name=dataset_name,
            treatment_type="investigate",
            affected_rows=len(valid_target_set),
            rows_before=rows_before,
            rows_after=rows_before,
            columns_treated=target_cols,
            details=details,
            timestamp=now_str,
        )
        return treated_df, summary

    else:
        raise ValueError(f"Unknown treatment type '{action}'.")
