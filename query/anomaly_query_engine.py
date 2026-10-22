"""Anomaly Query Engine for Phase 6 Natural Language Query Engine.

Reuses existing Phase 4 anomaly and outlier detection results.
Does NOT re-run heavy models and does NOT mutate or delete data rows.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


def compute_dual_outlier_comparison(
    df: pd.DataFrame,
    target_column: Optional[str] = None,
    dataset_name: Optional[str] = None,
    show_records: bool = True,
    z_threshold: float = 3.0,
) -> Dict[str, Any]:
    """Execute dual IQR (1.5x) and Z-score (|Z| > threshold) outlier detection and comparison."""
    warnings: List[str] = []
    ds_key = dataset_name or "dataset.csv"

    if df is None or df.empty:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": ["Dataset is empty."],
        }

    # Resolve target numeric column
    col = target_column
    if not col or col not in df.columns:
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not any(term in c.lower() for term in ["id", "index", "unnamed"])]
        monetary_cols = [c for c in num_cols if any(term in c.lower() for term in ["amount", "revenue", "sales", "price", "income", "spend", "cost"])]
        col = monetary_cols[0] if monetary_cols else (num_cols[0] if num_cols else None)

    if not col or col not in df.columns:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {"message": f"No valid numerical column found for outlier comparison (target: '{target_column}')."},
            "warnings": [f"Column '{target_column}' is missing or non-numeric."],
        }

    s = pd.to_numeric(df[col], errors="coerce")
    vals = s.dropna()
    total_rows = len(df)
    n_valid = len(vals)
    missing_count = total_rows - n_valid

    if n_valid < 4:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {"message": f"Insufficient non-null observations in '{col}' for statistical outlier detection (N={n_valid}, minimum 4 required)."},
            "warnings": [f"Insufficient data in '{col}'."],
        }

    # 1. IQR Method (Q1 - 1.5*IQR, Q3 + 1.5*IQR)
    q1 = float(vals.quantile(0.25))
    q3 = float(vals.quantile(0.75))
    iqr = q3 - q1
    iqr_low = q1 - 1.5 * iqr
    iqr_high = q3 + 1.5 * iqr
    iqr_mask = (vals < iqr_low) | (vals > iqr_high)
    iqr_flagged_idx = set(vals[iqr_mask].index.tolist())

    # 2. Z-Score Method (|Z| > threshold)
    mean_val = float(vals.mean())
    std_val = float(vals.std(ddof=1))

    if std_val == 0.0 or np.isnan(std_val):
        z_flagged_idx = set()
        warnings.append(f"Standard deviation for '{col}' is 0.0 (constant values); Z-scores cannot be computed.")
        z_low = mean_val
        z_high = mean_val
    else:
        z_scores = (vals - mean_val) / std_val
        z_mask = z_scores.abs() > z_threshold
        z_flagged_idx = set(vals[z_mask].index.tolist())
        z_low = mean_val - z_threshold * std_val
        z_high = mean_val + z_threshold * std_val

    # 3. Overlap & Disagreement
    overlap_idx = iqr_flagged_idx & z_flagged_idx
    iqr_only_idx = iqr_flagged_idx - z_flagged_idx
    z_only_idx = z_flagged_idx - iqr_flagged_idx
    all_flagged_idx = sorted(list(iqr_flagged_idx | z_flagged_idx))

    # 4. Distribution Skewness & Mathematical Explanation
    skew_val = float(vals.skew())
    if skew_val > 1.0:
        dist_shape = f"heavily right-skewed (skewness = {skew_val:.2f})"
    elif skew_val < -1.0:
        dist_shape = f"heavily left-skewed (skewness = {skew_val:.2f})"
    elif abs(skew_val) > 0.5:
        dist_shape = f"moderately skewed (skewness = {skew_val:.2f})"
    else:
        dist_shape = f"approximately symmetric (skewness = {skew_val:.2f})"

    if abs(skew_val) > 0.5:
        disagreement_explanation = (
            f"Method disagreement is driven by distribution skewness: '{col}' is {dist_shape}. "
            f"The Z-score method assumes an approximately normal distribution and relies on the sample mean ({mean_val:.2f}) "
            f"and sample standard deviation ({std_val:.2f}), both of which are pulled and inflated by extreme values. "
            f"This variance inflation stretches the +/- {z_threshold} std boundary, causing Z-score to miss extreme records that the non-parametric "
            f"IQR method (based on median and quartiles Q1={q1:.2f}, Q3={q3:.2f}, IQR={iqr:.2f}) reliably identifies."
        )
        recommendation = (
            f"The IQR method is more appropriate for '{col}' because the empirical distribution is {dist_shape} and non-normal. "
            f"Non-parametric quantile fences (lower: {iqr_low:.2f}, upper: {iqr_high:.2f}) do not assume normality and resist distortion "
            f"from extreme transactions. However, neither method is universally superior; business context must determine whether flagged records "
            f"reflect valid high-value orders or data anomalies."
        )
    else:
        disagreement_explanation = (
            f"Method comparison shows high alignment because '{col}' has an {dist_shape}. "
            f"For normal distributions, 1.5 * IQR corresponds to approximately +/- 2.7 standard deviations, making IQR slightly more sensitive "
            f"than the conservative |Z| > {z_threshold:.1f} cutoff."
        )
        recommendation = (
            f"Both methods are viable for '{col}' due to the {dist_shape}. "
            f"Use IQR for greater sensitivity (flagging values beyond ~2.7 std), or Z-score (|Z| > {z_threshold:.1f}) for conservative detection "
            f"of extreme deviations. Selection should align with the required tolerance for false-positive vs false-negative alerts."
        )

    # 5. Build Summary Comparison Table
    summary_rows = [
        {
            "Method / Comparison": "IQR Method",
            "Threshold": "Q1 - 1.5*IQR to Q3 + 1.5*IQR",
            "Lower Bound": round(iqr_low, 2),
            "Upper Bound": round(iqr_high, 2),
            "Flagged Outliers": len(iqr_flagged_idx),
            "Outlier Rate (%)": round(len(iqr_flagged_idx) / n_valid * 100, 2),
            "Basis": "Non-parametric (quartiles Q1/Q3)",
        },
        {
            "Method / Comparison": f"Z-Score Method (|Z| > {z_threshold:.1f})",
            "Threshold": f"Absolute Z-Score > {z_threshold:.1f}",
            "Lower Bound": round(z_low, 2) if std_val > 0 else 0.0,
            "Upper Bound": round(z_high, 2) if std_val > 0 else 0.0,
            "Flagged Outliers": len(z_flagged_idx),
            "Outlier Rate (%)": round(len(z_flagged_idx) / n_valid * 100, 2) if std_val > 0 else 0.0,
            "Basis": f"Parametric mean ({mean_val:.2f}) +/- {z_threshold:.1f} std ({std_val:.2f})",
        },
        {
            "Method / Comparison": "Overlapping Outliers",
            "Threshold": "Flagged by Both Methods",
            "Lower Bound": max(iqr_low, z_low) if std_val > 0 else iqr_low,
            "Upper Bound": min(iqr_high, z_high) if std_val > 0 else iqr_high,
            "Flagged Outliers": len(overlap_idx),
            "Outlier Rate (%)": round(len(overlap_idx) / n_valid * 100, 2),
            "Basis": "Intersection of IQR and Z-score flagged indices",
        },
        {
            "Method / Comparison": "IQR-Only Outliers",
            "Threshold": f"Outside IQR, within Z-Score +/- {z_threshold:.0f} std",
            "Lower Bound": round(iqr_low, 2),
            "Upper Bound": round(iqr_high, 2),
            "Flagged Outliers": len(iqr_only_idx),
            "Outlier Rate (%)": round(len(iqr_only_idx) / n_valid * 100, 2),
            "Basis": "Detected only by IQR due to non-parametric sensitivity",
        },
        {
            "Method / Comparison": "Z-Score-Only Outliers",
            "Threshold": f"Outside Z-Score +/- {z_threshold:.0f} std, within IQR",
            "Lower Bound": round(z_low, 2) if std_val > 0 else 0.0,
            "Upper Bound": round(z_high, 2) if std_val > 0 else 0.0,
            "Flagged Outliers": len(z_only_idx),
            "Outlier Rate (%)": round(len(z_only_idx) / n_valid * 100, 2),
            "Basis": "Detected only by Z-Score",
        },
    ]
    summary_df = pd.DataFrame(summary_rows)

    evidence = {
        "dataset": ds_key,
        "target_column": col,
        "total_rows": total_rows,
        "valid_observations": n_valid,
        "missing_count": missing_count,
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "iqr": round(iqr, 2),
        "iqr_lower_bound": round(iqr_low, 2),
        "iqr_upper_bound": round(iqr_high, 2),
        "mean": round(mean_val, 2),
        "std": round(std_val, 2),
        "z_threshold": z_threshold,
        "skewness": round(skew_val, 4),
        "distribution_shape": dist_shape,
        "iqr_outliers": len(iqr_flagged_idx),
        "zscore_outliers": len(z_flagged_idx),
        "overlap_count": len(overlap_idx),
        "iqr_only_count": len(iqr_only_idx),
        "zscore_only_count": len(z_only_idx),
        "disagreement_explanation": disagreement_explanation,
        "recommendation": recommendation,
        "summary_table": summary_rows,
    }

    # 6. Flagged Records Table (stable row indices)
    if all_flagged_idx:
        rec_rows = []
        for idx in all_flagged_idx:
            row_dict = df.loc[idx].to_dict()
            val_num = vals.loc[idx] if idx in vals.index else None
            z_val = round(float((val_num - mean_val) / std_val), 2) if (std_val > 0 and val_num is not None) else None
            if idx in overlap_idx:
                status = "Both (IQR & Z-score)"
            elif idx in iqr_only_idx:
                status = "IQR Only"
            else:
                status = "Z-score Only"

            flagged_entry = {
                "Row_Index": int(idx),
                col: val_num,
                "Outlier_Status": status,
                "Z_Score": z_val,
            }
            # Prioritize identifier, entity, and name columns (e.g. Customer_ID, Customer_Name)
            id_cols = [c for c in df.columns if any(k in c.lower() for k in ["id", "key", "code", "name", "customer", "order"])]
            other_cols = [c for c in df.columns if c not in id_cols]
            for c_other in (id_cols + other_cols):
                if c_other != col and c_other not in flagged_entry and len(flagged_entry) < 8:
                    flagged_entry[c_other] = row_dict.get(c_other)
            rec_rows.append(flagged_entry)

        rec_df = pd.DataFrame(rec_rows)
        evidence["records_shown"] = len(rec_df)
        evidence["total_flagged_records"] = len(all_flagged_idx)

        # Return records table as main data if show_records is True, with summary preserved in evidence
        if show_records:
            return {
                "result_type": "table",
                "data": rec_df,
                "columns": list(rec_df.columns),
                "row_count": len(rec_df),
                "evidence": evidence,
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


def compute_anomaly_query(
    df: pd.DataFrame,
    phase4_results: Optional[Dict[str, Any]] = None,
    dataset_name: Optional[str] = None,
    target_column: Optional[str] = None,
    show_records: bool = False,
    compare_methods: bool = False,
    z_threshold: float = 3.0,
) -> Dict[str, Any]:
    """Extract anomaly summaries or outlier records from Phase 4 results, or run dual comparison."""
    if compare_methods:
        return compute_dual_outlier_comparison(
            df=df,
            target_column=target_column,
            dataset_name=dataset_name,
            show_records=show_records,
            z_threshold=z_threshold,
        )

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
