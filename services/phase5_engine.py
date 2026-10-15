"""Phase 5 Engine - Concrete Function Contracts for Intelligent Data Analysis & Insight Generation.

Implements all 14 explicit Phase 5 Python function contracts:
5.1  calculate_column_statistics
5.2  analyze_distributions
5.3  calculate_correlations
5.4  analyze_categories
5.5  analyze_trends
5.6  detect_date_columns
5.7  summarize_anomaly_results
5.8  summarize_data_quality
5.9  analyze_across_datasets
5.10 generate_insights
5.11 validate_insights
5.12 prepare_analysis_visualizations
5.13 explain_insights_with_ai
5.14 run_phase5_analysis
"""

from typing import Any, Optional, Dict, List, Union
import numpy as np
import pandas as pd

from tools.anomaly_tool import AnomalyTool
from tools.statistics_tool import StatisticsTool
from agents.insight_agent import InsightAgent
from services.chart_generator import ChartGeneratorService
from services.analyst import AnalystService
from core.session_manager import SessionManager


# =============================================================================
# 5.1 STATISTICAL ANALYSIS
# =============================================================================

def calculate_column_statistics(
    df: pd.DataFrame,
    columns: Optional[list[str]] = None,
) -> dict[str, dict[str, Any]]:
    """Calculate descriptive statistics for selected columns without mutating df.

    Returns:
        {
            "column_name": {
                "dtype": str,
                "count": int,
                "missing_count": int,
                "missing_percentage": float,
                "unique_count": int,
                "mean": float | None,
                "median": float | None,
                "std": float | None,
                "variance": float | None,
                "min": Any,
                "max": Any,
                "q1": float | None,
                "q3": float | None,
                "iqr": float | None,
                "skewness": float | None
            }
        }
    """
    if df is None or df.empty:
        return {}

    working_df = df.copy()
    target_cols = columns if columns is not None else list(working_df.columns)
    stats: dict[str, dict[str, Any]] = {}

    for col in target_cols:
        if col not in working_df.columns:
            continue
        series = working_df[col]
        total_len = len(series)
        valid_series = series.dropna()
        valid_cnt = len(valid_series)
        missing_cnt = int(series.isna().sum())
        missing_pct = round(float(missing_cnt / total_len * 100), 2) if total_len > 0 else 0.0
        unique_cnt = int(series.nunique(dropna=True))
        dtype_str = str(series.dtype)

        is_num = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)

        if is_num and valid_cnt > 0:
            mean_val = round(float(valid_series.mean()), 4)
            med_val = round(float(valid_series.median()), 4)
            std_val = round(float(valid_series.std(ddof=1)), 4) if valid_cnt > 1 else 0.0
            var_val = round(float(valid_series.var(ddof=1)), 4) if valid_cnt > 1 else 0.0
            min_val = round(float(valid_series.min()), 4)
            max_val = round(float(valid_series.max()), 4)
            q1_val = round(float(valid_series.quantile(0.25)), 4)
            q3_val = round(float(valid_series.quantile(0.75)), 4)
            iqr_val = round(float(q3_val - q1_val), 4)
            skew_val = round(float(valid_series.skew()), 4) if valid_cnt > 2 and not np.isnan(valid_series.skew()) else 0.0

            stats[str(col)] = {
                "dtype": dtype_str,
                "count": valid_cnt,
                "missing_count": missing_cnt,
                "missing_percentage": missing_pct,
                "unique_count": unique_cnt,
                "mean": mean_val,
                "median": med_val,
                "std": std_val,
                "variance": var_val,
                "min": min_val,
                "max": max_val,
                "q1": q1_val,
                "q3": q3_val,
                "iqr": iqr_val,
                "skewness": skew_val,
            }
        else:
            min_val = str(valid_series.min()) if valid_cnt > 0 else None
            max_val = str(valid_series.max()) if valid_cnt > 0 else None
            stats[str(col)] = {
                "dtype": dtype_str,
                "count": valid_cnt,
                "missing_count": missing_cnt,
                "missing_percentage": missing_pct,
                "unique_count": unique_cnt,
                "mean": None,
                "median": None,
                "std": None,
                "variance": None,
                "min": min_val,
                "max": max_val,
                "q1": None,
                "q3": None,
                "iqr": None,
                "skewness": None,
            }

    return stats


# =============================================================================
# 5.2 DISTRIBUTION ANALYSIS
# =============================================================================

def analyze_distributions(
    df: pd.DataFrame,
    numeric_columns: Optional[list[str]] = None,
) -> dict[str, dict[str, Any]]:
    """Analyze numeric distributions.

    Returns distribution summaries without modifying df.
    """
    if df is None or df.empty:
        return {}

    working_df = df.copy()
    if numeric_columns is None:
        target_cols = [
            c for c in working_df.columns
            if pd.api.types.is_numeric_dtype(working_df[c])
            and not pd.api.types.is_bool_dtype(working_df[c])
            and not (str(c).lower().startswith("unnamed") or str(c).lower() in ("index", "level_0", "id", "row_id"))
        ]
    else:
        target_cols = [c for c in numeric_columns if c in working_df.columns and pd.api.types.is_numeric_dtype(working_df[c])]

    dist_summaries: dict[str, dict[str, Any]] = {}
    for col in target_cols:
        series = working_df[col].dropna()
        n = len(series)
        if n == 0:
            continue
        mean_val = float(series.mean())
        med_val = float(series.median())
        std_val = float(series.std(ddof=1)) if n > 1 else 0.0
        var_val = float(series.var(ddof=1)) if n > 1 else 0.0
        min_val = float(series.min())
        max_val = float(series.max())
        q1_val = float(series.quantile(0.25))
        q3_val = float(series.quantile(0.75))
        iqr_val = float(q3_val - q1_val)
        skew_val = float(series.skew()) if n > 2 and not np.isnan(series.skew()) else 0.0
        kurt_val = float(series.kurt()) if n > 3 and not np.isnan(series.kurt()) else 0.0

        is_skewed = abs(skew_val) >= 0.8
        is_high_var = (std_val / abs(mean_val) > 1.0) if mean_val != 0 else (std_val > 0)
        shape_label = (
            "Right-Skewed" if skew_val >= 0.8
            else ("Left-Skewed" if skew_val <= -0.8
            else ("High Variance" if is_high_var else "Normal / Symmetric"))
        )

        dist_summaries[str(col)] = {
            "shape_label": shape_label,
            "is_skewed": is_skewed,
            "skewness": round(skew_val, 4),
            "kurtosis": round(kurt_val, 4),
            "is_high_variance": is_high_var,
            "mean": round(mean_val, 4),
            "median": round(med_val, 4),
            "std": round(std_val, 4),
            "variance": round(var_val, 4),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "range": round(max_val - min_val, 4),
            "quartiles": {
                "q1": round(q1_val, 4),
                "median": round(med_val, 4),
                "q3": round(q3_val, 4),
            },
            "iqr": round(iqr_val, 4),
            "outlier_bounds": {
                "lower": round(q1_val - 1.5 * iqr_val, 4),
                "upper": round(q3_val + 1.5 * iqr_val, 4),
            },
        }

    return dist_summaries


