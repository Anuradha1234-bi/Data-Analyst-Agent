"""Prediction & Forecasting Visualizations Module.

Constructs interactive Plotly charts adhering to the application's professional
light SaaS aesthetic (Primary Blue: #2563EB, Dark Blue: #1D4ED8, Border: #E2E8F0).
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from models.prediction import PredictionResult, PredictionPoint, ModelCandidateResult, FeatureImportanceItem


class PredictionVisualizer:
    """Generates publication-quality charts for forecasting, regression, and model validation."""

    THEME = {
        "primary": "#2563EB",
        "primary_dark": "#1D4ED8",
        "primary_light": "#EFF6FF",
        "history_color": "#0F172A",
        "forecast_color": "#2563EB",
        "ribbon_color": "rgba(37, 99, 235, 0.18)",
        "grid_color": "#F1F5F9",
        "font_family": "Inter, -apple-system, sans-serif",
    }

    @classmethod
    def create_forecast_chart(
        cls,
        history_dates: List[str],
        history_values: List[float],
        predictions: List[PredictionPoint],
        target_name: str,
    ) -> go.Figure:
        """Create time-series line chart depicting historical observations and projected future values."""
        fig = go.Figure()

        # 1. Historical Sequence
        fig.add_trace(
            go.Scatter(
                x=history_dates,
                y=history_values,
                mode="lines+markers",
                name="Historical Actual",
                line=dict(color=cls.THEME["history_color"], width=2.5),
                marker=dict(size=4),
            )
        )

        # Extract future projection points
        fut_dates = [p.index_or_date for p in predictions]
        fut_vals = [float(p.predicted_value) for p in predictions]
        lowers = [p.lower_bound for p in predictions if p.lower_bound is not None]
        uppers = [p.upper_bound for p in predictions if p.upper_bound is not None]

        # 2. Uncertainty Ribbon (Upper and Lower Bounds)
        if len(lowers) == len(predictions) and len(uppers) == len(predictions):
            fig.add_trace(
                go.Scatter(
                    x=fut_dates + fut_dates[::-1],
                    y=uppers + lowers[::-1],
                    fill="toself",
                    fillcolor=cls.THEME["ribbon_color"],
                    line=dict(color="rgba(255,255,255,0)"),
                    hoverinfo="skip",
                    showlegend=True,
                    name="Prediction Interval (95%)",
                )
            )

        # 3. Forecast Projections
        # Connect last historical point to first forecast point for visual continuity
        conn_dates = [history_dates[-1]] + fut_dates if history_dates else fut_dates
        conn_vals = [history_values[-1]] + fut_vals if history_values else fut_vals

        fig.add_trace(
            go.Scatter(
                x=conn_dates,
                y=conn_vals,
                mode="lines+markers",
                name="Projected Forecast",
                line=dict(color=cls.THEME["forecast_color"], width=3, dash="dash"),
                marker=dict(size=6, symbol="circle", color=cls.THEME["primary_dark"]),
            )
        )

        # Vertical divider line separating history from forecast
        if history_dates and fut_dates:
            fig.add_vline(
                x=history_dates[-1],
                line_width=1.5,
                line_dash="dot",
                line_color="#94A3B8",
                annotation_text="Forecast Horizon Start",
                annotation_position="top left",
                annotation_font=dict(size=11, color="#64748B"),
            )

        fig.update_layout(
            title=dict(
                text=f"Historical Observations vs. Projected Forecast: <b>{target_name}</b>",
                font=dict(size=15, color="#0F172A", family=cls.THEME["font_family"]),
            ),
            xaxis=dict(
                title="Timeline",
                gridcolor=cls.THEME["grid_color"],
                showgrid=True,
                zeroline=False,
            ),
            yaxis=dict(
                title=f"{target_name} Value",
                gridcolor=cls.THEME["grid_color"],
                showgrid=True,
                zeroline=False,
            ),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            hovermode="x unified",
            margin=dict(l=40, r=20, t=60, b=40),
            height=460,
        )
        return fig

    @classmethod
    def create_model_comparison_bar(
        cls,
        candidates: List[ModelCandidateResult],
        metric_key: str = "mae",
        higher_is_better: bool = False,
    ) -> go.Figure:
        """Horizontal bar chart comparing validation metric performance across models."""
        fig = go.Figure()

        valid_cands = [c for c in candidates if c.status == "success" and getattr(c.metrics, metric_key, None) is not None]
        if not valid_cands:
            return fig

        # Sort: best model first
        valid_cands.sort(key=lambda c: getattr(c.metrics, metric_key), reverse=higher_is_better)

        names = [c.model_name for c in valid_cands]
        scores = [getattr(c.metrics, metric_key) for c in valid_cands]
        colors = [cls.THEME["primary"] if i == 0 else "#94A3B8" for i in range(len(names))]

        fig.add_trace(
            go.Bar(
                y=names,
                x=scores,
                orientation="h",
                marker=dict(color=colors, line=dict(color="#CBD5E1", width=1)),
                text=[f"{s:.4f}" for s in scores],
                textposition="auto",
            )
        )

        metric_label = "Mean Absolute Error (MAE)" if metric_key == "mae" else metric_key.upper()
        fig.update_layout(
            title=dict(
                text=f"Validation Performance Comparison ({metric_label})",
                font=dict(size=14, color="#0F172A", family=cls.THEME["font_family"]),
            ),
            xaxis=dict(
                title=f"Validation {metric_label}",
                gridcolor=cls.THEME["grid_color"],
            ),
            yaxis=dict(autorange="reversed"),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            margin=dict(l=40, r=20, t=50, b=40),
            height=280,
        )
        return fig

    @classmethod
    def create_feature_importance_bar(
        cls,
        importance_items: List[FeatureImportanceItem],
    ) -> go.Figure:
        """Horizontal bar chart ranking influential predictive factors."""
        fig = go.Figure()
        if not importance_items:
            return fig

        # Reverse for top-down display
        items = importance_items[::-1]
        features = [it.feature for it in items]
        pcts = [it.percentage for it in items]

        fig.add_trace(
            go.Bar(
                y=features,
                x=pcts,
                orientation="h",
                marker=dict(color="#3B82F6"),
                text=[f"{p:.1f}%" for p in pcts],
                textposition="auto",
            )
        )

        fig.update_layout(
            title=dict(
                text="Influential Feature Attribution (% Contribution)",
                font=dict(size=14, color="#0F172A", family=cls.THEME["font_family"]),
            ),
            xaxis=dict(title="Relative Influence (%)", gridcolor=cls.THEME["grid_color"]),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            margin=dict(l=40, r=20, t=50, b=40),
            height=300,
        )
        return fig

    @classmethod
    def create_actual_vs_predicted_scatter(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        target_name: str,
    ) -> go.Figure:
        """Scatter plot comparing actual validation observations to predicted values with 45° reference."""
        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=y_true,
                y=y_pred,
                mode="markers",
                name="Validation Point",
                marker=dict(color=cls.THEME["primary"], size=7, opacity=0.75),
            )
        )

        # 45-degree ideal fit line
        min_v = min(float(np.min(y_true)), float(np.min(y_pred)))
        max_v = max(float(np.max(y_true)), float(np.max(y_pred)))
        fig.add_trace(
            go.Scatter(
                x=[min_v, max_v],
                y=[min_v, max_v],
                mode="lines",
                name="Ideal Fit (y = x)",
                line=dict(color="#DC2626", width=2, dash="dash"),
            )
        )

        fig.update_layout(
            title=dict(
                text=f"Validation Fit: Actual vs Predicted <b>{target_name}</b>",
                font=dict(size=14, color="#0F172A", family=cls.THEME["font_family"]),
            ),
            xaxis=dict(title="Actual Value", gridcolor=cls.THEME["grid_color"]),
            yaxis=dict(title="Predicted Value", gridcolor=cls.THEME["grid_color"]),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            margin=dict(l=40, r=20, t=50, b=40),
            height=350,
        )
        return fig
