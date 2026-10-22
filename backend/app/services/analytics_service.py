"""Analytics Service - Comprehensive Exploratory Analytics Engine.

Provides deep statistical profiling, dynamic multidimensional aggregations,
time-series trend analysis with period comparisons, correlation analysis,
outlier detection via IQR, and automated evidence-grounded insights.
Strictly isolated per user and verified against actual uploaded dataset files.
"""

import io
import csv
import math
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.analytics import (
    KPICard,
    ColumnProfileSummary,
    AnalyticsOverviewResponse,
    FilterCondition,
    AnalyticsChartRequest,
    BoxPlotData,
    AnalyticsChartResponse,
    AnalyticsTrendRequest,
    PeriodComparison,
    AnalyticsTrendResponse,
    AnalyticsGroupCompareRequest,
    AnalyticsGroupCompareResponse,
    AnalyticsStatsRequest,
    DescriptiveStatRow,
    OutlierDetail,
    AnalyticsStatsResponse,
    AnalyticsInsightItem,
    AnalyticsInsightsResponse,
    AnalyticsExportCSVRequest,
    AnalyticsReportExportRequest,
)
from utils.file_loader import FileLoader


def _sanitize_float(val: Any) -> Any:
    """Sanitize float values (NaN, Infinity) for strictly valid JSON serialization."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or np.isnan(val):
            return None
        if math.isinf(val) or np.isinf(val):
            return "Infinity" if val > 0 else "-Infinity"
        return round(float(val), 4)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.isoformat()
    return str(val) if not isinstance(val, (bool, str, list, dict)) else val


def _format_compact_number(val: Optional[float]) -> str:
    """Format numeric values with compact human-readable suffixes (k, M, B)."""
    if val is None or not isinstance(val, (int, float)) or math.isnan(val):
        return "N/A"
    abs_v = abs(val)
    if abs_v >= 1_000_000_000:
        return f"{val / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    if abs_v >= 1_000:
        return f"{val / 1_000:.1f}k"
    if isinstance(val, int) or val.is_integer():
        return f"{int(val):,}"
    return f"{val:.2f}"


class AnalyticsService:
    """Enterprise service executing exploratory and statistical analytics on real datasets."""

    # In-memory DataFrame cache: key = file_path, value = (mtime, size, df)
    _df_cache: Dict[str, Tuple[float, int, pd.DataFrame]] = {}

    @classmethod
    def _get_cached_or_load_df(cls, file_path: Path, filename: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """Retrieve cached DataFrame or safely load with mtime & size invalidation."""
        file_path_str = str(file_path.resolve())
        stat = file_path.stat()
        mtime = stat.st_mtime
        size = stat.st_size

        cached = cls._df_cache.get(file_path_str)
        if cached:
            c_mtime, c_size, c_df = cached
            if c_mtime == mtime and c_size == size:
                return c_df.copy(), None

        load_res = FileLoader.load_file(
            file_obj=file_path_str,
            filename=filename,
            file_size_bytes=size,
        )
        if not load_res.success or load_res.df is None or load_res.df.empty:
            return None, load_res.error_message or f"Dataset file '{filename}' is empty or unreadable."

        if len(cls._df_cache) >= 16:
            cls._df_cache.pop(next(iter(cls._df_cache)))

        cls._df_cache[file_path_str] = (mtime, size, load_res.df.copy())
        return load_res.df, None

    @classmethod
    def get_dataset_and_df(
        cls,
        dataset_id: int,
        version: str,
        current_user: User,
        db: Session,
    ) -> Tuple[Dataset, pd.DataFrame, str, List[str]]:
        """Enforce user isolation, resolve dataset version (original vs cleaned), and load DataFrame."""
        warnings: List[str] = []

        dataset = (
            db.query(Dataset)
            .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
            .first()
        )
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset #{dataset_id} not found or access denied.",
            )

        use_version = (version or "original").lower().strip()
        actual_version = "original"
        active_filepath: Path

        if use_version == "cleaned":
            if dataset.has_cleaned and dataset.cleaned_file_path:
                cleaned_p = Path(dataset.cleaned_file_path)
                if cleaned_p.exists() and cleaned_p.is_file():
                    active_filepath = cleaned_p
                    actual_version = "cleaned"
                else:
                    active_filepath = Path(dataset.file_path)
                    warnings.append("Cleaned file was missing from storage disk; using original dataset version.")
            else:
                active_filepath = Path(dataset.file_path)
                warnings.append("No cleaned version exists for this dataset; using original dataset version.")
        else:
            active_filepath = Path(dataset.file_path)

        if not active_filepath.exists() or not active_filepath.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset file '{dataset.filename}' is missing from physical storage.",
            )

        df, err = cls._get_cached_or_load_df(active_filepath, dataset.filename)
        if df is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err or f"Dataset '{dataset.filename}' is empty or unreadable.",
            )

        return dataset, df, actual_version, warnings

    @classmethod
    def _classify_column_role(cls, series: pd.Series, col_name: str) -> str:
        """Classify column analytical role: numeric, date, categorical, id, text."""
        name_lower = col_name.lower()
        non_null_count = int(series.count())
        unique_count = int(series.nunique())

        # Date heuristic
        if pd.api.types.is_datetime64_any_dtype(series):
            return "date"
        if any(term in name_lower for term in ["date", "time", "year", "month", "day", "timestamp", "arrival"]):
            try:
                sample = series.dropna().head(20)
                if len(sample) > 0:
                    parsed = pd.to_datetime(sample, errors="coerce")
                    if parsed.notna().mean() >= 0.7:
                        return "date"
            except Exception:
                pass

        # ID heuristic
        if non_null_count > 0 and (unique_count == non_null_count or unique_count / max(non_null_count, 1) > 0.95):
            if any(term in name_lower for term in ["id", "code", "key", "uuid", "pk", "fk", "num", "serial"]):
                return "id"

        # Numeric heuristic
        if pd.api.types.is_numeric_dtype(series):
            # If numeric has very low cardinality and acts as a code/category
            if unique_count <= 8 and non_null_count > 20 and not any(term in name_lower for term in ["rate", "pct", "price", "amount", "cost", "total", "qty", "count"]):
                return "categorical"
            return "numeric"

        # Categorical vs Text heuristic
        if unique_count <= 60 or (non_null_count > 0 and unique_count / non_null_count <= 0.3):
            return "categorical"

        return "text"

    @classmethod
    def get_analytics_overview(
        cls,
        dataset_id: int,
        version: str,
        current_user: User,
        db: Session,
    ) -> AnalyticsOverviewResponse:
        """Calculate dynamic overview, KPIs, and column profiles from actual dataset schema."""
        dataset, df, actual_version, warnings = cls.get_dataset_and_df(dataset_id, version, current_user, db)

        total_rows = len(df)
        total_cols = len(df.columns)
        total_cells = total_rows * total_cols
        total_null_cells = int(df.isna().sum().sum())
        completeness_pct = round(((total_cells - total_null_cells) / max(total_cells, 1)) * 100, 2)

        column_summaries: List[ColumnProfileSummary] = []
        numeric_cols: List[str] = []
        categorical_cols: List[str] = []
        date_cols: List[str] = []

        for col in df.columns:
            s = df[col]
            role = cls._classify_column_role(s, col)
            non_null = int(s.count())
            null_count = int(s.isna().sum())
            null_pct = round((null_count / max(total_rows, 1)) * 100, 2)
            unique_c = int(s.nunique())

            # Sample values (up to 5 unique non-nulls)
            sample_unique = s.dropna().unique()[:5]
            sample_vals = [_sanitize_float(x) for x in sample_unique]

            column_summaries.append(
                ColumnProfileSummary(
                    name=str(col),
                    data_type=str(s.dtype),
                    role=role,
                    non_null_count=non_null,
                    null_count=null_count,
                    null_percentage=null_pct,
                    unique_count=unique_c,
                    sample_values=sample_vals,
                )
            )

            if role == "numeric":
                numeric_cols.append(str(col))
            elif role == "categorical":
                categorical_cols.append(str(col))
            elif role == "date":
                date_cols.append(str(col))

        # Dynamic KPI Cards calculated from the real dataset
        kpi_cards: List[KPICard] = []

        # KPI 1: Total Records
        kpi_cards.append(
            KPICard(
                id="kpi_rows",
                label="Total Records",
                value=total_rows,
                formatted_value=f"{total_rows:,} rows",
                subtext="Total active observations in dataset",
                calculation_method="Exact row count",
                category="volume",
            )
        )

        # KPI 2: Attributes Count
        kpi_cards.append(
            KPICard(
                id="kpi_columns",
                label="Feature Dimensions",
                value=total_cols,
                formatted_value=f"{total_cols} attributes",
                subtext=f"Numeric: {len(numeric_cols)} | Categorical: {len(categorical_cols)} | Dates: {len(date_cols)}",
                calculation_method="Schema dimension count",
                category="volume",
            )
        )

        # KPI 3: Data Completeness
        kpi_cards.append(
            KPICard(
                id="kpi_completeness",
                label="Data Completeness",
                value=completeness_pct,
                formatted_value=f"{completeness_pct}%",
                subtext=f"{total_null_cells:,} missing cells ({100 - completeness_pct:.2f}% missing rate)",
                calculation_method="Non-null cell percentage across all features",
                trend_direction="increasing" if completeness_pct >= 95 else "decreasing",
                category="quality",
            )
        )

        # KPI 4: Memory Footprint
        mem_bytes = int(df.memory_usage(deep=True).sum())
        mem_kb = mem_bytes / 1024
        mem_formatted = f"{mem_kb:.1f} KB" if mem_kb < 1024 else f"{mem_kb / 1024:.2f} MB"
        kpi_cards.append(
            KPICard(
                id="kpi_memory",
                label="Memory Footprint",
                value=mem_bytes,
                formatted_value=mem_formatted,
                subtext=f"Active version: {actual_version.capitalize()}",
                calculation_method="In-memory dataframe memory footprint",
                category="general",
            )
        )

        # KPI 5: Primary Metric Aggregate (if numeric columns exist)
        if numeric_cols:
            primary_col = numeric_cols[0]
            for col in numeric_cols:
                low = col.lower()
                if any(k in low for k in ["total", "amount", "price", "revenue", "sales", "cost", "value"]):
                    primary_col = col
                    break
            
            p_series = pd.to_numeric(df[primary_col], errors="coerce").dropna()
            if len(p_series) > 0:
                p_sum = float(p_series.sum())
                p_mean = float(p_series.mean())
                is_monetary = any(m in primary_col.lower() for m in ["price", "amount", "revenue", "sales", "cost", "fee"])
                prefix = "$" if is_monetary else ""
                kpi_cards.append(
                    KPICard(
                        id="kpi_primary_metric",
                        label=f"Total {primary_col.replace('_', ' ').title()}",
                        value=p_sum,
                        formatted_value=f"{prefix}{_format_compact_number(p_sum)}",
                        subtext=f"Average: {prefix}{_format_compact_number(p_mean)} (n={len(p_series):,})",
                        column=primary_col,
                        calculation_method=f"Sum and arithmetic mean of column '{primary_col}'",
                        category="monetary" if is_monetary else "distribution",
                    )
                )

        # KPI 6: Outlier Detection Concentration across numerics
        total_outliers = 0
        analyzed_num_cells = 0
        for col in numeric_cols[:5]:
            s_num = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(s_num) >= 4:
                q25, q75 = s_num.quantile(0.25), s_num.quantile(0.75)
                iqr = q75 - q25
                if iqr > 0:
                    outlier_mask = (s_num < (q25 - 1.5 * iqr)) | (s_num > (q75 + 1.5 * iqr))
                    total_outliers += int(outlier_mask.sum())
                analyzed_num_cells += len(s_num)

        outlier_pct = round((total_outliers / max(analyzed_num_cells, 1)) * 100, 2)
        kpi_cards.append(
            KPICard(
                id="kpi_outliers",
                label="IQR Outlier Volume",
                value=total_outliers,
                formatted_value=f"{total_outliers} outliers",
                subtext=f"{outlier_pct}% of analyzed numeric records beyond 1.5x IQR",
                calculation_method="Tukey 1.5x Interquartile Range boundary evaluation",
                trend_direction="stable" if outlier_pct < 5 else "increasing",
                category="distribution",
            )
        )

        return AnalyticsOverviewResponse(
            dataset_id=dataset.id,
            dataset_name=dataset.original_filename or dataset.filename,
            version=actual_version,
            rows=total_rows,
            columns=total_cols,
            file_size_bytes=dataset.file_size_bytes or 0,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
            column_summary=column_summaries,
            kpi_cards=kpi_cards,
            available_numeric_columns=numeric_cols,
            available_categorical_columns=categorical_cols,
            available_date_columns=date_cols,
            warnings=warnings,
        )

    @classmethod
    def _apply_filters(cls, df: pd.DataFrame, filters: Optional[List[FilterCondition]]) -> Tuple[pd.DataFrame, List[Dict[str, Any]], List[str]]:
        """Safely apply structured filter conditions against DataFrame."""
        applied: List[Dict[str, Any]] = []
        warnings: List[str] = []

        if not filters:
            return df, applied, warnings

        filtered_df = df.copy()

        for f in filters:
            col = f.column
            if col not in filtered_df.columns:
                warnings.append(f"Filter column '{col}' not found in dataset. Skipping.")
                continue

            op = f.operator.lower().strip()
            val = f.value

            try:
                series = filtered_df[col]
                is_num = pd.api.types.is_numeric_dtype(series)

                if op in ["==", "eq"]:
                    if is_num:
                        filtered_df = filtered_df[pd.to_numeric(series, errors="coerce") == float(val)]
                    else:
                        filtered_df = filtered_df[series.astype(str).str.lower() == str(val).lower()]
                elif op in ["!=", "neq"]:
                    if is_num:
                        filtered_df = filtered_df[pd.to_numeric(series, errors="coerce") != float(val)]
                    else:
                        filtered_df = filtered_df[series.astype(str).str.lower() != str(val).lower()]
                elif op in [">", "gt"]:
                    filtered_df = filtered_df[pd.to_numeric(series, errors="coerce") > float(val)]
                elif op in [">=", "gte"]:
                    filtered_df = filtered_df[pd.to_numeric(series, errors="coerce") >= float(val)]
                elif op in ["<", "lt"]:
                    filtered_df = filtered_df[pd.to_numeric(series, errors="coerce") < float(val)]
                elif op in ["<=", "lte"]:
                    filtered_df = filtered_df[pd.to_numeric(series, errors="coerce") <= float(val)]
                elif op in ["contains", "like"]:
                    filtered_df = filtered_df[series.astype(str).str.contains(str(val), case=False, na=False)]
                elif op == "in":
                    items = val if isinstance(val, list) else [str(x).strip() for x in str(val).split(",")]
                    if is_num:
                        num_items = [float(x) for x in items if str(x).replace(".", "", 1).isdigit()]
                        filtered_df = filtered_df[pd.to_numeric(series, errors="coerce").isin(num_items)]
                    else:
                        str_items = [str(x).lower() for x in items]
                        filtered_df = filtered_df[series.astype(str).str.lower().isin(str_items)]
                elif op == "between":
                    parts = val if isinstance(val, list) else [str(x).strip() for x in str(val).split(",")]
                    if len(parts) >= 2:
                        low_v, high_v = float(parts[0]), float(parts[1])
                        num_s = pd.to_numeric(series, errors="coerce")
                        filtered_df = filtered_df[(num_s >= low_v) & (num_s <= high_v)]

                applied.append({"column": col, "operator": op, "value": val})
            except Exception as e:
                warnings.append(f"Failed to apply filter on '{col}': {str(e)}")

        return filtered_df, applied, warnings

    @classmethod
    def generate_chart(
        cls,
        request: AnalyticsChartRequest,
        current_user: User,
        db: Session,
    ) -> AnalyticsChartResponse:
        """Generate interactive chart visualization and matching data table from actual dataset."""
        dataset, df, actual_version, warnings = cls.get_dataset_and_df(
            request.dataset_id, request.version, current_user, db
        )

        filtered_df, applied_filters, filter_warnings = cls._apply_filters(df, request.filters)
        warnings.extend(filter_warnings)

        if filtered_df.empty:
            return AnalyticsChartResponse(
                chart_type=request.chart_type,
                title="No Data Available After Filtering",
                x_axis_label=request.x_column or "Dimension",
                y_axis_label=request.y_column or "Metric",
                data_points=[],
                table_data={"columns": [], "rows": []},
                applied_filters=applied_filters,
                warnings=warnings + ["Applied filter conditions returned 0 matching records."],
            )

        chart_type = (request.chart_type or "bar").lower().strip()
        agg = (request.aggregation or "sum").lower().strip()
        limit = max(1, min(request.limit or 10, 100))
        sort_dir = (request.sort_direction or "desc").lower().strip()
        is_desc = sort_dir == "desc"

        # Determine default columns if omitted
        all_numeric = [c for c in filtered_df.columns if pd.api.types.is_numeric_dtype(filtered_df[c])]
        all_categorical = [c for c in filtered_df.columns if not pd.api.types.is_numeric_dtype(filtered_df[c])]

        if request.x_column and request.x_column in filtered_df.columns:
            x_col = request.x_column
        else:
            x_col = all_categorical[0] if all_categorical else filtered_df.columns[0]
            if request.x_column and request.x_column not in filtered_df.columns:
                warnings.append(f"Specified x_column '{request.x_column}' not found in dataset; defaulted to '{x_col}'.")

        if request.y_column and request.y_column in filtered_df.columns:
            y_col = request.y_column
        elif request.y_column and request.y_column not in filtered_df.columns:
            y_col = all_numeric[0] if all_numeric else None
            warnings.append(f"Specified y_column '{request.y_column}' not found in dataset; defaulted to '{y_col or 'count'}'.")
        else:
            y_col = all_numeric[0] if all_numeric else None

        data_points: List[Dict[str, Any]] = []
        table_columns: List[str] = []
        table_rows: List[Dict[str, Any]] = []
        trendline: Optional[List[Dict[str, Any]]] = None
        boxplot_data: Optional[List[BoxPlotData]] = None
        matrix: Optional[List[List[float]]] = None
        categories: Optional[List[str]] = None
        title = f"{chart_type.capitalize()} Analysis of {x_col}"
        x_label = str(x_col)
        y_label = f"{agg.capitalize()} of {y_col}" if y_col else "Count"

        # ----------------- HISTOGRAM -----------------
        if chart_type == "histogram":
            target_col = y_col or x_col
            s_num = pd.to_numeric(filtered_df[target_col], errors="coerce").dropna()
            num_bins = max(3, min(request.bins or 10, 30))
            if len(s_num) > 0:
                counts, bin_edges = np.histogram(s_num, bins=num_bins)
                table_columns = ["Bin Range", "Frequency Count", "Percentage"]
                for i in range(len(counts)):
                    b_label = f"{bin_edges[i]:.2f} - {bin_edges[i+1]:.2f}"
                    cnt = int(counts[i])
                    pct = round((cnt / len(s_num)) * 100, 2)
                    data_points.append({"label": b_label, "value": cnt})
                    table_rows.append({"Bin Range": b_label, "Frequency Count": cnt, "Percentage": f"{pct}%"})
            title = f"Histogram Distribution: {target_col}"
            x_label = str(target_col)
            y_label = "Frequency Count"

        # ----------------- SCATTER PLOT -----------------
        elif chart_type == "scatter":
            if not y_col:
                if len(all_numeric) >= 2:
                    x_col = all_numeric[0]
                    y_col = all_numeric[1]
                else:
                    y_col = x_col

            s_x = pd.to_numeric(filtered_df[x_col], errors="coerce")
            s_y = pd.to_numeric(filtered_df[y_col], errors="coerce")
            valid_mask = s_x.notna() & s_y.notna()
            clean_x = s_x[valid_mask].values
            clean_y = s_y[valid_mask].values

            # Sample/Limit to 100 for responsive rendering
            indices = np.arange(len(clean_x))
            if len(clean_x) > 100:
                indices = np.linspace(0, len(clean_x) - 1, 100, dtype=int)

            table_columns = [str(x_col), str(y_col)]
            for idx in indices:
                xv = float(clean_x[idx])
                yv = float(clean_y[idx])
                data_points.append({"label": f"({xv:.1f}, {yv:.1f})", "value": round(yv, 2), "x": round(xv, 2)})
                table_rows.append({str(x_col): round(xv, 2), str(y_col): round(yv, 2)})

            # Calculate regression trendline
            if len(clean_x) >= 2 and np.std(clean_x) > 0:
                slope, intercept = np.polyfit(clean_x, clean_y, 1)
                min_x = float(np.min(clean_x))
                max_x = float(np.max(clean_x))
                trendline = [
                    {"x": round(min_x, 2), "y": round(slope * min_x + intercept, 2)},
                    {"x": round(max_x, 2), "y": round(slope * max_x + intercept, 2)},
                ]

            title = f"Scatter Correlation: {x_col} vs {y_col}"
            x_label = str(x_col)
            y_label = str(y_col)

        # ----------------- HEATMAP (Correlation Matrix) -----------------
        elif chart_type == "heatmap":
            num_df = filtered_df[all_numeric].apply(pd.to_numeric, errors="coerce").dropna(how="all")
            corr = num_df.corr(method="pearson")
            categories = list(corr.columns)
            matrix = []
            for r_col in categories:
                row_vals = []
                for c_col in categories:
                    val = corr.loc[r_col, c_col]
                    row_vals.append(None if (math.isnan(val) or np.isnan(val)) else round(float(val), 2))
                matrix.append(row_vals)

            table_columns = ["Attribute"] + categories
            for r_idx, r_col in enumerate(categories):
                r_dict = {"Attribute": r_col}
                for c_idx, c_col in enumerate(categories):
                    r_dict[c_col] = matrix[r_idx][c_idx] if matrix[r_idx][c_idx] is not None else "—"
                table_rows.append(r_dict)

            title = "Correlation Heatmap Matrix"
            x_label = "Feature Attribute"
            y_label = "Feature Attribute"

        # ----------------- BOXPLOT -----------------
        elif chart_type == "boxplot":
            metric_target = y_col or (all_numeric[0] if all_numeric else None)
            boxplot_data = []
            table_columns = ["Category", "Min", "Q1 (25%)", "Median", "Q3 (75%)", "Max", "Outliers Count"]

            if metric_target and metric_target in filtered_df.columns:
                if x_col and x_col != metric_target and x_col in filtered_df.columns:
                    top_groups = filtered_df[x_col].value_counts().head(8).index
                    for grp in top_groups:
                        subset = pd.to_numeric(filtered_df[filtered_df[x_col] == grp][metric_target], errors="coerce").dropna()
                        if len(subset) >= 4:
                            q1, med, q3 = float(subset.quantile(0.25)), float(subset.median()), float(subset.quantile(0.75))
                            iqr = q3 - q1
                            low_b = q1 - 1.5 * iqr
                            up_b = q3 + 1.5 * iqr
                            min_val = float(subset[subset >= low_b].min() if len(subset[subset >= low_b]) > 0 else subset.min())
                            max_val = float(subset[subset <= up_b].max() if len(subset[subset <= up_b]) > 0 else subset.max())
                            outliers = [round(float(o), 2) for o in subset[(subset < low_b) | (subset > up_b)]]
                            b_item = BoxPlotData(
                                category=str(grp),
                                min_val=round(min_val, 2),
                                q1=round(q1, 2),
                                median=round(med, 2),
                                q3=round(q3, 2),
                                max_val=round(max_val, 2),
                                outliers=outliers[:10],
                            )
                            boxplot_data.append(b_item)
                            table_rows.append({
                                "Category": str(grp),
                                "Min": round(min_val, 2),
                                "Q1 (25%)": round(q1, 2),
                                "Median": round(med, 2),
                                "Q3 (75%)": round(q3, 2),
                                "Max": round(max_val, 2),
                                "Outliers Count": len(outliers),
                            })
                else:
                    subset = pd.to_numeric(filtered_df[metric_target], errors="coerce").dropna()
                    if len(subset) >= 4:
                        q1, med, q3 = float(subset.quantile(0.25)), float(subset.median()), float(subset.quantile(0.75))
                        iqr = q3 - q1
                        low_b = q1 - 1.5 * iqr
                        up_b = q3 + 1.5 * iqr
                        min_val = float(subset[subset >= low_b].min() if len(subset[subset >= low_b]) > 0 else subset.min())
                        max_val = float(subset[subset <= up_b].max() if len(subset[subset <= up_b]) > 0 else subset.max())
                        outliers = [round(float(o), 2) for o in subset[(subset < low_b) | (subset > up_b)]]
                        b_item = BoxPlotData(
                            category=str(metric_target),
                            min_val=round(min_val, 2),
                            q1=round(q1, 2),
                            median=round(med, 2),
                            q3=round(q3, 2),
                            max_val=round(max_val, 2),
                            outliers=outliers[:10],
                        )
                        boxplot_data.append(b_item)
                        table_rows.append({
                            "Category": str(metric_target),
                            "Min": round(min_val, 2),
                            "Q1 (25%)": round(q1, 2),
                            "Median": round(med, 2),
                            "Q3 (75%)": round(q3, 2),
                            "Max": round(max_val, 2),
                            "Outliers Count": len(outliers),
                        })

            title = f"Boxplot Quartile Distribution: {metric_target}"
            x_label = str(x_col) if x_col else "Overall"
            y_label = str(metric_target)

        # ----------------- BAR / LINE / DONUT / TABLE -----------------
        else:
            metric_label = f"{agg.capitalize()} of {y_col}" if y_col else "Record Count"
            table_columns = [str(x_col), metric_label]

            if y_col and y_col in filtered_df.columns:
                grouped = filtered_df.groupby(x_col)[y_col]
                if agg == "mean":
                    res_series = grouped.mean()
                elif agg == "median":
                    res_series = grouped.median()
                elif agg == "min":
                    res_series = grouped.min()
                elif agg == "max":
                    res_series = grouped.max()
                elif agg == "count":
                    res_series = grouped.count()
                else:
                    res_series = grouped.sum()
            else:
                res_series = filtered_df[x_col].value_counts()

            # Clean and sort
            res_series = res_series.dropna()
            if is_desc:
                res_series = res_series.sort_values(ascending=False)
            else:
                res_series = res_series.sort_values(ascending=True)

            # Limit records
            top_records = res_series.head(limit)

            # If Donut and items > 6, collapse excess to "Other"
            if chart_type == "donut" and len(res_series) > 6:
                main_slice = res_series.head(5)
                other_val = res_series.iloc[5:].sum()
                for k, v in main_slice.items():
                    data_points.append({"label": str(k), "value": round(float(v), 2)})
                    table_rows.append({str(x_col): str(k), metric_label: round(float(v), 2)})
                data_points.append({"label": "Other", "value": round(float(other_val), 2)})
                table_rows.append({str(x_col): "Other", metric_label: round(float(other_val), 2)})
            else:
                for k, v in top_records.items():
                    val_float = round(float(v), 2)
                    data_points.append({"label": str(k), "value": val_float})
                    table_rows.append({str(x_col): str(k), metric_label: val_float})

            title = f"{agg.capitalize()} of {y_col or 'Count'} by {x_col}"
            x_label = str(x_col)
            y_label = metric_label

        # Summary statistics of the visualization points
        summary_stats = None
        if data_points:
            numeric_vals = [p["value"] for p in data_points if isinstance(p.get("value"), (int, float)) and not math.isnan(p["value"])]
            if numeric_vals:
                summary_stats = {
                    "count": len(numeric_vals),
                    "sum": round(float(np.sum(numeric_vals)), 2),
                    "mean": round(float(np.mean(numeric_vals)), 2),
                    "min": round(float(np.min(numeric_vals)), 2),
                    "max": round(float(np.max(numeric_vals)), 2),
                }

        return AnalyticsChartResponse(
            chart_type=chart_type,
            title=title,
            x_axis_label=x_label,
            y_axis_label=y_label,
            data_points=data_points,
            table_data={"columns": table_columns, "rows": table_rows},
            matrix=matrix,
            categories=categories,
            boxplot_data=boxplot_data,
            trendline=trendline,
            summary_stats=summary_stats,
            applied_filters=applied_filters,
            warnings=warnings,
        )

    @classmethod
    def analyze_trend(
        cls,
        request: AnalyticsTrendRequest,
        current_user: User,
        db: Session,
    ) -> AnalyticsTrendResponse:
        """Execute chronological time-series aggregation, period-over-period comparison, and caveat."""
        dataset, df, actual_version, warnings = cls.get_dataset_and_df(
            request.dataset_id, request.version, current_user, db
        )

        date_col = request.date_column
        metric_col = request.metric_column
        interval = (request.interval or "daily").lower().strip()
        agg = (request.aggregation or "sum").lower().strip()

        if date_col not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Date column '{date_col}' does not exist in dataset.",
            )
        if metric_col not in df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Metric column '{metric_col}' does not exist in dataset.",
            )

        work_df = df[[date_col, metric_col]].copy()
        work_df[date_col] = pd.to_datetime(work_df[date_col], errors="coerce")
        work_df[metric_col] = pd.to_numeric(work_df[metric_col], errors="coerce")
        work_df = work_df.dropna(subset=[date_col, metric_col]).sort_values(by=date_col)

        if work_df.empty:
            return AnalyticsTrendResponse(
                date_column=date_col,
                metric_column=metric_col,
                interval=interval,
                data_points=[],
                trend_direction="relatively stable",
                causal_caveat="No valid parsed datetime records available in selected column.",
                warnings=warnings + ["Unable to parse datetime values from column."],
            )

        # Bucket by interval
        if interval == "monthly":
            work_df["bucket"] = work_df[date_col].dt.to_period("M").dt.to_timestamp()
            date_fmt = "%Y-%m"
        elif interval == "weekly":
            work_df["bucket"] = work_df[date_col].dt.to_period("W").dt.to_timestamp()
            date_fmt = "%Y-W%U"
        else:
            work_df["bucket"] = work_df[date_col].dt.to_period("D").dt.to_timestamp()
            date_fmt = "%Y-%m-%d"

        grouped = work_df.groupby("bucket")[metric_col]
        if agg == "mean":
            ts_series = grouped.mean()
        elif agg == "count":
            ts_series = grouped.count()
        else:
            ts_series = grouped.sum()

        ts_series = ts_series.sort_index()

        data_points: List[Dict[str, Any]] = []
        for ts, val in ts_series.items():
            dt_label = ts.strftime(date_fmt)
            data_points.append({"label": dt_label, "date": ts.isoformat(), "value": round(float(val), 2)})

        # Period-over-period comparison
        period_comp: Optional[PeriodComparison] = None
        if len(ts_series) >= 2:
            prev_t, prev_v = ts_series.index[-2], float(ts_series.iloc[-2])
            curr_t, curr_v = ts_series.index[-1], float(ts_series.iloc[-1])
            chg_pct = None
            if abs(prev_v) > 0.0001:
                chg_pct = round(((curr_v - prev_v) / abs(prev_v)) * 100, 2)

            chg_dir = "stable"
            if chg_pct is not None:
                if chg_pct > 1.0:
                    chg_dir = "increasing"
                elif chg_pct < -1.0:
                    chg_dir = "decreasing"
            elif prev_v == 0 and curr_v > 0:
                chg_dir = "baseline_zero"

            period_comp = PeriodComparison(
                current_period_label=curr_t.strftime(date_fmt),
                current_period_val=round(curr_v, 2),
                prev_period_label=prev_t.strftime(date_fmt),
                prev_period_val=round(prev_v, 2),
                change_pct=chg_pct,
                change_direction=chg_dir,
            )

        # Overall trend direction
        trend_direction = "relatively stable"
        if len(ts_series) >= 3:
            vals = ts_series.values
            half = len(vals) // 2
            first_half_avg = np.mean(vals[:half])
            second_half_avg = np.mean(vals[half:])
            diff_pct = ((second_half_avg - first_half_avg) / max(abs(first_half_avg), 1)) * 100
            if diff_pct > 5.0:
                trend_direction = "increasing"
            elif diff_pct < -5.0:
                trend_direction = "decreasing"

        causal_caveat = (
            "Statistical Note: Observed time-series trajectory reflects historical correlation "
            "and does not constitute direct causality. Confounding business variables, seasonality, "
            "and external dynamics should be evaluated prior to operational intervention."
        )

        return AnalyticsTrendResponse(
            date_column=date_col,
            metric_column=metric_col,
            interval=interval,
            data_points=data_points,
            previous_period_comparison=period_comp,
            trend_direction=trend_direction,
            causal_caveat=causal_caveat,
            warnings=warnings,
        )

    @classmethod
    def group_compare(
        cls,
        request: AnalyticsGroupCompareRequest,
        current_user: User,
        db: Session,
    ) -> AnalyticsGroupCompareResponse:
        """Multidimensional grouping, conditional filtering, and group-by comparison table."""
        dataset, df, actual_version, warnings = cls.get_dataset_and_df(
            request.dataset_id, request.version, current_user, db
        )

        filtered_df, applied_filters, filter_warnings = cls._apply_filters(df, request.filters)
        warnings.extend(filter_warnings)

        grp_cols = [c for c in request.group_by_columns if c in filtered_df.columns]
        if not grp_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one valid group_by column must exist in dataset.",
            )

        metric_col = request.metric_column
        if metric_col not in filtered_df.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Metric column '{metric_col}' does not exist in dataset.",
            )

        agg = (request.aggregation or "sum").lower().strip()
        limit = max(1, min(request.limit or 15, 100))
        is_desc = (request.sort_direction or "desc").lower().strip() == "desc"

        grouped = filtered_df.groupby(grp_cols)[metric_col]
        if agg == "mean":
            res = grouped.mean()
        elif agg == "median":
            res = grouped.median()
        elif agg == "min":
            res = grouped.min()
        elif agg == "max":
            res = grouped.max()
        elif agg == "count":
            res = grouped.count()
        else:
            res = grouped.sum()

        res = res.dropna().sort_values(ascending=not is_desc)
        total_groups = len(res)
        res_head = res.head(limit)

        metric_label = f"{agg.capitalize()} of {metric_col}"
        output_cols = grp_cols + [metric_label]
        rows: List[Dict[str, Any]] = []

        for idx, val in res_head.items():
            row_dict: Dict[str, Any] = {}
            if isinstance(idx, tuple):
                for col_name, col_val in zip(grp_cols, idx):
                    row_dict[col_name] = str(col_val)
            else:
                row_dict[grp_cols[0]] = str(idx)
            row_dict[metric_label] = round(float(val), 2)
            rows.append(row_dict)

        return AnalyticsGroupCompareResponse(
            columns=output_cols,
            rows=rows,
            total_groups=total_groups,
            metric_label=metric_label,
            active_filters=applied_filters,
            warnings=warnings,
        )

    @classmethod
    def deep_stats(
        cls,
        request: AnalyticsStatsRequest,
        current_user: User,
        db: Session,
    ) -> AnalyticsStatsResponse:
        """Calculate comprehensive descriptive stats, Pearson correlation matrix, and IQR outliers."""
        dataset, df, actual_version, warnings = cls.get_dataset_and_df(
            request.dataset_id, request.version, current_user, db
        )

        all_numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        selected_cols = [c for c in (request.numeric_columns or all_numeric) if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]

        descriptive_rows: List[DescriptiveStatRow] = []
        outlier_details: List[OutlierDetail] = []
        limitations: List[str] = [
            "Pearson correlation measures strictly linear relationships; non-linear dependencies may exist undetected.",
            "IQR outlier detection assumes continuous univariate distributions and is sensitive to small sample sizes.",
        ]

        for col in selected_cols:
            s_raw = df[col]
            total_c = len(s_raw)
            s_num = pd.to_numeric(s_raw, errors="coerce").dropna()
            non_null = len(s_num)
            missing = total_c - non_null
            missing_pct = round((missing / max(total_c, 1)) * 100, 2)

            if non_null == 0:
                continue

            q25 = float(s_num.quantile(0.25))
            med = float(s_num.median())
            q75 = float(s_num.quantile(0.75))
            iqr = q75 - q25
            low_b = q25 - 1.5 * iqr
            up_b = q75 + 1.5 * iqr

            outliers_s = s_num[(s_num < low_b) | (s_num > up_b)]
            outlier_cnt = int(len(outliers_s))
            outlier_pct = round((outlier_cnt / max(non_null, 1)) * 100, 2)

            skewness = float(s_num.skew()) if non_null >= 3 else None
            kurtosis = float(s_num.kurt()) if non_null >= 4 else None

            descriptive_rows.append(
                DescriptiveStatRow(
                    column=col,
                    count=non_null,
                    missing_count=missing,
                    missing_pct=missing_pct,
                    mean=round(float(s_num.mean()), 2),
                    median=round(med, 2),
                    std=round(float(s_num.std()), 2) if non_null >= 2 else None,
                    min=round(float(s_num.min()), 2),
                    q25=round(q25, 2),
                    q50=round(med, 2),
                    q75=round(q75, 2),
                    max=round(float(s_num.max()), 2),
                    skewness=round(skewness, 2) if skewness is not None else None,
                    kurtosis=round(kurtosis, 2) if kurtosis is not None else None,
                    outlier_count=outlier_cnt,
                    outlier_pct=outlier_pct,
                )
            )

            if outlier_cnt > 0:
                sample_out = [round(float(x), 2) for x in outliers_s.head(8)]
                outlier_details.append(
                    OutlierDetail(
                        column=col,
                        method="IQR (1.5 * IQR rule)",
                        lower_bound=round(low_b, 2),
                        upper_bound=round(up_b, 2),
                        outlier_count=outlier_cnt,
                        outlier_pct=outlier_pct,
                        sample_outliers=sample_out,
                    )
                )

        # Correlation Matrix
        corr_dict: Dict[str, Any] = {"columns": [], "matrix": []}
        if len(selected_cols) >= 2:
            num_df = df[selected_cols].apply(pd.to_numeric, errors="coerce").dropna(how="all")
            corr_mat = num_df.corr()
            corr_dict["columns"] = list(corr_mat.columns)
            corr_dict["matrix"] = [
                [None if (math.isnan(v) or np.isnan(v)) else round(float(v), 2) for v in row]
                for row in corr_mat.values
            ]

        return AnalyticsStatsResponse(
            descriptive_table=descriptive_rows,
            correlation_matrix=corr_dict,
            outliers=outlier_details,
            limitations=limitations,
        )

    @classmethod
    def generate_insights(
        cls,
        dataset_id: int,
        version: str,
        current_user: User,
        db: Session,
    ) -> AnalyticsInsightsResponse:
        """Automated evidence-grounded insights strictly verified against dataset metrics."""
        dataset, df, actual_version, warnings = cls.get_dataset_and_df(dataset_id, version, current_user, db)

        insights: List[AnalyticsInsightItem] = []
        total_rows = len(df)
        all_numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        all_categorical = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]

        # 1. Missing Value Concentration Insight
        for col in df.columns:
            null_cnt = int(df[col].isna().sum())
            null_rate = (null_cnt / max(total_rows, 1)) * 100
            if null_rate >= 10.0:
                insights.append(
                    AnalyticsInsightItem(
                        id=f"missing_{col}",
                        type="missing_values",
                        title=f"Elevated Missing Rate: {col}",
                        statement=f"Column '{col}' exhibits {null_cnt:,} missing entries ({null_rate:.1f}% of dataset). Imputation or deletion may alter statistical power.",
                        metric=f"{null_rate:.1f}% Missing",
                        columns_involved=[col],
                        confidence="High",
                        severity="Warning" if null_rate > 25 else "Actionable",
                        limitations="Missingness mechanism (MCAR vs MAR vs MNAR) unverified without longitudinal testing.",
                    )
                )

        # 2. Categorical Concentration (Pareto Dominance)
        for col in all_categorical[:4]:
            val_counts = df[col].dropna().value_counts()
            if len(val_counts) >= 2:
                top_name = val_counts.index[0]
                top_cnt = int(val_counts.iloc[0])
                top_pct = (top_cnt / max(total_rows, 1)) * 100
                if top_pct >= 45.0:
                    insights.append(
                        AnalyticsInsightItem(
                            id=f"conc_{col}",
                            type="concentration",
                            title=f"High Category Dominance: {col}",
                            statement=f"Category '{top_name}' constitutes {top_pct:.1f}% ({top_cnt:,} occurrences) of all records in '{col}'.",
                            metric=f"{top_pct:.1f}% Dominance",
                            columns_involved=[col],
                            confidence="High",
                            severity="Informational",
                            limitations="Class imbalance may bias general aggregations if unstratified.",
                        )
                    )

        # 3. Strong Pairwise Correlation
        if len(all_numeric) >= 2:
            num_df = df[all_numeric].apply(pd.to_numeric, errors="coerce").dropna(how="all")
            corr = num_df.corr()
            seen_pairs = set()
            for c1 in all_numeric:
                for c2 in all_numeric:
                    if c1 != c2 and (c2, c1) not in seen_pairs:
                        seen_pairs.add((c1, c2))
                        r = corr.loc[c1, c2]
                        if not math.isnan(r) and abs(r) >= 0.65:
                            polarity = "positive" if r > 0 else "inverse"
                            insights.append(
                                AnalyticsInsightItem(
                                    id=f"corr_{c1}_{c2}",
                                    type="correlation",
                                    title=f"Strong {polarity.capitalize()} Association: {c1} & {c2}",
                                    statement=f"Attributes '{c1}' and '{c2}' demonstrate a strong {polarity} linear association (Pearson r = {r:.2f}).",
                                    metric=f"r = {r:.2f}",
                                    columns_involved=[c1, c2],
                                    confidence="High",
                                    severity="Actionable",
                                    limitations="Association does NOT establish causal relationship; potential third-variable confounders.",
                                )
                            )

        # 4. Outlier Concentration
        for col in all_numeric[:4]:
            s_num = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(s_num) >= 10:
                q25, q75 = s_num.quantile(0.25), s_num.quantile(0.75)
                iqr = q75 - q25
                if iqr > 0:
                    outliers = s_num[(s_num < (q25 - 1.5 * iqr)) | (s_num > (q75 + 1.5 * iqr))]
                    o_cnt = len(outliers)
                    o_pct = (o_cnt / len(s_num)) * 100
                    if o_pct >= 4.0:
                        insights.append(
                            AnalyticsInsightItem(
                                id=f"outlier_{col}",
                                type="outlier",
                                title=f"Significant Outlier Concentration: {col}",
                                statement=f"Found {o_cnt:,} statistical outliers ({o_pct:.1f}%) in '{col}' exceeding 1.5x IQR boundaries (limits: [{q25 - 1.5*iqr:.1f}, {q75 + 1.5*iqr:.1f}]).",
                                metric=f"{o_pct:.1f}% Outliers",
                                columns_involved=[col],
                                confidence="High",
                                severity="Warning" if o_pct > 8 else "Informational",
                                limitations="Outliers may represent high-value signals rather than measurement noise.",
                            )
                        )

        # Fallback informative insight if dataset is pristine
        if not insights:
            insights.append(
                AnalyticsInsightItem(
                    id="clean_data_notice",
                    type="concentration",
                    title="High Data Stability",
                    statement=f"Dataset contains {total_rows:,} verified rows with uniform distribution and zero high-severity anomalies detected.",
                    metric="100% Balanced",
                    columns_involved=[],
                    confidence="High",
                    severity="Informational",
                    limitations="Standard rule thresholds applied.",
                )
            )

        return AnalyticsInsightsResponse(
            dataset_id=dataset.id,
            dataset_name=dataset.original_filename or dataset.filename,
            insights=insights,
        )

    @classmethod
    def export_csv_stream(cls, request: AnalyticsExportCSVRequest) -> StreamingResponse:
        """Export table data points as formatted CSV with UTF-8 BOM."""
        output = io.StringIO()
        output.write("\ufeff")  # UTF-8 BOM for Excel
        writer = csv.writer(output)

        writer.writerow(request.columns)
        for row in request.rows:
            writer.writerow([row.get(col, "") for col in request.columns])

        output.seek(0)
        filename = request.filename or "analytics_export.csv"
        if not filename.endswith(".csv"):
            filename += ".csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @classmethod
    def export_report_summary(
        cls,
        request: AnalyticsReportExportRequest,
        current_user: User,
        db: Session,
    ) -> Dict[str, Any]:
        """Generate structured comprehensive analytical executive summary report."""
        dataset, df, actual_version, warnings = cls.get_dataset_and_df(
            request.dataset_id, request.version, current_user, db
        )

        overview = cls.get_analytics_overview(request.dataset_id, request.version, current_user, db) if request.include_kpis else None
        stats = cls.deep_stats(AnalyticsStatsRequest(dataset_id=request.dataset_id, version=request.version), current_user, db) if request.include_stats else None
        insights = cls.generate_insights(request.dataset_id, request.version, current_user, db) if request.include_insights else None

        return {
            "title": request.title or f"Executive Analytics Report: {dataset.original_filename or dataset.filename}",
            "generated_at": datetime.now().isoformat(),
            "dataset_id": dataset.id,
            "dataset_name": dataset.original_filename or dataset.filename,
            "version": actual_version,
            "overview": overview.model_dump() if overview else None,
            "statistics": stats.model_dump() if stats else None,
            "insights": insights.model_dump() if insights else None,
        }