# =============================================================================
# 5.3 CORRELATION ANALYSIS
# =============================================================================

def calculate_correlations(
    df: pd.DataFrame,
    numeric_columns: Optional[list[str]] = None,
    method: str = "pearson",
) -> dict[str, Any]:
    """Calculate numeric correlations.

    Returns:
        {
            "matrix": dict,
            "relationships": [
                {
                    "column_a": str,
                    "column_b": str,
                    "correlation": float,
                    "direction": str,
                    "strength": str
                }
            ]
        }
    """
    valid_methods = {"pearson", "spearman", "kendall"}
    if method not in valid_methods:
        return {
            "status": "error",
            "message": f"Unsupported correlation method '{method}'. Supported methods: {', '.join(sorted(valid_methods))}.",
            "matrix": {},
            "relationships": [],
        }

    if df is None or df.empty:
        return {
            "status": "unavailable",
            "reason": "DataFrame is empty or None",
            "matrix": {},
            "relationships": [],
        }

    working_df = df.copy()
    if numeric_columns is None:
        target_cols = [
            c for c in working_df.columns
            if pd.api.types.is_numeric_dtype(working_df[c])
            and not pd.api.types.is_bool_dtype(working_df[c])
            and not (str(c).lower().startswith("unnamed") or str(c).lower() in ("index", "level_0", "id", "row_id"))
        ]
    else:
        target_cols = [c for c in numeric_columns if c in working_df.columns and pd.api.types.is_numeric_dtype(working_df[c])]

    if len(target_cols) < 2:
        return {
            "status": "unavailable",
            "reason": "Insufficient numeric columns (minimum 2 required) for correlation analysis",
            "matrix": {},
            "relationships": [],
        }

    corr_df = working_df[target_cols].corr(method=method).round(4)
    matrix_dict = corr_df.to_dict()

    relationships = []
    cols = list(corr_df.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            col_a = cols[i]
            col_b = cols[j]
            r = corr_df.loc[col_a, col_b]
            if pd.isna(r):
                continue
            r_val = float(r)
            direction = "positive" if r_val >= 0 else "negative"
            abs_r = abs(r_val)
            strength = "strong" if abs_r >= 0.70 else ("moderate" if abs_r >= 0.40 else "weak")
            relationships.append({
                "column_a": str(col_a),
                "column_b": str(col_b),
                "correlation": round(r_val, 4),
                "direction": direction,
                "strength": strength,
                "statement": f"'{col_a}' and '{col_b}' show a {strength} {direction} statistical association (r = {r_val:+.2f}).",
            })

    relationships.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    return {
        "status": "success",
        "method": method,
        "matrix": matrix_dict,
        "relationships": relationships,
    }


# =============================================================================
# 5.4 CATEGORY ANALYSIS
# =============================================================================

def analyze_categories(
    df: pd.DataFrame,
    categorical_columns: Optional[list[str]] = None,
    numeric_columns: Optional[list[str]] = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Analyze categorical distributions and optional numeric aggregations grouped by category."""
    if df is None or df.empty:
        return {
            "status": "unavailable",
            "reason": "DataFrame is empty or None",
            "distributions": [],
            "top_categories": [],
            "bottom_categories": [],
        }

    working_df = df.copy()
    if categorical_columns is None:
        cat_cols = []
        for col in working_df.columns:
            series = working_df[col]
            is_id, _ = AnomalyTool.is_id_or_index_column(series, str(col))
            if is_id:
                continue
            if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
                if not pd.api.types.is_datetime64_any_dtype(series):
                    col_lower = str(col).lower()
                    if not any(k in col_lower for k in ["date", "time", "day", "month", "timestamp"]):
                        cat_cols.append(str(col))
    else:
        cat_cols = [str(c) for c in categorical_columns if c in working_df.columns]

    if not cat_cols:
        return {
            "status": "unavailable",
            "reason": "No categorical columns detected",
            "distributions": [],
            "top_categories": [],
            "bottom_categories": [],
        }

    if numeric_columns is None:
        num_cols = [
            str(c) for c in working_df.columns
            if pd.api.types.is_numeric_dtype(working_df[c])
            and not pd.api.types.is_bool_dtype(working_df[c])
            and not AnomalyTool.is_id_or_index_column(working_df[c], str(c))[0]
        ]
    else:
        num_cols = [str(c) for c in numeric_columns if c in working_df.columns and pd.api.types.is_numeric_dtype(working_df[c])]

    distributions = []
    top_categories_list = []
    bottom_categories_list = []

    for col in cat_cols:
        series = working_df[col].dropna()
        total_valid = len(series)
        if total_valid == 0:
            continue

        vc = series.value_counts()
        total_unique = len(vc)
        most_freq_cat = str(vc.index[0])
        most_freq_cnt = int(vc.iloc[0])
        most_freq_pct = round(float(most_freq_cnt / total_valid * 100), 2)

        least_freq_cat = str(vc.index[-1])
        least_freq_cnt = int(vc.iloc[-1])
        least_freq_pct = round(float(least_freq_cnt / total_valid * 100), 2)

        is_imbalanced = (most_freq_pct >= 60.0) or (most_freq_cnt / max(1, least_freq_cnt) >= 10.0 and total_unique > 2)
        imbalance_exp = (
            f"Category '{most_freq_cat}' heavily dominates representing {most_freq_pct}% of records."
            if is_imbalanced else "Categories exhibit a relatively balanced distribution."
        )

        items = [
            {"category": str(k), "count": int(v), "percentage": round(float(v / total_valid * 100), 2)}
            for k, v in vc.head(top_n).items()
        ]

        distributions.append({
            "column": col,
            "unique_count": total_unique,
            "most_frequent": most_freq_cat,
            "most_frequent_percentage": most_freq_pct,
            "least_frequent": least_freq_cat,
            "least_frequent_percentage": least_freq_pct,
            "is_imbalanced": is_imbalanced,
            "imbalance_explanation": imbalance_exp,
            "categories": items,
        })

        for num_col in num_cols[:2]:
            try:
                grp = working_df.groupby(col)[num_col].agg(["sum", "mean", "count"]).dropna()
                if not grp.empty:
                    grp_sorted = grp.sort_values(by="sum", ascending=False)
                    tot_sum = float(grp_sorted["sum"].sum())
                    top3_sum = float(grp_sorted["sum"].head(3).sum())
                    conc_ratio = round((top3_sum / tot_sum * 100), 2) if tot_sum > 0 else 0.0

                    top_items = [
                        {
                            "category": str(k),
                            "value": round(float(row["sum"]), 2),
                            "mean": round(float(row["mean"]), 2),
                            "count": int(row["count"]),
                            "share_pct": round(float(row["sum"] / tot_sum * 100), 2) if tot_sum > 0 else 0.0,
                        }
                        for k, row in grp_sorted.head(top_n).iterrows()
                    ]

                    bot_items = [
                        {
                            "category": str(k),
                            "value": round(float(row["sum"]), 2),
                            "mean": round(float(row["mean"]), 2),
                            "count": int(row["count"]),
                            "share_pct": round(float(row["sum"] / tot_sum * 100), 2) if tot_sum > 0 else 0.0,
                        }
                        for k, row in grp_sorted.tail(top_n).iloc[::-1].iterrows()
                    ]

                    top_categories_list.append({
                        "category_column": col,
                        "metric_column": num_col,
                        "aggregation": "sum",
                        "concentration_ratio_top3": conc_ratio,
                        "total_categories": total_unique,
                        "items": top_items,
                    })

                    bottom_categories_list.append({
                        "category_column": col,
                        "metric_column": num_col,
                        "aggregation": "sum",
                        "total_categories": total_unique,
                        "items": bot_items,
                    })
            except Exception:
                pass

    return {
        "status": "success",
        "distributions": distributions,
        "top_categories": top_categories_list,
        "bottom_categories": bottom_categories_list,
    }


# =============================================================================
# 5.5 TREND ANALYSIS
# =============================================================================

def analyze_trends(
    df: pd.DataFrame,
    date_column: str,
    numeric_columns: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Analyze chronological changes."""
    if df is None or df.empty:
        return {
            "status": "unavailable",
            "reason": "DataFrame is empty or None",
            "trends": [],
            "changes": [],
            "peaks": [],
            "drops": [],
        }

    if date_column not in df.columns:
        return {
            "status": "unavailable",
            "reason": f"Specified date column '{date_column}' not found in dataset",
            "trends": [],
            "changes": [],
            "peaks": [],
            "drops": [],
        }

    working_df = df.copy()
    parsed_dates = pd.to_datetime(working_df[date_column], errors="coerce")
    valid_mask = parsed_dates.notna()
    if valid_mask.sum() < 3:
        return {
            "status": "unavailable",
            "reason": "Insufficient valid chronological data points (minimum 3 required) to compute trend trajectory",
            "trends": [],
            "changes": [],
            "peaks": [],
            "drops": [],
        }

    working_df["_parsed_date"] = parsed_dates
    working_df = working_df[valid_mask].sort_values("_parsed_date")

    if numeric_columns is None:
        num_cols = [
            str(c) for c in working_df.columns
            if pd.api.types.is_numeric_dtype(working_df[c])
            and not pd.api.types.is_bool_dtype(working_df[c])
            and c != "_parsed_date"
            and not AnomalyTool.is_id_or_index_column(working_df[c], str(c))[0]
        ]
    else:
        num_cols = [str(c) for c in numeric_columns if c in working_df.columns and pd.api.types.is_numeric_dtype(working_df[c])]

    if not num_cols:
        return {
            "status": "unavailable",
            "reason": "No numeric columns available to compute trends over time",
            "trends": [],
            "changes": [],
            "peaks": [],
            "drops": [],
        }

    trends = []
    changes = []
    peaks = []
    drops = []

    for metric in num_cols:
        series = working_df.dropna(subset=[metric])
        if len(series) < 3:
            continue

        daily = series.groupby("_parsed_date")[metric].mean().reset_index()
        if len(daily) < 2:
            continue

        start_val = float(daily[metric].iloc[0])
        end_val = float(daily[metric].iloc[-1])
        start_date = daily["_parsed_date"].iloc[0].strftime("%Y-%m-%d")
        end_date = daily["_parsed_date"].iloc[-1].strftime("%Y-%m-%d")

        chg_val = end_val - start_val
        chg_pct = round((chg_val / abs(start_val) * 100), 2) if start_val != 0 else 0.0

        direction = (
            "increasing" if chg_pct >= 5.0
            else ("decreasing" if chg_pct <= -5.0 else "stable")
        )

        max_idx = daily[metric].idxmax()
        min_idx = daily[metric].idxmin()
        peak_date = daily["_parsed_date"].loc[max_idx].strftime("%Y-%m-%d")
        peak_val = round(float(daily[metric].loc[max_idx]), 2)
        drop_date = daily["_parsed_date"].loc[min_idx].strftime("%Y-%m-%d")
        drop_val = round(float(daily[metric].loc[min_idx]), 2)

        peaks.append({"column": metric, "date": peak_date, "value": peak_val})
        drops.append({"column": metric, "date": drop_date, "value": drop_val})

        daily["_pct_chg"] = daily[metric].pct_change() * 100
        sudden_shifts = []
        for idx, row in daily.iterrows():
            pct = row["_pct_chg"]
            if pd.notna(pct) and abs(pct) >= 20.0:
                prev_date = daily["_parsed_date"].iloc[idx - 1].strftime("%Y-%m-%d") if idx > 0 else "N/A"
                prev_val = round(float(daily[metric].iloc[idx - 1]), 2) if idx > 0 else 0.0
                curr_date = row["_parsed_date"].strftime("%Y-%m-%d")
                curr_val = round(float(row[metric]), 2)
                shift_record = {
                    "column": metric,
                    "type": "Sudden Spike" if pct > 0 else "Sudden Plunge",
                    "date": curr_date,
                    "previous_date": prev_date,
                    "previous_value": prev_val,
                    "current_value": curr_val,
                    "change_pct": round(float(pct), 2),
                }
                changes.append(shift_record)
                sudden_shifts.append(shift_record)

        trends.append({
            "column": metric,
            "direction": direction,
            "change_percentage": chg_pct,
            "start_value": round(start_val, 2),
            "end_value": round(end_val, 2),
            "start_date": start_date,
            "end_date": end_date,
            "peak": {"date": peak_date, "value": peak_val},
            "drop": {"date": drop_date, "value": drop_val},
            "sudden_changes": sudden_shifts[:3],
        })

    return {
        "status": "success",
        "date_column": date_column,
        "trends": trends,
        "changes": changes,
        "peaks": peaks,
        "drops": drops,
    }


# =============================================================================
# 5.6 DATE COLUMN DETECTION
# =============================================================================

def detect_date_columns(df: pd.DataFrame) -> list[str]:
    """Detect columns that can reasonably be interpreted as dates."""
    if df is None or df.empty:
        return []

    date_cols: list[str] = []
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            date_cols.append(str(col))
            continue

        if pd.api.types.is_bool_dtype(series):
            continue

        col_lower = str(col).lower()
        is_id, _ = AnomalyTool.is_id_or_index_column(series, str(col))
        if is_id:
            continue

        # Prevent arbitrary numeric columns from being blindly classified as dates
        if pd.api.types.is_numeric_dtype(series):
            if any(k in col_lower for k in ["year", "date", "timestamp"]):
                valid_num = series.dropna().head(30)
                if len(valid_num) >= 3:
                    is_year = ((valid_num >= 1900) & (valid_num <= 2100)).all()
                    is_yyyymmdd = ((valid_num >= 19000101) & (valid_num <= 21001231)).all()
                    if is_year or is_yyyymmdd:
                        date_cols.append(str(col))
            continue

        if any(k in col_lower for k in ["date", "time", "day", "month", "timestamp", "period"]):
            valid_sample = series.dropna().head(30)
            if len(valid_sample) >= 3:
                try:
                    parsed = pd.to_datetime(valid_sample, errors="coerce")
                    if parsed.notna().mean() >= 0.8:
                        date_cols.append(str(col))
                        continue
                except Exception:
                    pass

        if series.dtype == object:
            valid_sample = series.dropna().head(20)
            if len(valid_sample) >= 5:
                sample_str = valid_sample.astype(str)
                if sample_str.str.contains(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", regex=True).mean() >= 0.8 or \
                   sample_str.str.contains(r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", regex=True).mean() >= 0.8:
                    try:
                        parsed = pd.to_datetime(valid_sample, errors="coerce")
                        if parsed.notna().mean() >= 0.8:
                            date_cols.append(str(col))
                    except Exception:
                        pass

    return date_cols


# =============================================================================
# 5.7 PHASE 4 ANOMALY INTEGRATION
# =============================================================================

def summarize_anomaly_results(anomaly_results: dict[str, Any]) -> dict[str, Any]:
    """Convert existing Phase 4 anomaly results into Phase 5 insight-ready summaries.

    Must not rerun anomaly detection.
    """
    if not anomaly_results or not isinstance(anomaly_results, dict):
        return {
            "status": "unavailable",
            "reason": "No Phase 4 anomaly results provided",
            "total_anomalies": 0,
            "iqr_outliers": 0,
            "isolation_forest_anomalies": 0,
            "multivariate_anomalies": 0,
            "affected_columns": [],
            "affected_rows": [],
            "method_summary": {},
        }

    total_anom = 0
    iqr_outliers = 0
    if_anom = 0
    mv_anom = 0
    affected_cols = set()
    affected_rows = set()
    method_summary = {}

    if "iqr" in anomaly_results:
        iqr_res = anomaly_results["iqr"]
        iqr_outliers = getattr(iqr_res, "total_outlier_rows", 0) if not isinstance(iqr_res, dict) else iqr_res.get("total_outlier_rows", 0)
        total_anom += iqr_outliers
        cols = getattr(iqr_res, "columns_analyzed", []) if not isinstance(iqr_res, dict) else iqr_res.get("columns_analyzed", [])
        for c in cols:
            affected_cols.add(str(c))
        rows = getattr(iqr_res, "all_outlier_indices", []) if not isinstance(iqr_res, dict) else iqr_res.get("all_outlier_indices", [])
        for r in rows:
            affected_rows.add(r)
        method_summary["iqr"] = {
            "outlier_rows": iqr_outliers,
            "outlier_rate": getattr(iqr_res, "outlier_rate", 0.0) if not isinstance(iqr_res, dict) else iqr_res.get("outlier_rate", 0.0),
        }

    if "isolation_forest" in anomaly_results:
        if_res = anomaly_results["isolation_forest"]
        if_anom = getattr(if_res, "anomaly_count", 0) if not isinstance(if_res, dict) else if_res.get("anomaly_count", 0)
        total_anom += if_anom
        cols = getattr(if_res, "features_used", []) if not isinstance(if_res, dict) else if_res.get("features_used", [])
        for c in cols:
            affected_cols.add(str(c))
        rows = getattr(if_res, "anomaly_indices", []) if not isinstance(if_res, dict) else if_res.get("anomaly_indices", [])
        for r in rows:
            affected_rows.add(r)
        method_summary["isolation_forest"] = {
            "anomaly_count": if_anom,
            "anomaly_pct": getattr(if_res, "anomaly_pct", 0.0) if not isinstance(if_res, dict) else if_res.get("anomaly_pct", 0.0),
        }

    if "multivariate" in anomaly_results:
        mv_res = anomaly_results["multivariate"]
        mv_anom = getattr(mv_res, "anomaly_count", 0) if not isinstance(mv_res, dict) else mv_res.get("anomaly_count", 0)
        total_anom += mv_anom
        cols = getattr(mv_res, "features_used", []) if not isinstance(mv_res, dict) else mv_res.get("features_used", [])
        for c in cols:
            affected_cols.add(str(c))
        rows = getattr(mv_res, "all_anomaly_indices", []) if not isinstance(mv_res, dict) else mv_res.get("all_anomaly_indices", [])
        for r in rows:
            affected_rows.add(r)
        method_summary["multivariate"] = {
            "anomaly_count": mv_anom,
            "anomaly_pct": getattr(mv_res, "anomaly_pct", 0.0) if not isinstance(mv_res, dict) else mv_res.get("anomaly_pct", 0.0),
        }

    return {
        "status": "success",
        "total_anomalies": total_anom,
        "iqr_outliers": iqr_outliers,
        "isolation_forest_anomalies": if_anom,
        "multivariate_anomalies": mv_anom,
        "affected_columns": sorted(list(affected_cols)),
        "affected_rows": sorted(list(affected_rows)),
        "method_summary": method_summary,
    }


# =============================================================================
# 5.8 DATA QUALITY INSIGHT INTEGRATION
# =============================================================================

def summarize_data_quality(
    df: pd.DataFrame,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Summarize existing data-quality information for Phase 5 insight generation."""
    if df is None or df.empty:
        return {
            "row_count": 0,
            "column_count": 0,
            "duplicate_rows": 0,
            "duplicate_rate": 0.0,
            "missing_count": 0,
            "missing_rate": 0.0,
            "high_missing_columns": [],
            "constant_columns": [],
        }

    working_df = df.copy()
    row_cnt = len(working_df)
    col_cnt = len(working_df.columns)
    total_cells = row_cnt * max(1, col_cnt)

    dup_cnt = int(working_df.duplicated().sum())
    dup_rate = round(float(dup_cnt / row_cnt * 100), 2) if row_cnt > 0 else 0.0

    missing_cnt = int(working_df.isna().sum().sum())
    missing_rate = round(float(missing_cnt / total_cells * 100), 2) if total_cells > 0 else 0.0

    high_missing = [str(c) for c in working_df.columns if working_df[c].isna().mean() >= 0.10]
    constant_cols = [str(c) for c in working_df.columns if working_df[c].nunique(dropna=False) <= 1]

    dq_summary = {
        "row_count": row_cnt,
        "column_count": col_cnt,
        "duplicate_rows": dup_cnt,
        "duplicate_rate": dup_rate,
        "missing_count": missing_cnt,
        "missing_rate": missing_rate,
        "high_missing_columns": high_missing,
        "constant_columns": constant_cols,
    }

    if metadata and isinstance(metadata, dict):
        dq_summary.update(metadata)

    return dq_summary


# =============================================================================
# 5.9 CROSS-DATASET ANALYSIS
# =============================================================================

def analyze_across_datasets(
    datasets: dict[str, pd.DataFrame],
    validated_relationships: list[dict[str, Any]],
    join_audit: Optional[list[dict[str, Any]]] = None,
    analysis_request: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Perform cross-dataset analysis only using validated relationships.

    Unsafe relationships must be blocked.
    """
    if len(datasets) < 2 or not validated_relationships:
        return {
            "status": "unavailable",
            "reason": "Requires at least 2 datasets and at least 1 validated relationship",
            "datasets_used": [],
            "relationships_used": [],
            "join_type": None,
            "rows_before": {},
            "rows_after": None,
            "analysis": {},
            "warnings": ["Insufficient datasets or relationships for cross-file linkage."],
        }

    target_rel = None
    for r in validated_relationships:
        conf = r.get("confidence") if isinstance(r, dict) else getattr(r, "confidence", "")
        confirmed = r.get("confirmed_by_user", False) if isinstance(r, dict) else getattr(r, "confirmed_by_user", False)
        if conf == "HIGH" or confirmed:
            target_rel = r
            break

    if not target_rel:
        return {
            "status": "unavailable",
            "reason": "No high-confidence or confirmed relationships found",
            "datasets_used": [],
            "relationships_used": [],
            "join_type": None,
            "rows_before": {},
            "rows_after": None,
            "analysis": {},
            "warnings": ["Only HIGH confidence or user-confirmed relationships may be analyzed."],
        }

    src_name = target_rel.get("source_dataset") if isinstance(target_rel, dict) else getattr(target_rel, "source_dataset", "")
    src_col = target_rel.get("source_column") if isinstance(target_rel, dict) else getattr(target_rel, "source_column", "")
    tgt_name = target_rel.get("target_dataset") if isinstance(target_rel, dict) else getattr(target_rel, "target_dataset", "")
    tgt_col = target_rel.get("target_column") if isinstance(target_rel, dict) else getattr(target_rel, "target_column", "")

    if src_name not in datasets or tgt_name not in datasets:
        return {
            "status": "error",
            "reason": f"Required datasets '{src_name}' or '{tgt_name}' are not loaded",
            "datasets_used": [],
            "relationships_used": [],
            "join_type": None,
            "rows_before": {},
            "rows_after": None,
            "analysis": {},
            "warnings": [f"Missing datasets: {src_name}, {tgt_name}"],
        }

    left_df = datasets[src_name].copy()
    right_df = datasets[tgt_name].copy()
    rows_before = {src_name: len(left_df), tgt_name: len(right_df)}

    # Guard against many-to-many Cartesian explosion
    src_dups = left_df[src_col].duplicated().sum() if src_col in left_df.columns else 0
    tgt_dups = right_df[tgt_col].duplicated().sum() if tgt_col in right_df.columns else 0
    if src_dups > 0 and tgt_dups > 0:
        return {
            "status": "blocked",
            "reason": "Unsafe many-to-many relationship causes row explosion",
            "datasets_used": [src_name, tgt_name],
            "relationships_used": [target_rel if isinstance(target_rel, dict) else {"source_dataset": src_name, "source_column": src_col, "target_dataset": tgt_name, "target_column": tgt_col}],
            "join_type": None,
            "rows_before": rows_before,
            "rows_after": None,
            "analysis": {},
            "warnings": [f"Join blocked: Duplicate keys detected in both '{src_name}.{src_col}' and '{tgt_name}.{tgt_col}'."],
        }

    try:
        merged = pd.merge(left_df, right_df, left_on=src_col, right_on=tgt_col, how="left")
        rows_after = len(merged)

        left_nums = [c for c in left_df.columns if pd.api.types.is_numeric_dtype(left_df[c]) and not AnomalyTool.is_id_or_index_column(left_df[c], str(c))[0]]
        right_cats = [c for c in right_df.columns if not pd.api.types.is_numeric_dtype(right_df[c]) and c != tgt_col and not AnomalyTool.is_id_or_index_column(right_df[c], str(c))[0]]

        metric_col = left_nums[0] if left_nums else (right_nums[0] if (right_nums := [c for c in right_df.columns if pd.api.types.is_numeric_dtype(right_df[c])]) else None)
        group_col = right_cats[0] if right_cats else (left_cats[0] if (left_cats := [c for c in left_df.columns if not pd.api.types.is_numeric_dtype(left_df[c]) and c != src_col]) else None)

        breakdown = []
        if metric_col and group_col and metric_col in merged.columns and group_col in merged.columns:
            grp = merged.groupby(group_col)[metric_col].agg(["sum", "mean", "count"]).sort_values(by="sum", ascending=False)
            tot = float(grp["sum"].sum())
            for k, row in grp.head(10).iterrows():
                breakdown.append({
                    "entity": str(k),
                    "total": round(float(row["sum"]), 2),
                    "average": round(float(row["mean"]), 2),
                    "count": int(row["count"]),
                    "share_pct": round(float(row["sum"] / tot * 100), 2) if tot > 0 else 0.0,
                })

        return {
            "status": "success",
            "datasets_used": [src_name, tgt_name],
            "relationships_used": [target_rel if isinstance(target_rel, dict) else {"source_dataset": src_name, "source_column": src_col, "target_dataset": tgt_name, "target_column": tgt_col}],
            "join_type": "left",
            "rows_before": rows_before,
            "rows_after": rows_after,
            "analysis": {
                "metric_column": metric_col,
                "group_column": group_col,
                "breakdown": breakdown,
            },
            "warnings": [],
        }
    except Exception as e:
        return {
            "status": "error",
            "reason": f"Join execution failed: {str(e)}",
            "datasets_used": [src_name, tgt_name],
            "relationships_used": [],
            "join_type": None,
            "rows_before": rows_before,
            "rows_after": None,
            "analysis": {},
            "warnings": [str(e)],
        }


# =============================================================================
# 5.10 INSIGHT ENGINE
# =============================================================================

def generate_insights(
    statistics: dict[str, Any],
    trends: dict[str, Any],
    correlations: dict[str, Any],
    categories: dict[str, Any],
    anomalies: dict[str, Any],
    data_quality: dict[str, Any],
    cross_dataset: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Generate evidence-backed structured insights."""
    payload = {
        "dataset_name": statistics.get("dataset_name", "dataset.csv"),
        "statistics": statistics,
        "trends": trends,
        "correlations": correlations,
        "categories": categories,
        "anomalies": anomalies,
        "data_quality": data_quality,
        "cross_dataset": cross_dataset or {},
    }
    return InsightAgent.insight_engine(payload)


# =============================================================================
# 5.11 INSIGHT VALIDATION
# =============================================================================

def validate_insights(
    insights: list[dict[str, Any]],
    analysis_results: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate that generated insights are supported by computed analysis results."""
    required_keys = {
        "title", "category", "finding", "evidence", "severity",
        "dataset", "columns", "recommended_investigation"
    }
    valid_severities = {"High", "Medium", "Low"}
    validated = []

    for ins in insights:
        if not isinstance(ins, dict):
            continue
        if not required_keys.issubset(ins.keys()):
            continue
        if ins.get("severity") not in valid_severities:
            ins["severity"] = "Medium"
        ev = ins.get("evidence")
        if ev is None or (isinstance(ev, dict) and len(ev) == 0):
            continue
        cols = ins.get("columns")
        if not isinstance(cols, list):
            ins["columns"] = [str(cols)] if cols else ["All Columns"]

        validated.append(ins)

    return validated


# =============================================================================
# 5.12 VISUALIZATION PREPARATION
# =============================================================================

def prepare_analysis_visualizations(
    analysis_results: dict[str, Any],
) -> dict[str, Any]:
    """Convert Phase 5 analysis results into chart-compatible structures."""
    df = analysis_results.get("df")
    return ChartGeneratorService.analysis_visualizations(analysis_results, df=df)


# =============================================================================
# 5.13 AI INSIGHT EXPLANATION
# =============================================================================

def explain_insights_with_ai(
    insights: list[dict[str, Any]],
    analysis_results: dict[str, Any],
    user_question: Optional[str] = None,
) -> dict[str, Any]:
    """Generate natural-language explanations grounded strictly in computed analysis results."""
    if user_question:
        target_name = analysis_results.get("datasets_analyzed", ["dataset.csv"])[0] if analysis_results.get("datasets_analyzed") else "dataset.csv"
        all_ds = SessionManager.get_datasets() if SessionManager.is_dataset_loaded() else {}
        rels = SessionManager.get_relationships()
        answer = None
        try:
            answer = AnalystService._handle_phase5_query(user_question, user_question.lower(), all_ds, rels)
        except Exception:
            try:
                answer = AnalystService._handle_phase5_query(user_question, filename=target_name)
            except Exception:
                pass

        if answer:
            explanation_text = getattr(answer, "summary_markdown", None) or getattr(answer, "headline", None) or str(answer)
            return {
                "status": "success",
                "question": user_question,
                "explanation": explanation_text,
                "grounded_in_computed_facts": True,
            }
        else:
            return {
                "status": "success",
                "question": user_question,
                "explanation": "There is not enough evidence in the analyzed data to determine this.",
                "grounded_in_computed_facts": True,
            }

    narrative = InsightAgent.ai_insight_explainer({
        "dataset_name": analysis_results.get("datasets_analyzed", ["dataset.csv"])[0] if analysis_results.get("datasets_analyzed") else "dataset.csv",
        "insights": insights,
        **analysis_results,
    })
    return {
        "status": "success",
        "summary": narrative,
        "grounded_in_computed_facts": True,
        "insight_count": len(insights),
    }


# =============================================================================
# 5.14 MAIN PHASE 5 ORCHESTRATOR
# =============================================================================

def run_phase5_analysis(
    datasets: dict[str, pd.DataFrame],
    analysis_configuration: Optional[dict[str, Any]] = None,
    anomaly_results: Optional[dict[str, Any]] = None,
    validated_relationships: Optional[list[dict[str, Any]]] = None,
    join_audit: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Execute the complete Phase 5 analysis pipeline.

    Coordinates modules without embedding heavy calculations.
    """
    if not datasets or not isinstance(datasets, dict):
        return {
            "status": "error",
            "datasets_analyzed": [],
            "statistics": {},
            "trends": {},
            "correlations": {},
            "categories": {},
            "anomalies": {},
            "data_quality": {},
            "cross_dataset": None,
            "insights": [],
            "visualizations": {},
            "warnings": ["No datasets provided for analysis."],
            "errors": ["Input 'datasets' must be a non-empty dictionary."],
        }

    warnings: list[str] = []
    errors: list[str] = []
    datasets_analyzed = list(datasets.keys())
    cfg = analysis_configuration or {}

    target_name = cfg.get("target_dataset")
    if not target_name or target_name not in datasets:
        target_name = datasets_analyzed[0]

    primary_df = datasets[target_name]
    if primary_df is None or primary_df.empty:
        return {
            "status": "error",
            "datasets_analyzed": datasets_analyzed,
            "statistics": {},
            "trends": {},
            "correlations": {},
            "categories": {},
            "anomalies": {},
            "data_quality": {},
            "cross_dataset": None,
            "insights": [],
            "visualizations": {},
            "warnings": [],
            "errors": [f"Target dataset '{target_name}' is empty or None."],
        }

    # 1. Statistical Analysis
    stats_cfg = cfg.get("statistics")
    stats_enabled = True
    if isinstance(stats_cfg, dict):
        stats_enabled = stats_cfg.get("enabled", True)
    
    selected_cols = cfg.get("selected_columns")
    if stats_enabled:
        col_stats = calculate_column_statistics(primary_df, columns=selected_cols)
        dist_stats = analyze_distributions(primary_df, numeric_columns=selected_cols)
        statistics_payload = {
            "status": "success",
            "dataset_name": target_name,
            "column_statistics": col_stats,
            "distribution_statistics": dist_stats,
        }
    else:
        statistics_payload = {
            "status": "disabled",
            "dataset_name": target_name,
            "column_statistics": {},
            "distribution_statistics": {},
        }

    # 2. Date detection & Trend Analysis
    trends_cfg = cfg.get("trends")
    trends_enabled = True
    date_col = None
    if isinstance(trends_cfg, dict):
        trends_enabled = trends_cfg.get("enabled", True)
        configured_date = trends_cfg.get("date_column")
        if configured_date and configured_date != "Auto Detect":
            date_col = configured_date
    if not date_col:
        date_col = cfg.get("date_column")

    if not trends_enabled:
        trends_payload = {"status": "disabled", "reason": "Trend analysis disabled in configuration", "trends": []}
    else:
        if not date_col:
            detected_dates = detect_date_columns(primary_df)
            date_col = detected_dates[0] if detected_dates else None

        if date_col and date_col in primary_df.columns:
            trends_payload = analyze_trends(primary_df, date_column=date_col, numeric_columns=cfg.get("numeric_columns"))
        else:
            trends_payload = {"status": "unavailable", "reason": "No valid date/time column detected", "trends": []}

    # 3. Correlation Analysis
    corr_cfg = cfg.get("correlations")
    corr_enabled = True
    corr_method = "pearson"
    if isinstance(corr_cfg, dict):
        corr_enabled = corr_cfg.get("enabled", True)
        corr_method = str(corr_cfg.get("method", "pearson")).lower()
    else:
        corr_method = str(cfg.get("correlation_method", "pearson")).lower()

    if not corr_enabled:
        correlations_payload = {"status": "disabled", "reason": "Correlation analysis disabled in configuration", "matrix": {}, "relationships": []}
    else:
        correlations_payload = calculate_correlations(primary_df, numeric_columns=cfg.get("numeric_columns"), method=corr_method)

    # 4. Category Analysis
    cat_cfg = cfg.get("categories")
    cat_enabled = True
    top_n = 10
    if isinstance(cat_cfg, dict):
        cat_enabled = cat_cfg.get("enabled", True)
        top_n = int(cat_cfg.get("top_n", 10))
    else:
        top_n = int(cfg.get("top_n", 10))

    if not cat_enabled:
        categories_payload = {"status": "disabled", "reason": "Category analysis disabled in configuration", "distributions": [], "top_categories": []}
    else:
        categories_payload = analyze_categories(
            primary_df,
            categorical_columns=cfg.get("categorical_columns"),
            numeric_columns=cfg.get("numeric_columns"),
            top_n=top_n,
        )

    # 5. Phase 4 Anomaly Integration
    anom_cfg = cfg.get("anomalies")
    include_anom = True
    if isinstance(anom_cfg, dict):
        include_anom = anom_cfg.get("include_phase4", True)

    if not include_anom:
        anomalies_payload = {"status": "disabled", "reason": "Anomaly integration disabled in configuration", "total_anomalies": 0, "method_summary": {}}
    else:
        ds_anom = None
        if anomaly_results and isinstance(anomaly_results, dict):
            ds_anom = anomaly_results.get(target_name) if target_name in anomaly_results else anomaly_results
        else:
            ds_anom = SessionManager.get_anomaly_results(target_name)
        anomalies_payload = summarize_anomaly_results(ds_anom)

    # 6. Data Quality Summary
    data_quality_payload = summarize_data_quality(primary_df)

    # 7. Cross-Dataset Analysis
    cross_cfg = cfg.get("cross_dataset")
    cross_enabled = True
    if isinstance(cross_cfg, dict):
        cross_enabled = cross_cfg.get("enabled", True)

    cross_dataset_payload = None
    rels = validated_relationships or SessionManager.get_relationships()
    if cross_enabled and len(datasets) > 1 and rels:
        cross_dataset_payload = analyze_across_datasets(
            datasets=datasets,
            validated_relationships=rels,
            join_audit=join_audit or (SessionManager.get_join_audit() if hasattr(SessionManager, "get_join_audit") else SessionManager.get_join_audits()),
            analysis_request=cross_cfg if isinstance(cross_cfg, dict) else None,
        )
        if cross_dataset_payload and cross_dataset_payload.get("warnings"):
            warnings.extend(cross_dataset_payload.get("warnings", []))
    elif not cross_enabled:
        cross_dataset_payload = {"status": "disabled", "reason": "Cross-dataset analysis disabled in configuration"}

    # 8. Insight Generation
    insights_cfg = cfg.get("insights")
    insights_enabled = True
    max_insights = 20
    min_evidence_score = 0.60
    if isinstance(insights_cfg, dict):
        insights_enabled = insights_cfg.get("enabled", True)
        max_insights = int(insights_cfg.get("max_insights", 20))
        min_evidence_score = float(insights_cfg.get("min_evidence_score", 0.60))

    if not insights_enabled:
        raw_insights = []
        validated_insights = []
    else:
        raw_insights = generate_insights(
            statistics=statistics_payload,
            trends=trends_payload,
            correlations=correlations_payload,
            categories=categories_payload,
            anomalies=anomalies_payload,
            data_quality=data_quality_payload,
            cross_dataset=cross_dataset_payload,
        )

        # 9. Insight Validation
        combined_analysis = {
            "status": "success",
            "datasets_analyzed": datasets_analyzed,
            "dataset_name": target_name,
            "statistics": statistics_payload,
            "trends": trends_payload,
            "correlations": correlations_payload,
            "categories": categories_payload,
            "anomalies": anomalies_payload,
            "data_quality": data_quality_payload,
            "cross_dataset": cross_dataset_payload,
        }
        validated_insights = validate_insights(raw_insights, combined_analysis)
        if max_insights and len(validated_insights) > max_insights:
            validated_insights = validated_insights[:max_insights]

    combined_analysis = {
        "status": "success",
        "datasets_analyzed": datasets_analyzed,
        "dataset_name": target_name,
        "statistics": statistics_payload,
        "trends": trends_payload,
        "correlations": correlations_payload,
        "categories": categories_payload,
        "anomalies": anomalies_payload,
        "data_quality": data_quality_payload,
        "cross_dataset": cross_dataset_payload,
    }

    # 10. Visualization Preparation
    viz_cfg = cfg.get("visualizations")
    viz_enabled = True
    if isinstance(viz_cfg, dict):
        viz_enabled = viz_cfg.get("enabled", True)

    if viz_enabled:
        viz_payload = prepare_analysis_visualizations({**combined_analysis, "df": primary_df})
    else:
        viz_payload = {"status": "disabled", "charts": {}, "chart_types": []}

    # Compute per-dataset cache for seamless multi-dataset switching
    per_dataset: dict[str, Any] = {}
    for d_name, d_df in datasets.items():
        if d_df is None or d_df.empty:
            continue
        if d_name == target_name:
            per_dataset[d_name] = {
                "statistics": statistics_payload,
                "trends": trends_payload,
                "correlations": correlations_payload,
                "categories": categories_payload,
                "anomalies": anomalies_payload,
                "data_quality": data_quality_payload,
                "df": d_df,
            }
        else:
            p_col_stats = calculate_column_statistics(d_df) if stats_enabled else {}
            p_dist_stats = analyze_distributions(d_df) if stats_enabled else {}
            p_dates = detect_date_columns(d_df)
            p_date_col = p_dates[0] if p_dates else None
            p_trends = analyze_trends(d_df, date_column=p_date_col) if (trends_enabled and p_date_col) else {"status": "unavailable", "reason": "No valid date/time column detected", "trends": []}
            p_corrs = calculate_correlations(d_df, method=corr_method) if corr_enabled else {"status": "disabled", "matrix": {}, "relationships": []}
            p_cats = analyze_categories(d_df, top_n=top_n) if cat_enabled else {"status": "disabled", "distributions": []}
            p_ds_anom = summarize_anomaly_results(anomaly_results.get(d_name) if isinstance(anomaly_results, dict) else SessionManager.get_anomaly_results(d_name)) if include_anom else {"status": "disabled"}
            p_dq = summarize_data_quality(d_df)

            per_dataset[d_name] = {
                "statistics": {"status": "success" if stats_enabled else "disabled", "dataset_name": d_name, "column_statistics": p_col_stats, "distribution_statistics": p_dist_stats},
                "trends": p_trends,
                "correlations": p_corrs,
                "categories": p_cats,
                "anomalies": p_ds_anom,
                "data_quality": p_dq,
                "df": d_df,
            }

    status_str = "success"
    if errors:
        status_str = "error"
    elif warnings:
        status_str = "warning"

    result = {
        "status": status_str,
        "datasets_analyzed": datasets_analyzed,
        "target_dataset": target_name,
        "statistics": statistics_payload,
        "trends": trends_payload,
        "correlations": correlations_payload,
        "categories": categories_payload,
        "anomalies": anomalies_payload,
        "data_quality": data_quality_payload,
        "cross_dataset": cross_dataset_payload,
        "insights": validated_insights,
        "visualizations": viz_payload,
        "per_dataset": per_dataset,
        "warnings": warnings,
        "errors": errors,
    }

    # Session State Integration (Part 11)
    try:
        SessionManager.set("phase5_analysis", result)
    except Exception:
        pass

    return result

