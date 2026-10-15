"""Anomaly Query Engine for Phase 6 Natural Language Query Engine.

Reuses existing Phase 4 anomaly and outlier detection results.
Does NOT re-run heavy models and does NOT mutate or delete data rows.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


def compute_anomaly_query(
    df: pd.DataFrame,
    phase4_results: Optional[Dict[str, Any]] = None,
    dataset_name: Optional[str] = None,
    target_column: Optional[str] = None,
    show_records: bool = False,
) -> Dict[str, Any]:
    """Extract anomaly summaries or outlier records from Phase 4 results."""
    warnings: List[str] = []

    if df is None or df.empty:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": ["Dataset is empty."],
        }

    # 1. Attempt to pull from existing Phase 4 results
    # phase4_results can be SessionManager.get("anomaly_results", {})
    ds_key = dataset_name or "dataset.csv"
    p4_dataset_results = None

    if phase4_results:
        if ds_key in phase4_results:
            p4_dataset_results = phase4_results[ds_key]
        elif len(phase4_results) == 1:
            p4_dataset_results = list(phase4_results.values())[0]

    if p4_dataset_results and isinstance(p4_dataset_results, dict):
        iqr_res = p4_dataset_results.get("iqr")
        if_res = p4_dataset_results.get("isolation_forest")

        # Compile summary table
        breakdown_rows = []
        if iqr_res and hasattr(iqr_res, "column_results"):
            for col, cres in iqr_res.column_results.items():
                if target_column and col.lower() != target_column.lower():
                    continue
                breakdown_rows.append({
                    "Feature": col,
                    "Method": "IQR",
                    "Outlier Count": cres.outlier_count,
                    "Outlier Rate (%)": round(cres.outlier_percentage, 2),
                    "Lower Bound": round(cres.lower_bound, 2),
                    "Upper Bound": round(cres.upper_bound, 2),
                })
        elif iqr_res and isinstance(iqr_res, dict) and "column_results" in iqr_res:
            for col, cres in iqr_res["column_results"].items():
                if target_column and col.lower() != target_column.lower():
                    continue
                cnt = cres.get("outlier_count", 0) if isinstance(cres, dict) else getattr(cres, "outlier_count", 0)
                pct = cres.get("outlier_percentage", 0.0) if isinstance(cres, dict) else getattr(cres, "outlier_percentage", 0.0)
                breakdown_rows.append({
                    "Feature": col,
                    "Method": "IQR",
                    "Outlier Count": cnt,
                    "Outlier Rate (%)": round(pct, 2),
                })

        summary_df = pd.DataFrame(breakdown_rows)

        total_iqr_outliers = sum(r["Outlier Count"] for r in breakdown_rows) if breakdown_rows else 0
        if_anom_count = getattr(if_res, "anomaly_count", 0) if if_res else 0

        evidence = {
            "dataset": ds_key,
            "total_iqr_outliers": total_iqr_outliers,
            "isolation_forest_anomalies": if_anom_count,
            "columns_with_anomalies": [r["Feature"] for r in breakdown_rows if r["Outlier Count"] > 0],
            "phase4_reused": True,
        }

        # If user asked for actual records:
        if show_records:
            # Check flagged records or compute IQR masks
            outlier_indices = set()
            for col in [r["Feature"] for r in breakdown_rows if r["Outlier Count"] > 0]:
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    q1 = df[col].quantile(0.25)
                    q3 = df[col].quantile(0.75)
                    iqr = q3 - q1
                    low = q1 - 1.5 * iqr
                    high = q3 + 1.5 * iqr
                    outliers = df[(df[col] < low) | (df[col] > high)]
                    outlier_indices.update(outliers.index.tolist())

            if outlier_indices:
                rec_df = df.loc[sorted(list(outlier_indices))].head(25)
                return {
                    "result_type": "table",
                    "data": rec_df,
                    "columns": list(rec_df.columns),
                    "row_count": len(rec_df),
                    "evidence": {**evidence, "records_shown": len(rec_df), "total_anomalous_records": len(outlier_indices)},
                    "warnings": warnings,
                }

        return {
            "result_type": "table",
            "data": summary_df,
            "columns": list(summary_df.columns) if not summary_df.empty else ["Outlier Count"],
            "row_count": len(summary_df),
            "evidence": evidence,
            "warnings": warnings,
        }

    # 2. Fallback: Quick deterministic non-destructive IQR inspection
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    breakdown_rows = []
    outlier_idx = set()

    for col in num_cols:
        if any(term in col.lower() for term in ["unnamed", "id", "index"]):
            continue
        if target_column and col.lower() != target_column.lower():
            continue
        vals = df[col].dropna()
        if len(vals) < 4:
            continue
        q1 = float(vals.quantile(0.25))
        q3 = float(vals.quantile(0.75))
        iqr = q3 - q1
        low = q1 - 1.5 * iqr
        high = q3 + 1.5 * iqr
        outliers = vals[(vals < low) | (vals > high)]
        cnt = len(outliers)
        pct = (cnt / len(vals) * 100.0) if len(vals) > 0 else 0.0
        if cnt > 0:
            outlier_idx.update(outliers.index.tolist())
        breakdown_rows.append({
            "Feature": col,
            "Outlier Count": cnt,
            "Outlier Rate (%)": round(pct, 2),
            "Lower Bound": round(low, 2),
            "Upper Bound": round(high, 2),
        })

    summary_df = pd.DataFrame(breakdown_rows)
    total_outliers = sum(r["Outlier Count"] for r in breakdown_rows)

    evidence = {
        "dataset": ds_key,
        "total_anomalies": total_outliers,
        "columns_with_anomalies": [r["Feature"] for r in breakdown_rows if r["Outlier Count"] > 0],
        "phase4_reused": False,
    }

    if show_records and outlier_idx:
        rec_df = df.loc[sorted(list(outlier_idx))].head(25)
        return {
            "result_type": "table",
            "data": rec_df,
            "columns": list(rec_df.columns),
            "row_count": len(rec_df),
            "evidence": {**evidence, "records_shown": len(rec_df)},
            "warnings": warnings,
        }

    return {
        "result_type": "table",
        "data": summary_df,
        "columns": list(summary_df.columns),
        "row_count": len(summary_df),
        "evidence": evidence,
        "warnings": warnings,
    }
