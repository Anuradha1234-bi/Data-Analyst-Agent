"""Automated Data-Driven Insight Discovery Engine.

Discovers evidence-grounded, mathematical patterns:
- Pareto / Value Concentration (Top 20% vs Total).
- Outlier & Statistical Deviation Spikes.
- Period-over-Period Drift & Directional Shifts.
- Data Completeness & Missingness Risks.
- Bivariate Correlation & Relationship Discoveries.
"""

from typing import Dict, Any, List, Optional
import math
import numpy as np
import pandas as pd


class InsightEngine:
    """Discovers verifiable, non-hallucinatory insights directly from raw dataset and query results."""

    @classmethod
    def discover_insights(
        cls,
        df: pd.DataFrame,
        target_column: Optional[str] = None,
        group_column: Optional[str] = None,
        date_column: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate structured insights strictly from mathematical properties."""
        insights: List[Dict[str, Any]] = []
        if df is None or df.empty:
            return insights

        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_datetime64_any_dtype(df[c])]

        # Default columns if not specified
        primary_num = target_column if (target_column in num_cols) else (num_cols[0] if num_cols else None)
        primary_cat = group_column if (group_column in cat_cols) else (cat_cols[0] if cat_cols else None)

        # -------------------------------------------------------------
        # 1. Pareto / Concentration Insight (Top Categories vs Total)
        # -------------------------------------------------------------
        if primary_cat and primary_num:
            try:
                grouped = df.groupby(primary_cat)[primary_num].sum().sort_values(ascending=False)
                total_val = grouped.sum()
                if total_val > 0 and len(grouped) >= 3:
                    top_n_count = max(1, int(math.ceil(len(grouped) * 0.2)))  # Top 20%
                    top_sum = grouped.head(top_n_count).sum()
                    pct_share = round((top_sum / total_val) * 100.0, 1)

                    top_names = list(grouped.head(top_n_count).index)
                    names_str = ", ".join(f"'{n}'" for n in top_names[:3])

                    if pct_share >= 50.0:
                        severity = "High" if pct_share >= 80.0 else "Medium"
                        insights.append({
                            "type": "Concentration (Pareto Effect)",
                            "statement": (
                                f"High concentration detected: The top {top_n_count} {primary_cat} "
                                f"({names_str}) contribute {pct_share}% of total {primary_num}."
                            ),
                            "metric": f"{pct_share}% of total",
                            "columns_involved": [primary_cat, primary_num],
                            "records_considered": len(df),
                            "method": "Pareto distribution calculation (Sum of top 20% categories / Total sum)",
                            "confidence": "High",
                            "severity": severity,
                            "limitations": "Measures volumetric share only; does not imply profit margin or unit profitability.",
                        })
            except Exception:
                pass

        # -------------------------------------------------------------
        # 2. Statistical Outlier & Deviation Spikes
        # -------------------------------------------------------------
        for c in num_cols:
            try:
                s = df[c].dropna()
                if len(s) >= 10:
                    mean_val = float(s.mean())
                    std_val = float(s.std())
                    if std_val > 0:
                        z_scores = (s - mean_val).abs() / std_val
                        outliers_count = int((z_scores > 3.0).sum())
                        if outliers_count > 0:
                            pct_outliers = round((outliers_count / len(s)) * 100.0, 1)
                            insights.append({
                                "type": "Statistical Anomaly / Outliers",
                                "statement": (
                                    f"Identified {outliers_count} extreme outlier observations ({pct_outliers}% of data) "
                                    f"in '{c}' exceeding 3 standard deviations from the mean (Mean: {mean_val:,.2f}, Std: {std_val:,.2f})."
                                ),
                                "metric": f"{outliers_count} outliers (|Z| > 3.0)",
                                "columns_involved": [c],
                                "records_considered": len(s),
                                "method": "Z-score parametric outlier detection (Threshold: 3.0 Sigma)",
                                "confidence": "High",
                                "severity": "Medium" if outliers_count < 5 else "High",
                                "limitations": "Assumes underlying values follow a bell-shaped distribution. Extreme values may represent high-value transactions rather than errors.",
                            })
                            break
            except Exception:
                pass

        # -------------------------------------------------------------
        # 3. Strongest Correlation Insight
        # -------------------------------------------------------------
        if len(num_cols) >= 2:
            try:
                corr_df = df[num_cols].dropna().corr()
                max_corr = 0.0
                best_pair = None
                for i in range(len(num_cols)):
                    for j in range(i + 1, len(num_cols)):
                        c1, c2 = num_cols[i], num_cols[j]
                        val = corr_df.loc[c1, c2]
                        if not math.isnan(val) and abs(val) > abs(max_corr):
                            max_corr = val
                            best_pair = (c1, c2)

                if best_pair and abs(max_corr) >= 0.5:
                    direction = "positive" if max_corr > 0 else "negative"
                    strength = "strong" if abs(max_corr) >= 0.7 else "moderate"
                    insights.append({
                        "type": "Bivariate Relationship",
                        "statement": (
                            f"Discovered a {strength} {direction} correlation (r = {max_corr:.3f}) "
                            f"between '{best_pair[0]}' and '{best_pair[1]}'."
                        ),
                        "metric": f"r = {round(max_corr, 3)}",
                        "columns_involved": list(best_pair),
                        "records_considered": len(df[num_cols].dropna()),
                        "method": "Pearson pairwise correlation coefficient",
                        "confidence": "High",
                        "severity": "Low",
                        "limitations": "Correlation demonstrates co-movement; it does NOT establish causal relationship or mechanism.",
                    })
            except Exception:
                pass

        # -------------------------------------------------------------
        # 4. Data Hygiene & Missingness Warning
        # -------------------------------------------------------------
        null_counts = df.isnull().sum()
        cols_with_nulls = null_counts[null_counts > 0]
        if not cols_with_nulls.empty:
            worst_col = cols_with_nulls.idxmax()
            worst_cnt = int(cols_with_nulls.max())
            worst_pct = round((worst_cnt / len(df)) * 100.0, 1)

            if worst_pct >= 5.0:
                insights.append({
                    "type": "Data Hygiene & Completeness",
                    "statement": (
                        f"Column '{worst_col}' has {worst_cnt:,} missing entries "
                        f"({worst_pct}% of total records), which may introduce bias in aggregations."
                    ),
                    "metric": f"{worst_pct}% missing",
                    "columns_involved": [worst_col],
                    "records_considered": len(df),
                    "method": "Column completeness analysis",
                    "confidence": "High",
                    "severity": "High" if worst_pct >= 20.0 else "Medium",
                    "limitations": "Estimates based on missing value counts. Dropping rows may skew category representations.",
                })

        return insights[:5]
