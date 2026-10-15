"""Comparison Engine for Phase 6 Natural Language Query Engine.

Computes deterministic comparisons between entities, groups, and temporal periods.
Calculates absolute changes, percentage shifts, and ratio metrics.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


def compare_groups(
    df: pd.DataFrame,
    group_col: str,
    metric_col: str,
    groups: Optional[List[str]] = None,
    aggregation: str = "mean",
) -> Dict[str, Any]:
    """Compare a metric across categorical groups or specified pairs.
    
    Returns structured comparison result.
    """
    if df is None or df.empty:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": ["DataFrame is empty."],
        }

    if group_col not in df.columns or metric_col not in df.columns:
        return {
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [f"Columns '{group_col}' or '{metric_col}' not found."],
        }

    agg = aggregation if aggregation in ("mean", "sum", "median", "count") else "mean"
    calc_df = df.copy()
    if agg != "count":
        calc_df[metric_col] = pd.to_numeric(calc_df[metric_col], errors="coerce")

    # If specific groups requested
    if groups and len(groups) >= 2:
        calc_df = calc_df[calc_df[group_col].astype(str).str.lower().isin([str(g).lower() for g in groups])]

    grouped = calc_df.groupby(group_col, observed=False)[metric_col].agg(agg).reset_index()
    grouped.columns = [group_col, f"{agg}_{metric_col}"]
    grouped = grouped.sort_values(by=f"{agg}_{metric_col}", ascending=False).reset_index(drop=True)

    evidence: Dict[str, Any] = {
        "group_col": group_col,
        "metric_col": metric_col,
        "aggregation": agg,
        "groups_compared": list(grouped[group_col]),
    }

    if len(grouped) >= 2:
        top_name = grouped.iloc[0][group_col]
        top_val = float(grouped.iloc[0][f"{agg}_{metric_col}"])
        second_name = grouped.iloc[1][group_col]
        second_val = float(grouped.iloc[1][f"{agg}_{metric_col}"])

        diff = top_val - second_val
        pct_diff = (diff / second_val * 100.0) if second_val != 0 else 0.0

        evidence["top_group"] = top_name
        evidence["top_value"] = round(top_val, 2)
        evidence["second_group"] = second_name
        evidence["second_value"] = round(second_val, 2)
        evidence["absolute_difference"] = round(diff, 2)
        evidence["percentage_difference"] = round(pct_diff, 2)

    return {
        "result_type": "table",
        "data": grouped,
        "columns": list(grouped.columns),
        "row_count": len(grouped),
        "evidence": evidence,
        "warnings": [],
    }


def compare_dates(
    df: pd.DataFrame,
    date_col: str,
    metric_col: str,
    date_a: Optional[str] = None,
    date_b: Optional[str] = None,
    aggregation: str = "mean",
) -> Dict[str, Any]:
    """Compare a metric between two dates or time intervals."""
    if df is None or df.empty or date_col not in df.columns or metric_col not in df.columns:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": ["Insufficient data or missing columns for date comparison."],
        }

    calc_df = df.copy()
    calc_df[date_col] = pd.to_datetime(calc_df[date_col], errors="coerce")
    calc_df[metric_col] = pd.to_numeric(calc_df[metric_col], errors="coerce")
    calc_df = calc_df.dropna(subset=[date_col, metric_col])

    if calc_df.empty:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": ["No valid date and numeric values found for comparison."],
        }

    agg = aggregation if aggregation in ("mean", "sum", "median") else "mean"

    # If specific dates provided
    if date_a and date_b:
        dt_a = pd.to_datetime(date_a, errors="coerce")
        dt_b = pd.to_datetime(date_b, errors="coerce")
        val_a = calc_df[calc_df[date_col] == dt_a][metric_col].agg(agg) if not pd.isna(dt_a) else None
        val_b = calc_df[calc_df[date_col] == dt_b][metric_col].agg(agg) if not pd.isna(dt_b) else None
    else:
        # Default: compare earliest date vs latest date in dataset
        earliest_dt = calc_df[date_col].min()
        latest_dt = calc_df[date_col].max()
        val_a = calc_df[calc_df[date_col] == earliest_dt][metric_col].agg(agg)
        val_b = calc_df[calc_df[date_col] == latest_dt][metric_col].agg(agg)
        date_a = str(earliest_dt.date())
        date_b = str(latest_dt.date())

    v_a = float(val_a) if val_a is not None and not pd.isna(val_a) else 0.0
    v_b = float(val_b) if val_b is not None and not pd.isna(val_b) else 0.0
    change = v_b - v_a
    pct_change = (change / v_a * 100.0) if v_a != 0 else 0.0

    res_df = pd.DataFrame([
        {"Period": str(date_a), f"{agg}_{metric_col}": round(v_a, 2)},
        {"Period": str(date_b), f"{agg}_{metric_col}": round(v_b, 2)},
        {"Period": "Absolute Change", f"{agg}_{metric_col}": round(change, 2)},
        {"Period": "Percentage Change (%)", f"{agg}_{metric_col}": round(pct_change, 2)},
    ])

    evidence = {
        "date_a": str(date_a),
        "value_a": round(v_a, 2),
        "date_b": str(date_b),
        "value_b": round(v_b, 2),
        "absolute_change": round(change, 2),
        "percentage_change": round(pct_change, 2),
        "direction": "increased" if change > 0 else ("decreased" if change < 0 else "remained flat"),
    }

    return {
        "result_type": "table",
        "data": res_df,
        "columns": list(res_df.columns),
        "row_count": len(res_df),
        "evidence": evidence,
        "warnings": [],
    }
