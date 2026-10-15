"""Aggregation Engine for Phase 6 Natural Language Query Engine.

Computes safe, deterministic single-column and grouped aggregations:
count, sum, mean, median, min, max, std, nunique, with sorting, limits, and offsets.
"""

from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np


def compute_aggregation(
    df: pd.DataFrame,
    column: Optional[str] = None,
    aggregation: str = "mean",
    group_by: Optional[List[str]] = None,
    sort: Optional[str] = None,  # "descending", "ascending", or None
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute mathematical aggregation over a DataFrame safely.
    
    Returns structured execution result:
    {
        "result_type": "table" | "scalar",
        "data": DataFrame | scalar,
        "columns": List[str],
        "row_count": int,
        "evidence": Dict[str, Any],
        "warnings": List[str]
    }
    """
    warnings: List[str] = []

    if df is None or df.empty:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {"message": "DataFrame is empty."},
            "warnings": ["The dataset contains no rows."],
        }

    agg_clean = (aggregation or "mean").lower()
    if agg_clean in ("avg", "average"):
        agg_clean = "mean"

    # CASE A: Group-by aggregation (e.g. Market by average price)
    if group_by and len(group_by) > 0:
        valid_groups = [g for g in group_by if g in df.columns]
        if not valid_groups:
            warnings.append(f"Group columns {group_by} not found in dataset. Falling back to whole-dataset aggregation.")
            return compute_aggregation(df, column, aggregation, group_by=None, sort=sort, limit=limit, offset=offset)

        if not column or column not in df.columns:
            # If no measure column specified, count records per group
            res_series = df.groupby(valid_groups, observed=False).size().reset_index(name="record_count")
            measure_label = "record_count"
        else:
            measure_label = f"{agg_clean}_{column}"
            # Ensure column is numeric for numeric aggregations
            if agg_clean in ("mean", "median", "sum", "std") and not pd.api.types.is_numeric_dtype(df[column]):
                # Attempt conversion
                converted = pd.to_numeric(df[column], errors="coerce")
                if converted.dropna().empty:
                    warnings.append(f"Column '{column}' cannot be converted to numeric for '{agg_clean}'. Counting occurrences instead.")
                    res_series = df.groupby(valid_groups, observed=False)[column].count().reset_index(name=f"count_{column}")
                    measure_label = f"count_{column}"
                else:
                    df_calc = df.copy()
                    df_calc[column] = converted
                    res_series = df_calc.groupby(valid_groups, observed=False)[column].agg(agg_clean).reset_index(name=measure_label)
            else:
                res_series = df.groupby(valid_groups, observed=False)[column].agg(agg_clean).reset_index(name=measure_label)

        # Apply sorting
        if sort in ("descending", "desc"):
            res_series = res_series.sort_values(by=measure_label, ascending=False)
        elif sort in ("ascending", "asc"):
            res_series = res_series.sort_values(by=measure_label, ascending=True)

        total_rows = len(res_series)

        # Apply offset if requested (e.g. "second highest" -> offset=1, limit=1)
        if offset is not None and offset > 0:
            res_series = res_series.iloc[offset:]

        # Apply limit
        if limit is not None and limit > 0:
            res_series = res_series.head(limit)

        evidence = {
            "aggregation": agg_clean,
            "measure_column": column or "records",
            "group_columns": valid_groups,
            "total_groups": total_rows,
            "returned_rows": len(res_series),
            "top_record": res_series.iloc[0].to_dict() if not res_series.empty else {},
        }

        return {
            "result_type": "table",
            "data": res_series.reset_index(drop=True),
            "columns": list(res_series.columns),
            "row_count": len(res_series),
            "evidence": evidence,
            "warnings": warnings,
        }

    # CASE B: Whole-dataset single aggregation (e.g. "What is the average modal price?")
    if not column or column not in df.columns:
        if agg_clean == "count":
            val = int(len(df))
            return {
                "result_type": "scalar",
                "data": val,
                "columns": ["record_count"],
                "row_count": 1,
                "evidence": {"value": val, "aggregation": "count", "column": "all_rows"},
                "warnings": warnings,
            }
        # Do not silently fall back to the first numeric column
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        return {
            "result_type": "empty",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {
                "message": f"No valid numerical column specified for aggregation '{agg_clean}'. Available numerical columns: {num_cols}",
                "available_columns": list(df.columns),
                "numeric_columns": num_cols,
            },
            "warnings": [f"Cannot compute '{agg_clean}' without a valid numerical column. Available columns: {list(df.columns)}"],
        }

    series = df[column]
    if agg_clean in ("mean", "median", "sum", "std", "min", "max") and not pd.api.types.is_numeric_dtype(series):
        series = pd.to_numeric(series, errors="coerce")

    series_valid = series.dropna()
    if series_valid.empty:
        return {
            "result_type": "scalar",
            "data": None,
            "columns": [column],
            "row_count": 0,
            "evidence": {"message": f"Column '{column}' contains no valid values."},
            "warnings": [f"No valid values found in '{column}'."],
        }

    if agg_clean == "mean":
        val = float(series_valid.mean())
    elif agg_clean == "median":
        val = float(series_valid.median())
    elif agg_clean == "sum":
        val = float(series_valid.sum())
    elif agg_clean == "min":
        val = float(series_valid.min()) if pd.api.types.is_numeric_dtype(series_valid) else series_valid.min()
    elif agg_clean == "max":
        val = float(series_valid.max()) if pd.api.types.is_numeric_dtype(series_valid) else series_valid.max()
    elif agg_clean == "std":
        val = float(series_valid.std())
    elif agg_clean == "nunique":
        val = int(series_valid.nunique())
    elif agg_clean == "count":
        val = int(len(series_valid))
    else:
        val = float(series_valid.mean())
        warnings.append(f"Unknown aggregation '{agg_clean}'; defaulted to mean.")

    # Round floats nicely
    if isinstance(val, float):
        val = round(val, 4)

    evidence = {
        "column": column,
        "aggregation": agg_clean,
        "value": val,
        "count_valid": int(len(series_valid)),
        "count_null": int(df[column].isna().sum()),
    }

    # Also build a single-row 1-column or 2-column DataFrame for uniform table rendering
    res_df = pd.DataFrame([{f"{agg_clean}_{column}": val}])

    return {
        "result_type": "scalar",
        "data": val,
        "table_view": res_df,
        "columns": [f"{agg_clean}_{column}"],
        "row_count": 1,
        "evidence": evidence,
        "warnings": warnings,
    }
