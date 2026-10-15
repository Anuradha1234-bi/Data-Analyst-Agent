"""Statistics Tool - Deep Descriptive, Trend, Distribution, Correlation, and Cross-Dataset Analysis Engine.

Performs deterministic, non-hallucinatory statistical calculations across tabular datasets:
1. Complete Dataset Statistical Summaries
2. Chronological & Time-Series Trend Detection (slope, percentage change, peaks, drops, sudden shifts)
3. Top / Bottom Entity & Segment Performance Rankings (with concentration ratios)
4. Distribution Shape Analysis (skewness, kurtosis, variance classification)
5. Correlation Analysis (strong positive/negative with strict non-causal language)
6. Categorical Frequency & Imbalance Diagnostics
7. Safe Cross-Dataset Linkage Aggregations
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import re
from datetime import datetime
import numpy as np
import pandas as pd

from tools.anomaly_tool import AnomalyTool
from models.insight import (
    TrendAnalysisResult,
    TopBottomCategoryResult,
    DistributionAnalysisResult,
    CorrelationPair,
    CorrelationAnalysisResult,
    CategoryBreakdownItem,
    CategoryBreakdownResult,
    CrossDatasetInsightResult,
    DatasetAnalysisResult,
)


class StatisticsTool:
    """Comprehensive statistical computing engine for tabular datasets."""

    def __init__(self, strong_corr_threshold: float = 0.70):
        self.strong_corr_threshold = strong_corr_threshold
        self.version = "Phase 5 - Intelligent Data Analysis Engine"

    # =========================================================================
    # COLUMN TYPE INFERENCE & ID FILTERING
    # =========================================================================

    @classmethod
    def get_feature_types(cls, df: pd.DataFrame) -> Dict[str, List[str]]:
        """Classify DataFrame columns into semantic categories while excluding index/ID artifacts."""
        numeric_cols = []
        categorical_cols = []
        date_cols = []
        id_cols = []

        for col in df.columns:
            series = df[col]
            is_id, _ = AnomalyTool.is_id_or_index_column(series, str(col))
            if is_id:
                id_cols.append(str(col))
                continue

            # Check if datetime
            if pd.api.types.is_datetime64_any_dtype(series):
                date_cols.append(str(col))
            elif pd.api.types.is_numeric_dtype(series):
                # Check if it could be a date encoded as string or number (e.g. 20230101)
                col_lower = str(col).lower()
                if "date" in col_lower or "time" in col_lower or "day" in col_lower or "year" in col_lower:
                    try:
                        sample = series.dropna().head(10)
                        if len(sample) > 0 and pd.to_datetime(sample, errors="coerce").notna().all():
                            date_cols.append(str(col))
                            continue
                    except Exception:
                        pass
                numeric_cols.append(str(col))
            else:
                # String / Categorical / Date detection
                col_lower = str(col).lower()
                is_date = False
                if any(k in col_lower for k in ["date", "time", "day", "month", "timestamp", "period"]):
                    try:
                        sample = series.dropna().head(20)
                        if len(sample) > 0:
                            parsed = pd.to_datetime(sample, errors="coerce")
                            if parsed.notna().mean() >= 0.8:
                                date_cols.append(str(col))
                                is_date = True
                    except Exception:
                        pass

                if not is_date:
                    # Check unique cardinality: if non-numeric and reasonable unique count
                    categorical_cols.append(str(col))

        return {
            "numeric": numeric_cols,
            "categorical": categorical_cols,
            "date": date_cols,
            "id": id_cols,
        }

    # =========================================================================
    # 1. DATASET STATISTICAL SUMMARY & DISTRIBUTIONS
    # =========================================================================

    @classmethod
    def analyze_distributions(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "dataset.csv",
        columns: Optional[List[str]] = None,
    ) -> Dict[str, DistributionAnalysisResult]:
        """Compute complete parametric and non-parametric shape metrics for numeric columns."""
        results: Dict[str, DistributionAnalysisResult] = {}
        if df is None or df.empty:
            return results

        feature_types = cls.get_feature_types(df)
        target_cols = columns or feature_types["numeric"]

        for col in target_cols:
            if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
                continue

            series = df[col].dropna()
            count = len(series)
            if count == 0:
                continue

            # Basic moments
            mean_val = float(series.mean())
            median_val = float(series.median())
            std_val = float(series.std(ddof=1)) if count > 1 else 0.0
            var_val = float(series.var(ddof=1)) if count > 1 else 0.0
            min_val = float(series.min())
            max_val = float(series.max())

            # Quartiles
            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            iqr = q3 - q1

            # Skewness & Kurtosis
            skew_val = float(series.skew()) if count > 2 else 0.0
            if np.isnan(skew_val):
                skew_val = 0.0
            kurt_val = float(series.kurt()) if count > 3 else 0.0
            if np.isnan(kurt_val):
                kurt_val = 0.0

            # Shape classification
            is_skewed = abs(skew_val) >= 0.8
            cv = (std_val / abs(mean_val)) if abs(mean_val) > 1e-9 else 0.0
            is_high_variance = cv > 1.0 or (var_val > 1e6 and std_val > 1000)

            if abs(skew_val) < 0.5 and abs(kurt_val) < 1.0:
                shape_label = "Normal-like (Symmetric)"
            elif skew_val >= 0.8:
                shape_label = "Right-skewed (Positive Tail)"
            elif skew_val <= -0.8:
                shape_label = "Left-skewed (Negative Tail)"
            elif is_high_variance:
                shape_label = "High Variance (Dispersed)"
            elif std_val < 1e-5 or series.nunique() <= 2:
                shape_label = "Low Variance (Concentrated)"
            else:
                shape_label = "Moderately Skewed"

            results[col] = DistributionAnalysisResult(
                dataset_name=dataset_name,
                column=col,
                count=count,
                mean=round(mean_val, 4),
                median=round(median_val, 4),
                std=round(std_val, 4),
                variance=round(var_val, 4),
                min_val=round(min_val, 4),
                max_val=round(max_val, 4),
                q1=round(q1, 4),
                q3=round(q3, 4),
                iqr=round(iqr, 4),
                skewness=round(skew_val, 4),
                kurtosis=round(kurt_val, 4),
                shape_label=shape_label,
                is_skewed=is_skewed,
                is_high_variance=is_high_variance,
            )

        return results

    # =========================================================================
    # 2. CHRONOLOGICAL TREND DETECTION
    # =========================================================================

    @classmethod
    def detect_trends(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "dataset.csv",
        date_col: Optional[str] = None,
        metric_col: Optional[str] = None,
    ) -> List[TrendAnalysisResult]:
        """Detect deterministic time-based trends, peaks, drops, and sudden movements."""
        results: List[TrendAnalysisResult] = []
        if df is None or df.empty:
            return results

        feature_types = cls.get_feature_types(df)
        candidate_dates = [date_col] if date_col and date_col in df.columns else feature_types["date"]
        candidate_metrics = [metric_col] if metric_col and metric_col in df.columns else feature_types["numeric"]

        if not candidate_dates or not candidate_metrics:
            return results

        target_date = candidate_dates[0]

        # Parse date column safely
        try:
            date_series = pd.to_datetime(df[target_date], errors="coerce")
            valid_mask = date_series.notna()
            if valid_mask.sum() < 3:
                return results
        except Exception:
            return results

        # Iterate over primary numeric metrics (limit to top 4 for performance)
        for metric in candidate_metrics[:4]:
            if metric not in df.columns or not pd.api.types.is_numeric_dtype(df[metric]):
                continue

            sub_df = pd.DataFrame({
                "date": date_series[valid_mask],
                "val": pd.to_numeric(df[metric][valid_mask], errors="coerce"),
            }).dropna().sort_values("date")

            if len(sub_df) < 3:
                continue

            # Group by date if multiple entries per timestamp
            grouped = sub_df.groupby("date")["val"].mean().reset_index()
            if len(grouped) < 3:
                continue

            start_date_str = grouped["date"].iloc[0].strftime("%Y-%m-%d")
            end_date_str = grouped["date"].iloc[-1].strftime("%Y-%m-%d")
            start_val = float(grouped["val"].iloc[0])
            end_val = float(grouped["val"].iloc[-1])

            # Calculate change percentage
            if abs(start_val) > 1e-9:
                change_pct = round(((end_val - start_val) / abs(start_val)) * 100.0, 2)
            else:
                change_pct = 0.0

            # Direction classification via linear slope
            x_vals = np.arange(len(grouped))
            y_vals = grouped["val"].values
            slope = 0.0
            if len(x_vals) > 1 and np.var(x_vals) > 0:
                slope, _ = np.polyfit(x_vals, y_vals, 1)

            # Volatility check: coefficient of variation of differences
            diffs = np.diff(y_vals)
            avg_val = np.mean(y_vals)
            rel_volatility = np.std(diffs) / abs(avg_val) if abs(avg_val) > 1e-9 else 0.0

            if rel_volatility > 0.35 and abs(change_pct) < 15.0:
                direction = "Volatile / Fluctuating"
            elif change_pct >= 5.0 or slope > 0.05 * (np.std(y_vals) + 1e-5):
                direction = "Increasing"
            elif change_pct <= -5.0 or slope < -0.05 * (np.std(y_vals) + 1e-5):
                direction = "Decreasing"
            else:
                direction = "Stable"

            # Peak & Trough
            max_idx = grouped["val"].idxmax()
            min_idx = grouped["val"].idxmin()
            peak_date = grouped["date"].loc[max_idx].strftime("%Y-%m-%d")
            peak_val = float(grouped["val"].loc[max_idx])
            trough_date = grouped["date"].loc[min_idx].strftime("%Y-%m-%d")
            trough_val = float(grouped["val"].loc[min_idx])

            # Sudden changes: steps where day-over-day change exceeds 2.5x standard deviation of steps
            sudden_changes = []
            if len(diffs) >= 4:
                std_diff = np.std(diffs)
                mean_diff = np.mean(diffs)
                threshold = max(std_diff * 2.2, abs(avg_val) * 0.15)
                for i, d in enumerate(diffs):
                    if abs(d - mean_diff) > threshold and threshold > 0:
                        change_date = grouped["date"].iloc[i + 1].strftime("%Y-%m-%d")
                        prev_date = grouped["date"].iloc[i].strftime("%Y-%m-%d")
                        prev_v = float(grouped["val"].iloc[i])
                        curr_v = float(grouped["val"].iloc[i + 1])
                        pct = round(((curr_v - prev_v) / abs(prev_v) * 100.0) if abs(prev_v) > 1e-9 else 0.0, 1)
                        sudden_changes.append({
                            "date": change_date,
                            "previous_date": prev_date,
                            "previous_value": round(prev_v, 2),
                            "current_value": round(curr_v, 2),
                            "change_pct": pct,
                            "type": "Sharp Spike" if d > 0 else "Sudden Drop",
                        })

            results.append(TrendAnalysisResult(
                dataset_name=dataset_name,
                date_column=target_date,
                metric_column=metric,
                start_date=start_date_str,
                end_date=end_date_str,
                start_value=round(start_val, 2),
                end_value=round(end_val, 2),
                change_pct=change_pct,
                direction=direction,
                peak_date=peak_date,
                peak_value=round(peak_val, 2),
                trough_date=trough_date,
                trough_value=round(trough_val, 2),
                sudden_changes=sudden_changes[:5],
                records_analyzed=len(grouped),
                timeseries_df=grouped.rename(columns={"date": target_date, "val": metric}),
            ))

        return results

    # =========================================================================
    # 3. TOP / BOTTOM CATEGORY PERFORMANCE ANALYSIS
    # =========================================================================

    @classmethod
    def analyze_top_bottom(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "dataset.csv",
        category_col: Optional[str] = None,
        metric_col: Optional[str] = None,
    ) -> List[TopBottomCategoryResult]:
        """Rank categorical entities by volume/value with concentration ratios."""
        results: List[TopBottomCategoryResult] = []
        if df is None or df.empty:
            return results

        feature_types = cls.get_feature_types(df)
        cat_candidates = [category_col] if category_col and category_col in df.columns else feature_types["categorical"]
        metric_candidates = [metric_col] if metric_col and metric_col in df.columns else feature_types["numeric"]

        if not cat_candidates or not metric_candidates:
            return results

        # Limit to top 2 meaningful categorical dimensions and top 2 metrics
        for cat in cat_candidates[:2]:
            if df[cat].nunique() < 2 or df[cat].nunique() > 200:
                continue

            for met in metric_candidates[:2]:
                if not pd.api.types.is_numeric_dtype(df[met]):
                    continue

                clean_sub = df[[cat, met]].dropna()
                if clean_sub.empty:
                    continue

                grouped = clean_sub.groupby(cat)[met].agg(["sum", "mean", "count"]).reset_index()
                if grouped.empty:
                    continue

                total_sum = float(grouped["sum"].sum())
                if total_sum <= 0:
                    # If metric is not summable (e.g. rate or temperature), rank by mean
                    agg_type = "mean"
                    sort_col = "mean"
                    total_metric_val = float(grouped["mean"].mean())
                else:
                    agg_type = "sum"
                    sort_col = "sum"
                    total_metric_val = total_sum

                grouped_sorted = grouped.sort_values(sort_col, ascending=False)
                total_cats = len(grouped_sorted)

                # Format top items
                top_items = []
                for _, r in grouped_sorted.head(5).iterrows():
                    val = float(r[sort_col])
                    share = round((val / total_metric_val * 100.0) if total_metric_val > 0 else 0.0, 2)
                    top_items.append({
                        "category": str(r[cat]),
                        "value": round(val, 2),
                        "mean_value": round(float(r["mean"]), 2),
                        "count": int(r["count"]),
                        "share_pct": share,
                    })

                # Format bottom items
                bottom_items = []
                for _, r in grouped_sorted.tail(5).iloc[::-1].iterrows():
                    val = float(r[sort_col])
                    share = round((val / total_metric_val * 100.0) if total_metric_val > 0 else 0.0, 2)
                    bottom_items.append({
                        "category": str(r[cat]),
                        "value": round(val, 2),
                        "mean_value": round(float(r["mean"]), 2),
                        "count": int(r["count"]),
                        "share_pct": share,
                    })

                # Concentration ratio of top 3
                top3_sum = float(grouped_sorted.head(3)[sort_col].sum())
                conc_top3 = round((top3_sum / total_metric_val * 100.0) if total_metric_val > 0 else 0.0, 2)

                results.append(TopBottomCategoryResult(
                    dataset_name=dataset_name,
                    category_column=cat,
                    metric_column=met,
                    aggregation=agg_type,
                    top_items=top_items,
                    bottom_items=bottom_items,
                    total_metric_value=round(total_metric_val, 2),
                    concentration_ratio_top3=conc_top3,
                    total_categories=total_cats,
                ))

        return results

    # =========================================================================
    # 4. CORRELATION ANALYSIS (STRICT NON-CAUSAL LANGUAGE)
    # =========================================================================

    @classmethod
    def analyze_correlations(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "dataset.csv",
        threshold: float = 0.70,
    ) -> Optional[CorrelationAnalysisResult]:
        """Compute Pearson correlation matrix and flag strong positive/negative associations."""
        if df is None or df.empty:
            return None

        feature_types = cls.get_feature_types(df)
        num_cols = [c for c in feature_types["numeric"] if df[c].nunique() > 1]
        if len(num_cols) < 2:
            return None

        # Compute pairwise correlations
        corr_matrix_df = df[num_cols].corr(method="pearson")
        matrix_dict: Dict[str, Dict[str, float]] = {}
        for c1 in num_cols:
            matrix_dict[c1] = {}
            for c2 in num_cols:
                val = corr_matrix_df.loc[c1, c2]
                matrix_dict[c1][c2] = round(float(val), 4) if pd.notna(val) else 0.0

        strong_pos: List[CorrelationPair] = []
        strong_neg: List[CorrelationPair] = []
        moderate: List[CorrelationPair] = []

        seen_pairs = set()
        for i, c1 in enumerate(num_cols):
            for j in range(i + 1, len(num_cols)):
                c2 = num_cols[j]
                r = corr_matrix_df.loc[c1, c2]
                if pd.isna(r):
                    continue

                r_val = round(float(r), 4)
                pair_key = tuple(sorted([c1, c2]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                if r_val >= threshold:
                    strength = "Strong Positive"
                    stmt = f"Features `{c1}` and `{c2}` exhibit a strong positive statistical association (r = +{r_val:.2f})."
                    strong_pos.append(CorrelationPair(c1, c2, r_val, strength, stmt))
                elif r_val <= -threshold:
                    strength = "Strong Negative"
                    stmt = f"Features `{c1}` and `{c2}` exhibit a strong negative statistical association (r = {r_val:.2f})."
                    strong_neg.append(CorrelationPair(c1, c2, r_val, strength, stmt))
                elif abs(r_val) >= 0.40:
                    strength = "Moderate Positive" if r_val > 0 else "Moderate Negative"
                    stmt = f"Features `{c1}` and `{c2}` show a moderate statistical association (r = {r_val:+.2f})."
                    moderate.append(CorrelationPair(c1, c2, r_val, strength, stmt))

        # Sort pairs by absolute correlation descending
        strong_pos.sort(key=lambda p: abs(p.correlation), reverse=True)
        strong_neg.sort(key=lambda p: abs(p.correlation), reverse=True)
        moderate.sort(key=lambda p: abs(p.correlation), reverse=True)

        return CorrelationAnalysisResult(
            dataset_name=dataset_name,
            features_analyzed=num_cols,
            correlation_matrix=matrix_dict,
            strong_positive_pairs=strong_pos,
            strong_negative_pairs=strong_neg,
            moderate_pairs=moderate,
        )

    # =========================================================================
    # 5. CATEGORY FREQUENCY & IMBALANCE ANALYSIS
    # =========================================================================

    @classmethod
    def analyze_categories(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "dataset.csv",
        columns: Optional[List[str]] = None,
    ) -> Dict[str, CategoryBreakdownResult]:
        """Compute category distributions, top/bottom shares, and imbalance detection."""
        results: Dict[str, CategoryBreakdownResult] = {}
        if df is None or df.empty:
            return results

        feature_types = cls.get_feature_types(df)
        target_cols = columns or feature_types["categorical"]

        for col in target_cols:
            if col not in df.columns:
                continue

            series = df[col].dropna()
            total_non_null = len(series)
            if total_non_null == 0:
                continue

            val_counts = series.value_counts()
            unique_count = len(val_counts)
            if unique_count == 0:
                continue

            items: List[CategoryBreakdownItem] = []
            for cat_name, cnt in val_counts.head(10).items():
                pct = round((cnt / total_non_null) * 100.0, 2)
                items.append(CategoryBreakdownItem(category=str(cat_name), count=int(cnt), percentage=pct))

            most_frequent = str(val_counts.index[0])
            most_frequent_pct = round((val_counts.iloc[0] / total_non_null) * 100.0, 2)
            least_frequent = str(val_counts.index[-1])
            least_frequent_pct = round((val_counts.iloc[-1] / total_non_null) * 100.0, 2)

            # Imbalance: top category dominates > 60% or top 2 dominate > 85%
            is_imbalanced = False
            imbalance_expl = "Balanced distribution"
            if most_frequent_pct >= 60.0:
                is_imbalanced = True
                imbalance_expl = f"High category concentration: '{most_frequent}' accounts for {most_frequent_pct}% of non-null records."
            elif unique_count >= 3 and (val_counts.iloc[:2].sum() / total_non_null * 100.0) >= 85.0:
                is_imbalanced = True
                imbalance_expl = f"Duopoly concentration: Top 2 categories constitute {round(val_counts.iloc[:2].sum() / total_non_null * 100.0, 1)}% of volume."

            results[col] = CategoryBreakdownResult(
                dataset_name=dataset_name,
                column=col,
                unique_count=unique_count,
                total_non_null=total_non_null,
                items=items,
                most_frequent=most_frequent,
                most_frequent_pct=most_frequent_pct,
                least_frequent=least_frequent,
                least_frequent_pct=least_frequent_pct,
                is_imbalanced=is_imbalanced,
                imbalance_explanation=imbalance_expl,
            )

        return results

    # =========================================================================
    # 6. CROSS-DATASET LINKAGE & DUPLICATE PROTECTION
    # =========================================================================

    @classmethod
    def analyze_cross_dataset(
        cls,
        left_df: pd.DataFrame,
        left_name: str,
        right_df: pd.DataFrame,
        right_name: str,
        relationship: Any,
    ) -> CrossDatasetInsightResult:
        """Safely join two datasets on a validated relationship and aggregate key metrics."""
        left_key = relationship.source_column
        right_key = relationship.target_column
        conf = getattr(relationship, "confidence", "HIGH")

        # Duplicate protection & Many-to-Many safeguard
        left_dups = left_df[left_key].duplicated().sum() if left_key in left_df.columns else 0
        right_dups = right_df[right_key].duplicated().sum() if right_key in right_df.columns else 0

        # Many-to-Many explosion check
        if left_dups > 0 and right_dups > 0:
            return CrossDatasetInsightResult(
                left_dataset=left_name,
                right_dataset=right_name,
                join_key=f"{left_key} <-> {right_key}",
                relationship_confidence=conf,
                join_type="inner",
                is_blocked=True,
                block_reason="Cross-file analysis blocked. Reason: Potential many-to-many relationship may duplicate records.",
                rows_before=len(left_df),
                rows_after=0,
            )

        try:
            merged = pd.merge(
                left_df,
                right_df,
                left_on=left_key,
                right_on=right_key,
                how="inner",
                suffixes=(f"_{left_name[:4]}", f"_{right_name[:4]}"),
            )
            rows_after = len(merged)

            # Safeguard row multiplication
            if rows_after > len(left_df) * 1.5:
                return CrossDatasetInsightResult(
                    left_dataset=left_name,
                    right_dataset=right_name,
                    join_key=f"{left_key} <-> {right_key}",
                    relationship_confidence=conf,
                    join_type="inner",
                    is_blocked=True,
                    block_reason=f"Cross-file analysis blocked: Join resulted in unexpected row multiplication ({len(left_df)} -> {rows_after} rows).",
                    rows_before=len(left_df),
                    rows_after=rows_after,
                )

            # Find suitable numerical metric from left or right and categorical from the other
            left_num = [c for c in left_df.select_dtypes(include=["number"]).columns if c != left_key]
            right_cat = [c for c in right_df.select_dtypes(include=["object", "category"]).columns if c != right_key]

            breakdown_list = []
            metric_chosen = None
            group_chosen = None

            if left_num and right_cat:
                metric_chosen = left_num[0]
                group_chosen = right_cat[0]
                # Check for suffixed column names in merged
                m_col = metric_chosen if metric_chosen in merged.columns else f"{metric_chosen}_{left_name[:4]}"
                g_col = group_chosen if group_chosen in merged.columns else f"{group_chosen}_{right_name[:4]}"

                if m_col in merged.columns and g_col in merged.columns:
                    grp = merged.groupby(g_col)[m_col].agg(["sum", "mean", "count"]).reset_index()
                    grp = grp.sort_values("sum", ascending=False).head(10)
                    for _, r in grp.iterrows():
                        breakdown_list.append({
                            "entity": str(r[g_col]),
                            "total": round(float(r["sum"]), 2),
                            "average": round(float(r["mean"]), 2),
                            "records": int(r["count"]),
                        })

            return CrossDatasetInsightResult(
                left_dataset=left_name,
                right_dataset=right_name,
                join_key=f"{left_key} <-> {right_key}",
                relationship_confidence=conf,
                join_type="inner",
                is_blocked=False,
                block_reason=None,
                rows_before=len(left_df),
                rows_after=rows_after,
                metric_column=metric_chosen,
                group_column=group_chosen,
                breakdown=breakdown_list,
            )

        except Exception as e:
            return CrossDatasetInsightResult(
                left_dataset=left_name,
                right_dataset=right_name,
                join_key=f"{left_key} <-> {right_key}",
                relationship_confidence=conf,
                join_type="inner",
                is_blocked=True,
                block_reason=f"Join failed: {str(e)}",
                rows_before=len(left_df),
                rows_after=0,
            )

    # =========================================================================
    # 7. UNIFIED DATASET ANALYSIS ORCHESTRATION
    # =========================================================================

    @classmethod
    def compute_summary(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "dataset.csv",
    ) -> DatasetAnalysisResult:
        """Execute complete Phase 5 statistical pipeline for an individual dataset."""
        if df is None or df.empty:
            return DatasetAnalysisResult(
                dataset_name=dataset_name,
                row_count=0,
                column_count=0,
            )

        feature_types = cls.get_feature_types(df)
        total_cells = df.size
        missing_count = int(df.isna().sum().sum())
        missing_rate = round((missing_count / total_cells * 100.0) if total_cells > 0 else 0.0, 2)
        duplicate_rows = int(df.duplicated().sum())
        duplicate_rate = round((duplicate_rows / len(df) * 100.0) if len(df) > 0 else 0.0, 2)

        # 1. Distributions
        distributions = cls.analyze_distributions(df, dataset_name)

        # 2. Trends
        trends = cls.detect_trends(df, dataset_name)

        # 3. Top / Bottom Rankings
        top_bottom = cls.analyze_top_bottom(df, dataset_name)

        # 4. Correlations
        correlations = cls.analyze_correlations(df, dataset_name)

        # 5. Categories
        categories = cls.analyze_categories(df, dataset_name)

        return DatasetAnalysisResult(
            dataset_name=dataset_name,
            row_count=len(df),
            column_count=len(df.columns),
            numeric_columns=feature_types["numeric"],
            categorical_columns=feature_types["categorical"],
            date_columns=feature_types["date"],
            missing_count=missing_count,
            missing_rate=missing_rate,
            duplicate_rows=duplicate_rows,
            duplicate_rate=duplicate_rate,
            distributions=distributions,
            trends=trends,
            top_bottom_rankings=top_bottom,
            correlations=correlations,
            categories=categories,
        )

    # =========================================================================
    # CONCRETE MODULE CONTRACTS (MODULES 1 - 6)
    # =========================================================================

    @classmethod
    def statistical_analysis(cls, df: pd.DataFrame, selected_columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """MODULE 1 CONTRACT: Reusable statistical and distribution calculations."""
        if df is None or df.empty:
            return {
                "status": "error",
                "error_type": "EmptyDataError",
                "message": "DataFrame is empty or None",
                "details": "Cannot calculate statistics on an empty dataset",
            }
        try:
            dists = cls.analyze_distributions(df, columns=selected_columns)
            corrs = cls.analyze_correlations(df)
            cats = cls.analyze_categories(df)

            col_stats = {}
            dist_stats = {}
            for col, d in dists.items():
                col_stats[col] = {
                    "count": d.count,
                    "mean": d.mean,
                    "median": d.median,
                    "std": d.std,
                    "variance": d.variance,
                    "min": d.min_val,
                    "max": d.max_val,
                    "q1": d.q1,
                    "q3": d.q3,
                    "iqr": d.iqr,
                    "skewness": d.skewness,
                    "kurtosis": d.kurtosis,
                }
                dist_stats[col] = {
                    "shape": d.shape_label,
                    "is_skewed": d.is_skewed,
                    "is_high_variance": d.is_high_variance,
                }

            return {
                "status": "success",
                "column_statistics": col_stats,
                "distribution_statistics": dist_stats,
                "correlations": corrs.correlation_matrix if corrs else {},
                "category_statistics": {c: cb.unique_count for c, cb in cats.items()},
            }
        except Exception as e:
            return {
                "status": "error",
                "error_type": type(e).__name__,
                "message": str(e),
                "details": "Error encountered during statistical analysis execution",
            }

    @classmethod
    def trend_analysis(
        cls,
        df: pd.DataFrame,
        date_column: Optional[str] = None,
        numeric_columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """MODULE 2 CONTRACT: Chronological trend analysis."""
        if df is None or df.empty:
            return {
                "status": "error",
                "error_type": "EmptyDataError",
                "message": "DataFrame is empty",
                "details": "Cannot detect trends on an empty dataset",
            }

        ft = cls.get_feature_types(df)
        target_dates = [date_column] if date_column and date_column in df.columns else ft["date"]
        if not target_dates:
            return {
                "status": "unavailable",
                "reason": "No valid date column detected",
            }

        trends_list = cls.detect_trends(
            df,
            date_col=target_dates[0],
            metric_col=(numeric_columns[0] if numeric_columns else None),
        )
        if not trends_list:
            return {
                "status": "unavailable",
                "reason": "No suitable numerical features or insufficient time points to compute trend trajectory",
            }

        trends = []
        changes = []
        peaks = []
        drops = []

        for tr in trends_list:
            trends.append({
                "column": tr.metric_column,
                "direction": tr.direction.lower(),
                "change_percentage": tr.change_pct,
                "start_value": tr.start_value,
                "end_value": tr.end_value,
                "start_date": tr.start_date,
                "end_date": tr.end_date,
            })
            peaks.append({"column": tr.metric_column, "date": tr.peak_date, "value": tr.peak_value})
            drops.append({"column": tr.metric_column, "date": tr.trough_date, "value": tr.trough_value})
            changes.extend(tr.sudden_changes)

        return {
            "status": "success",
            "date_column": target_dates[0],
            "trends": trends,
            "changes": changes,
            "peaks": peaks,
            "drops": drops,
        }

    @classmethod
    def correlation_analysis(
        cls,
        df: pd.DataFrame,
        numeric_columns: Optional[List[str]] = None,
        threshold: float = 0.70,
    ) -> Dict[str, Any]:
        """MODULE 3 CONTRACT: Correlation analysis with strict non-causal language."""
        if df is None or df.empty:
            return {
                "status": "error",
                "error_type": "EmptyDataError",
                "message": "DataFrame is empty",
                "details": "Cannot calculate correlations on empty dataset",
            }

        c_res = cls.analyze_correlations(df, threshold=threshold)
        if not c_res or not c_res.features_analyzed:
            return {
                "status": "unavailable",
                "reason": "Insufficient numeric columns (minimum 2 required)",
            }

        relationships = []
        all_pairs = c_res.strong_positive_pairs + c_res.strong_negative_pairs + c_res.moderate_pairs
        for p in all_pairs:
            direction = "positive" if p.correlation > 0 else "negative"
            strength = "strong" if "Strong" in p.strength else "moderate"
            relationships.append({
                "column_a": p.feature_x,
                "column_b": p.feature_y,
                "correlation": p.correlation,
                "strength": strength,
                "direction": direction,
                "statement": p.non_causal_statement,
            })

        return {
            "status": "success",
            "matrix": c_res.correlation_matrix,
            "relationships": relationships,
        }

    @classmethod
    def category_analysis(
        cls,
        df: pd.DataFrame,
        categorical_columns: Optional[List[str]] = None,
        numeric_columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """MODULE 4 CONTRACT: Categorical distributions and top/bottom aggregations."""
        if df is None or df.empty:
            return {
                "status": "error",
                "error_type": "EmptyDataError",
                "message": "DataFrame is empty",
                "details": "Cannot perform category analysis on empty dataset",
            }

        ft = cls.get_feature_types(df)
        cat_cols = categorical_columns or ft["categorical"]
        if not cat_cols:
            return {
                "status": "unavailable",
                "reason": "No categorical columns found",
            }

        cats = cls.analyze_categories(df, columns=cat_cols)
        tb_list = cls.analyze_top_bottom(df, category_col=(cat_cols[0] if cat_cols else None))

        distributions = []
        for col, cb in cats.items():
            distributions.append({
                "column": col,
                "unique_count": cb.unique_count,
                "most_frequent": cb.most_frequent,
                "most_frequent_percentage": cb.most_frequent_pct,
                "least_frequent": cb.least_frequent,
                "least_frequent_percentage": cb.least_frequent_pct,
                "is_imbalanced": cb.is_imbalanced,
                "imbalance_explanation": cb.imbalance_explanation,
                "categories": [{"category": it.category, "count": it.count, "percentage": it.percentage} for it in cb.items],
            })

        top_categories = []
        bottom_categories = []
        for tb in tb_list:
            top_categories.append({
                "category_column": tb.category_column,
                "metric_column": tb.metric_column,
                "aggregation": tb.aggregation,
                "concentration_ratio_top3": tb.concentration_ratio_top3,
                "items": tb.top_items,
            })
            bottom_categories.append({
                "category_column": tb.category_column,
                "metric_column": tb.metric_column,
                "aggregation": tb.aggregation,
                "items": tb.bottom_items,
            })

        return {
            "status": "success",
            "distributions": distributions,
            "top_categories": top_categories,
            "bottom_categories": bottom_categories,
        }

    @classmethod
    def anomaly_integration(cls, anomaly_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """MODULE 5 CONTRACT: Ingest existing Phase 4 anomaly results without rerunning detection."""
        if not anomaly_results or not isinstance(anomaly_results, dict):
            return {
                "status": "unavailable",
                "reason": "No Phase 4 anomaly results provided",
                "anomaly_summary": {
                    "total_anomalies": 0,
                    "iqr_outliers": 0,
                    "isolation_forest_anomalies": 0,
                    "multivariate_anomalies": 0,
                },
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
            iqr_outliers = getattr(iqr_res, "total_outlier_rows", 0)
            total_anom += iqr_outliers
            for c in getattr(iqr_res, "columns_analyzed", []):
                affected_cols.add(c)
            for idx in getattr(iqr_res, "all_outlier_indices", []):
                affected_rows.add(idx)
            method_summary["iqr"] = {
                "outlier_rows": iqr_outliers,
                "outlier_rate": getattr(iqr_res, "outlier_rate", 0.0),
                "multiplier": getattr(iqr_res, "multiplier", 1.5),
            }

        if "isolation_forest" in anomaly_results:
            if_res = anomaly_results["isolation_forest"]
            if_anom = getattr(if_res, "anomaly_count", 0)
            total_anom += if_anom
            for f in getattr(if_res, "features_used", []):
                affected_cols.add(f)
            for idx in getattr(if_res, "anomaly_indices", []):
                affected_rows.add(idx)
            method_summary["isolation_forest"] = {
                "anomaly_count": if_anom,
                "anomaly_pct": getattr(if_res, "anomaly_pct", 0.0),
                "features": getattr(if_res, "features_used", []),
            }

        if "multivariate" in anomaly_results:
            mv_res = anomaly_results["multivariate"]
            mv_anom = getattr(mv_res, "anomaly_count", 0)
            total_anom += mv_anom
            for f in getattr(mv_res, "features_used", []):
                affected_cols.add(f)
            for idx in getattr(mv_res, "all_anomaly_indices", []):
                affected_rows.add(idx)
            method_summary["multivariate"] = {
                "anomaly_count": mv_anom,
                "anomaly_pct": getattr(mv_res, "anomaly_pct", 0.0),
                "features": getattr(mv_res, "features_used", []),
            }

        return {
            "status": "success",
            "anomaly_summary": {
                "total_anomalies": total_anom,
                "iqr_outliers": iqr_outliers,
                "isolation_forest_anomalies": if_anom,
                "multivariate_anomalies": mv_anom,
            },
            "affected_columns": sorted(list(affected_cols)),
            "affected_rows": sorted(list(affected_rows)),
            "method_summary": method_summary,
        }

    @classmethod
    def cross_dataset_analysis(
        cls,
        datasets: Dict[str, pd.DataFrame],
        validated_relationships: List[Any],
        join_audit: Optional[List[Any]] = None,
        analysis_request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """MODULE 6 CONTRACT: Safe cross-dataset analysis with many-to-many guards."""
        if len(datasets) < 2 or not validated_relationships:
            return {
                "status": "unavailable",
                "reason": "Requires at least 2 datasets and at least 1 validated relationship",
            }

        usable_rel = None
        for r in validated_relationships:
            if getattr(r, "confidence", "") == "HIGH" or getattr(r, "confirmed_by_user", False):
                usable_rel = r
                break

        if not usable_rel:
            return {
                "status": "unavailable",
                "reason": "No high-confidence or user-confirmed relationships available",
            }

        left_name = usable_rel.source_dataset
        right_name = usable_rel.target_dataset
        if left_name not in datasets or right_name not in datasets:
            return {
                "status": "error",
                "error_type": "MissingDatasetError",
                "message": f"Datasets `{left_name}` or `{right_name}` not loaded in memory",
            }

        left_df = datasets[left_name]
        right_df = datasets[right_name]

        cross_res = cls.analyze_cross_dataset(
            left_df=left_df,
            left_name=left_name,
            right_df=right_df,
            right_name=right_name,
            relationship=usable_rel,
        )

        rel_str = f"{usable_rel.source_column} <-> {usable_rel.target_column}"

        if cross_res.is_blocked:
            return {
                "status": "blocked",
                "reason": cross_res.block_reason or "Unsafe join detected",
                "datasets_used": [left_name, right_name],
                "relationships_used": [rel_str],
                "rows_before": cross_res.rows_before,
                "rows_after": 0,
            }

        return {
            "status": "success",
            "datasets_used": [left_name, right_name],
            "relationships_used": [rel_str],
            "join_type": cross_res.join_type,
            "rows_before": cross_res.rows_before,
            "rows_after": cross_res.rows_after,
            "analysis": {
                "metric_column": cross_res.metric_column,
                "group_column": cross_res.group_column,
                "breakdown": cross_res.breakdown,
            },
        }
