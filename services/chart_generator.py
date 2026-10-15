"""Chart Generator Service - Unified dark SaaS Plotly chart construction for analytical insights."""

from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


class ChartGeneratorService:
    """Constructs high-aesthetic dark theme Plotly charts for analytical insights."""

    # Professional Light AI Analytics theme palette
    COLORS = ["#2563EB", "#16A34A", "#D97706", "#DC2626", "#1D4ED8", "#64748B"]
    BG_CARD = "#FFFFFF"
    BORDER_COLOR = "#E2E8F0"
    TEXT_MAIN = "#0F172A"
    TEXT_MUTED = "#64748B"

    @classmethod
    def apply_dark_theme(cls, fig: go.Figure, title: str = "") -> go.Figure:
        """Apply uniform SaaS enterprise light styling to any Plotly figure."""
        fig.update_layout(
            title={
                "text": title,
                "font": {"color": cls.TEXT_MAIN, "size": 14, "family": "Inter, sans-serif"},
                "x": 0.02,
                "y": 0.95,
            },
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            margin=dict(l=40, r=30, t=50, b=40),
            font={"color": cls.TEXT_MUTED, "family": "Inter, sans-serif", "size": 11},
            xaxis=dict(
                gridcolor=cls.BORDER_COLOR,
                zerolinecolor=cls.BORDER_COLOR,
                tickfont=dict(color=cls.TEXT_MUTED),
                title_font=dict(color=cls.TEXT_MAIN),
            ),
            yaxis=dict(
                gridcolor=cls.BORDER_COLOR,
                zerolinecolor=cls.BORDER_COLOR,
                tickfont=dict(color=cls.TEXT_MUTED),
                title_font=dict(color=cls.TEXT_MAIN),
            ),
            legend=dict(
                bgcolor="rgba(255, 255, 255, 0.92)",
                bordercolor=cls.BORDER_COLOR,
                font=dict(color=cls.TEXT_MAIN),
            ),
            hoverlabel=dict(
                bgcolor=cls.BG_CARD,
                font_size=12,
                font_family="Inter, sans-serif",
                bordercolor=cls.COLORS[0],
                font=dict(color=cls.TEXT_MAIN),
            ),
        )
        return fig

    @classmethod
    def create_bar_chart(
        cls,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: str,
        orientation: str = "v",
        color_col: Optional[str] = None,
    ) -> go.Figure:
        """Create a styled bar chart."""
        if orientation == "h":
            fig = px.bar(
                df,
                x=y_col,
                y=x_col,
                orientation="h",
                color=color_col or x_col,
                color_discrete_sequence=cls.COLORS,
            )
        else:
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                color=color_col or x_col,
                color_discrete_sequence=cls.COLORS,
            )
        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_line_chart(
        cls,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        title: str,
    ) -> go.Figure:
        """Create a styled line chart for trends and time series."""
        fig = px.line(
            df,
            x=x_col,
            y=y_col,
            markers=True,
            color_discrete_sequence=[cls.COLORS[0]],
        )
        fig.update_traces(line=dict(width=2.5), marker=dict(size=6, color=cls.COLORS[1]))
        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_histogram(
        cls,
        df: pd.DataFrame,
        col: str,
        title: str,
        nbins: int = 20,
    ) -> go.Figure:
        """Create a styled distribution histogram."""
        fig = px.histogram(
            df,
            x=col,
            nbins=nbins,
            color_discrete_sequence=[cls.COLORS[0]],
        )
        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_pie_chart(
        cls,
        df: pd.DataFrame,
        names_col: str,
        values_col: str,
        title: str,
    ) -> go.Figure:
        """Create a styled donut/pie chart."""
        fig = px.pie(
            df,
            names=names_col,
            values=values_col,
            hole=0.45,
            color_discrete_sequence=cls.COLORS,
        )
        return cls.apply_dark_theme(fig, title)

    # =========================================================================
    # PHASE 4 ANOMALY DETECTION CHARTS
    # =========================================================================

    @classmethod
    def create_box_plot(
        cls,
        df: pd.DataFrame,
        y_col: str,
        title: str,
        x_col: Optional[str] = None,
    ) -> go.Figure:
        """Create a styled Box Plot highlighting median, quartiles, and statistical outliers."""
        fig = px.box(
            df,
            x=x_col,
            y=y_col,
            points="outliers",
            color_discrete_sequence=[cls.COLORS[0]],
        )
        fig.update_traces(
            marker=dict(size=5, color="#DC2626", symbol="circle-open"),
            line=dict(color=cls.COLORS[0], width=2),
            fillcolor="#EFF6FF",
        )
        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_distribution_with_bounds(
        cls,
        df: pd.DataFrame,
        col: str,
        lower_bound: float,
        upper_bound: float,
        title: str,
        nbins: int = 25,
    ) -> go.Figure:
        """Create a distribution histogram with IQR lower and upper boundary cutoff markers."""
        fig = px.histogram(
            df,
            x=col,
            nbins=nbins,
            color_discrete_sequence=[cls.COLORS[0]],
        )
        # Add boundary markers
        fig.add_vline(
            x=lower_bound,
            line_width=2,
            line_dash="dash",
            line_color="#DC2626",
            annotation_text=f"Lower: {lower_bound:,.2f}",
            annotation_position="top left",
            annotation_font_color="#DC2626",
            annotation_font_size=10,
        )
        fig.add_vline(
            x=upper_bound,
            line_width=2,
            line_dash="dash",
            line_color="#DC2626",
            annotation_text=f"Upper: {upper_bound:,.2f}",
            annotation_position="top right",
            annotation_font_color="#DC2626",
            annotation_font_size=10,
        )
        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_anomaly_scatter(
        cls,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        status_col: str,
        title: str,
        hover_data: Optional[List[str]] = None,
    ) -> go.Figure:
        """Create a bivariate scatter plot clearly distinguishing Normal observations from Anomalies."""
        color_map = {"Normal": "#2563EB", "Anomaly": "#DC2626"}
        symbol_map = {"Normal": "circle", "Anomaly": "diamond"}
        size_map = {"Normal": 7, "Anomaly": 11}

        # Ensure status_col exists
        plot_df = df.copy()
        if status_col not in plot_df.columns:
            plot_df[status_col] = "Normal"

        fig = px.scatter(
            plot_df,
            x=x_col,
            y=y_col,
            color=status_col,
            color_discrete_map=color_map,
            symbol=status_col,
            symbol_map=symbol_map,
            hover_data=hover_data,
        )
        fig.update_traces(marker=dict(opacity=0.85, line=dict(width=1, color="#0F172A")))
        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_anomaly_score_histogram(
        cls,
        scores: List[float],
        threshold: float,
        title: str,
        nbins: int = 25,
    ) -> go.Figure:
        """Create an anomaly score distribution histogram with calibrated threshold."""
        score_df = pd.DataFrame({"Anomaly Score": scores})
        fig = px.histogram(
            score_df,
            x="Anomaly Score",
            nbins=nbins,
            color_discrete_sequence=[cls.COLORS[0]],
        )
        fig.add_vline(
            x=threshold,
            line_width=2,
            line_dash="dash",
            line_color="#DC2626",
            annotation_text=f"Anomaly Threshold: {threshold:.3f}",
            annotation_position="top right",
            annotation_font_color="#DC2626",
            annotation_font_size=10,
        )
        return cls.apply_dark_theme(fig, title)

    # =========================================================================
    # PHASE 5 INTELLIGENT ANALYSIS CHARTS
    # =========================================================================

    @classmethod
    def create_correlation_heatmap(
        cls,
        corr_matrix: Union[pd.DataFrame, Dict[str, Dict[str, float]]],
        title: str = "Feature Correlation Matrix",
    ) -> go.Figure:
        """Create a styled correlation heatmap with numerical annotations."""
        if isinstance(corr_matrix, dict):
            df_corr = pd.DataFrame(corr_matrix)
        else:
            df_corr = corr_matrix

        z_vals = df_corr.values
        x_labels = list(df_corr.columns)
        y_labels = list(df_corr.index)

        fig = go.Figure(
            data=go.Heatmap(
                z=z_vals,
                x=x_labels,
                y=y_labels,
                colorscale="Blues",
                zmin=-1.0,
                zmax=1.0,
                text=np.around(z_vals, decimals=2),
                texttemplate="%{text}",
                textfont={"size": 11, "family": "Inter, sans-serif"},
                hoverongaps=False,
                colorbar=dict(
                    title=dict(text="r", font=dict(color=cls.TEXT_MAIN)),
                    tickfont=dict(color=cls.TEXT_MUTED),
                ),
            )
        )
        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_trend_line_chart(
        cls,
        df: pd.DataFrame,
        date_col: str,
        value_col: str,
        title: str,
        peak_date: Optional[str] = None,
        trough_date: Optional[str] = None,
    ) -> go.Figure:
        """Create a time-series trend line chart with optional peak and trough markers."""
        fig = px.line(
            df,
            x=date_col,
            y=value_col,
            markers=True,
            color_discrete_sequence=[cls.COLORS[0]],
        )
        fig.update_traces(
            line=dict(width=2.5, color="#2563EB"),
            marker=dict(size=5, color="#1D4ED8"),
        )

        # Highlight Peak if provided
        if peak_date:
            peak_rows = df[df[date_col].astype(str).str.startswith(str(peak_date))]
            if not peak_rows.empty:
                p_val = float(peak_rows[value_col].iloc[0])
                fig.add_annotation(
                    x=peak_rows[date_col].iloc[0],
                    y=p_val,
                    text=f"Peak: {p_val:,.1f}",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="#16A34A",
                    font=dict(color="#16A34A", size=10, family="Inter, sans-serif"),
                    bgcolor="#EFF6FF",
                    bordercolor="#16A34A",
                )

        # Highlight Trough if provided
        if trough_date:
            trough_rows = df[df[date_col].astype(str).str.startswith(str(trough_date))]
            if not trough_rows.empty:
                t_val = float(trough_rows[value_col].iloc[0])
                fig.add_annotation(
                    x=trough_rows[date_col].iloc[0],
                    y=t_val,
                    text=f"Trough: {t_val:,.1f}",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="#DC2626",
                    font=dict(color="#DC2626", size=10, family="Inter, sans-serif"),
                    bgcolor="#EFF6FF",
                    bordercolor="#DC2626",
                )

        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_top_bottom_bar_chart(
        cls,
        items: List[Dict[str, Any]],
        title: str,
        value_key: str = "value",
        label_key: str = "category",
        orientation: str = "h",
    ) -> go.Figure:
        """Create a ranked bar chart from structured top/bottom category records."""
        df_plot = pd.DataFrame(items)
        if df_plot.empty:
            return cls.apply_dark_theme(go.Figure(), title)

        if orientation == "h":
            # Invert for horizontal bar chart so highest is on top
            df_plot = df_plot.iloc[::-1]
            fig = px.bar(
                df_plot,
                x=value_key,
                y=label_key,
                orientation="h",
                color_discrete_sequence=[cls.COLORS[0]],
                text=value_key,
            )
            fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
        else:
            fig = px.bar(
                df_plot,
                x=label_key,
                y=value_key,
                color_discrete_sequence=[cls.COLORS[0]],
                text=value_key,
            )
            fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")

        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_category_distribution_bar(
        cls,
        items: List[Any],
        title: str,
    ) -> go.Figure:
        """Create a distribution bar chart showing category shares with percentage labels."""
        rows = []
        for it in items:
            cat = getattr(it, "category", None) or it.get("category", "")
            pct = getattr(it, "percentage", None) or it.get("percentage", 0.0)
            cnt = getattr(it, "count", None) or it.get("count", 0)
            rows.append({"Category": cat, "Share (%)": pct, "Count": cnt})

        df_plot = pd.DataFrame(rows)
        if df_plot.empty:
            return cls.apply_dark_theme(go.Figure(), title)

        fig = px.bar(
            df_plot,
            x="Category",
            y="Share (%)",
            color_discrete_sequence=[cls.COLORS[0]],
            text="Share (%)",
            hover_data=["Count"],
        )
    @classmethod
    def analysis_visualizations(
        cls,
        structured_analysis: Union[Dict[str, Any], Any],
        df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """MODULE 8 CONTRACT: Map structured analysis results to chart-compatible configurations.

        Input:
            structured_analysis: Structured analysis result dict or DatasetAnalysisResult.
            df: Optional DataFrame for high-resolution distribution or time series curves.

        Output:
            Structured chart configurations generated using existing Plotly engine.
        """
        if not structured_analysis:
            return {
                "status": "unavailable",
                "reason": "No structured analysis data provided",
                "charts": {},
                "chart_types": [],
            }

        charts: Dict[str, Any] = {}

        # 1. Trend Visualization (Line Chart)
        trends_info = structured_analysis.get("trends", {}) if isinstance(structured_analysis, dict) else getattr(structured_analysis, "trends", None)
        if trends_info:
            date_col = None
            metric_col = None
            peak_date = None
            trough_date = None

            if isinstance(trends_info, dict):
                date_col = trends_info.get("date_column")
                tr_list = trends_info.get("trends", [])
                if tr_list:
                    metric_col = tr_list[0].get("column")
                peaks = trends_info.get("peaks", [])
                if peaks:
                    peak_date = peaks[0].get("date")
                drops = trends_info.get("drops", [])
                if drops:
                    trough_date = drops[0].get("date")
            elif isinstance(trends_info, list) and len(trends_info) > 0:
                first_tr = trends_info[0]
                date_col = getattr(first_tr, "date_column", None)
                metric_col = getattr(first_tr, "metric_column", None)
                peak_date = getattr(first_tr, "peak_date", None)
                trough_date = getattr(first_tr, "trough_date", None)

            if df is not None and date_col and metric_col and date_col in df.columns and metric_col in df.columns:
                charts["trend"] = cls.create_trend_line_chart(
                    df=df,
                    date_col=date_col,
                    value_col=metric_col,
                    title=f"Trajectory & Trend Analysis: {metric_col}",
                    peak_date=peak_date,
                    trough_date=trough_date,
                )
            elif isinstance(trends_info, dict) and trends_info.get("trends"):
                tr = trends_info["trends"][0]
                sample_data = pd.DataFrame([
                    {"Date": str(tr.get("start_date", "Start")), "Value": tr.get("start_value", 0)},
                    {"Date": str(tr.get("end_date", "End")), "Value": tr.get("end_value", 0)},
                ])
                charts["trend"] = cls.create_line_chart(
                    df=sample_data,
                    x_col="Date",
                    y_col="Value",
                    title=f"Trend Trajectory: {tr.get('column', 'Metric')}",
                )

        # 2. Correlation Visualization (Heatmap)
        corrs_info = structured_analysis.get("correlations", {}) if isinstance(structured_analysis, dict) else getattr(structured_analysis, "correlations", None)
        matrix = None
        if isinstance(corrs_info, dict):
            matrix = corrs_info.get("matrix") or corrs_info.get("correlation_matrix")
        elif hasattr(corrs_info, "correlation_matrix"):
            matrix = corrs_info.correlation_matrix

        if matrix and len(matrix) >= 2:
            charts["correlation"] = cls.create_correlation_heatmap(
                corr_matrix=matrix,
                title="Cross-Feature Statistical Correlation Matrix",
            )

        # 3. Category Visualization (Bar Chart)
        cats_info = structured_analysis.get("categories", {}) if isinstance(structured_analysis, dict) else getattr(structured_analysis, "categories", None)
        if isinstance(cats_info, dict):
            top_cats = cats_info.get("top_categories", [])
            dists = cats_info.get("distributions", [])
            if top_cats and top_cats[0].get("items"):
                first_tb = top_cats[0]
                charts["category"] = cls.create_top_bottom_bar_chart(
                    items=first_tb.get("items", []),
                    title=f"Top Segments by {first_tb.get('metric_column', 'Value')}",
                    value_key="value",
                    label_key="category",
                )
            elif dists and dists[0].get("categories"):
                charts["category"] = cls.create_category_distribution_bar(
                    items=dists[0].get("categories", []),
                    title=f"Distribution Shares: {dists[0].get('column', 'Category')}",
                )
        elif isinstance(cats_info, list) and len(cats_info) > 0:
            first_cat = cats_info[0]
            if hasattr(first_cat, "top_items") and first_cat.top_items:
                charts["category"] = cls.create_top_bottom_bar_chart(
                    items=first_cat.top_items,
                    title=f"Top Segments by {first_cat.metric_column}",
                    value_key="value",
                    label_key="category",
                )

        # 4. Distribution Visualization (Histogram / Box Plot)
        stats_info = structured_analysis.get("statistics", {}) if isinstance(structured_analysis, dict) else getattr(structured_analysis, "distributions", None)
        if df is not None:
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if num_cols:
                target_col = num_cols[0]
                charts["distribution"] = cls.create_histogram(
                    df=df,
                    col=target_col,
                    title=f"Parametric Distribution: {target_col}",
                )
        elif isinstance(stats_info, dict):
            col_stats = stats_info.get("column_statistics", {})
            if col_stats:
                first_col = next(iter(col_stats.keys()))
                s = col_stats[first_col]
                df_dist_summary = pd.DataFrame([
                    {"Metric": "Min", "Value": s.get("min", 0)},
                    {"Metric": "Q1", "Value": s.get("q1", 0)},
                    {"Metric": "Median", "Value": s.get("median", 0)},
                    {"Metric": "Mean", "Value": s.get("mean", 0)},
                    {"Metric": "Q3", "Value": s.get("q3", 0)},
                    {"Metric": "Max", "Value": s.get("max", 0)},
                ])
                charts["distribution"] = cls.create_bar_chart(
                    df=df_dist_summary,
                    x_col="Metric",
                    y_col="Value",
                    title=f"Distribution Moments: {first_col}",
                )

        # 5. Anomaly Visualization (Box Plot / Highlight)
        anom_info = structured_analysis.get("anomalies", {}) if isinstance(structured_analysis, dict) else None
        if df is not None and anom_info:
            affected_cols = anom_info.get("affected_columns", [])
            if affected_cols and affected_cols[0] in df.columns:
                charts["anomaly"] = cls.create_box_plot(
                    df=df,
                    y_col=affected_cols[0],
                    title=f"Outlier & Anomaly Spread: {affected_cols[0]}",
                )
        elif df is not None and hasattr(structured_analysis, "numeric_columns") and structured_analysis.numeric_columns:
            charts["anomaly"] = cls.create_box_plot(
                df=df,
                y_col=structured_analysis.numeric_columns[0],
                title=f"Outlier & Anomaly Spread: {structured_analysis.numeric_columns[0]}",
            )

        return {
            "status": "success",
            "charts": charts,
            "chart_types": list(charts.keys()),
        }

    @classmethod
    def create_anomaly_time_series(
        cls,
        df: pd.DataFrame,
        date_col: str,
        value_col: str,
        anomaly_indices: List[Any],
        title: str = "Time Series with Anomalies",
    ) -> go.Figure:
        """Create a time series line chart with anomalies overlaid as prominent red markers."""
        clean_df = df.dropna(subset=[date_col, value_col]).sort_values(by=date_col)
        fig = go.Figure()

        # Regular timeline trace
        fig.add_trace(
            go.Scatter(
                x=clean_df[date_col],
                y=clean_df[value_col],
                mode="lines",
                name="Normal Sequence",
                line=dict(color=cls.COLORS[0], width=2),
            )
        )

        # Anomalies trace
        anom_mask = clean_df.index.isin(anomaly_indices)
        anom_pts = clean_df[anom_mask]
        if not anom_pts.empty:
            fig.add_trace(
                go.Scatter(
                    x=anom_pts[date_col],
                    y=anom_pts[value_col],
                    mode="markers",
                    name="Anomaly",
                    marker=dict(
                        color="#DC2626",
                        size=10,
                        symbol="diamond",
                        line=dict(width=1.5, color="#7F1D1D"),
                    ),
                )
            )

        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_method_agreement_bar(
        cls,
        agreement_counts: Dict[str, int],
        title: str = "Method Agreement Distribution",
    ) -> go.Figure:
        """Create a styled bar chart showing multi-algorithm agreement counts."""
        labels = list(agreement_counts.keys())
        counts = list(agreement_counts.values())
        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=counts,
                    marker=dict(
                        color=["#93C5FD", "#60A5FA", "#2563EB", "#1D4ED8"][:len(labels)],
                        line=dict(color="#1E40AF", width=1),
                    ),
                    text=counts,
                    textposition="auto",
                )
            ]
        )
        fig.update_layout(xaxis_title="Methods in Agreement", yaxis_title="Records Flagged")
        return cls.apply_dark_theme(fig, title)

    @classmethod
    def create_column_anomaly_counts_bar(
        cls,
        col_counts: Dict[str, int],
        title: str = "Outliers by Numerical Column",
    ) -> go.Figure:
        """Create a horizontal bar chart depicting outlier frequency per column."""
        cols = list(col_counts.keys())
        counts = list(col_counts.values())
        fig = go.Figure(
            data=[
                go.Bar(
                    y=cols,
                    x=counts,
                    orientation="h",
                    marker=dict(color=cls.COLORS[0]),
                    text=counts,
                    textposition="auto",
                )
            ]
        )
        fig.update_layout(xaxis_title="Outlier Count", yaxis_title="Column")
        return cls.apply_dark_theme(fig, title)



def analysis_visualizations(
    structured_analysis: Union[Dict[str, Any], Any],
    df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """MODULE 8 CONTRACT: Standalone wrapper for visualization integration."""
    return ChartGeneratorService.analysis_visualizations(structured_analysis, df=df)


