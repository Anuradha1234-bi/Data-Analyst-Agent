"""Unified Report Data Models for AI Data Analyst Agent.

Provides standardized containers for Dataset Information, Data Profile,
Cleaning Summary, Anomaly Summary, Prediction Summary, Forecast Summary,
and Ask Analyst Session Summary.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Union


@dataclass
class DatasetInfoSection:
    """Basic metadata about the analyzed dataset."""

    dataset_name: str
    file_type: str = "CSV"
    rows: int = 0
    columns: int = 0
    analysis_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "file_type": self.file_type,
            "rows": self.rows,
            "columns": self.columns,
            "analysis_time": self.analysis_time,
        }


@dataclass
class ColumnProfileItem:
    """Statistical and structural characteristics of a single feature."""

    name: str
    dtype: str
    semantic_type: str = "UNKNOWN"
    missing_count: int = 0
    missing_percentage: float = 0.0
    unique_count: int = 0
    unique_percentage: float = 0.0
    numeric_stats: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "column": self.name,
            "dtype": self.dtype,
            "semantic_type": self.semantic_type,
            "missing_count": self.missing_count,
            "missing_percentage": round(self.missing_percentage, 2),
            "unique_count": self.unique_count,
            "unique_percentage": round(self.unique_percentage, 2),
        }
        if self.numeric_stats:
            for k, v in self.numeric_stats.items():
                if v is not None:
                    d[f"stat_{k}"] = round(float(v), 2)
        return d


@dataclass
class DataProfileSection:
    """Comprehensive data profiling results and quality metrics."""

    total_rows: int
    total_columns: int
    total_missing: int
    missing_percentage: float
    duplicate_rows: int
    duplicate_percentage: float
    type_counts: Dict[str, int] = field(default_factory=dict)
    health_score: Optional[int] = None
    health_status: Optional[str] = None
    health_explanation: Optional[str] = None
    columns: List[ColumnProfileItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "total_missing": self.total_missing,
            "missing_percentage": round(self.missing_percentage, 2),
            "duplicate_rows": self.duplicate_rows,
            "duplicate_percentage": round(self.duplicate_percentage, 2),
            "type_counts": self.type_counts,
            "health_score": self.health_score,
            "health_status": self.health_status,
            "health_explanation": self.health_explanation,
            "columns_count": len(self.columns),
        }


@dataclass
class CleaningSection:
    """Audit summary of data cleaning and remediation actions."""

    before_rows: int
    after_rows: int
    before_columns: int
    after_columns: int
    missing_handled: int
    duplicates_handled: int
    columns_modified: List[str] = field(default_factory=list)
    rows_affected: int = 0
    changes_applied: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "before_rows": self.before_rows,
            "after_rows": self.after_rows,
            "before_columns": self.before_columns,
            "after_columns": self.after_columns,
            "missing_handled": self.missing_handled,
            "duplicates_handled": self.duplicates_handled,
            "columns_modified": self.columns_modified,
            "rows_affected": self.rows_affected,
            "changes_applied": self.changes_applied,
            "timestamp": self.timestamp,
        }


@dataclass
class AnomalyMethodResult:
    """Summary of an anomaly detection algorithm execution."""

    method: str
    anomalies_detected: int
    anomaly_percentage: float
    features_used: List[str] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "anomalies_detected": self.anomalies_detected,
            "anomaly_percentage": round(self.anomaly_percentage, 2),
            "features_used": self.features_used,
            "details": self.details,
        }


@dataclass
class AnomalySection:
    """Aggregated anomaly detection findings and treatments."""

    methods: List[AnomalyMethodResult] = field(default_factory=list)
    total_anomalies: int = 0
    treatment_applied: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "methods": [m.to_dict() for m in self.methods],
            "total_anomalies": self.total_anomalies,
            "treatment_applied": self.treatment_applied,
        }


@dataclass
class PredictionSection:
    """Supervised regression or classification model results."""

    target: str
    problem_type: str
    selected_model: str
    metrics: Dict[str, float] = field(default_factory=dict)
    prediction_count: int = 0
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    top_features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "problem_type": self.problem_type,
            "selected_model": self.selected_model,
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
            "prediction_count": self.prediction_count,
            "top_features": self.top_features,
            "predictions_sample_count": len(self.predictions),
        }


@dataclass
class ForecastSection:
    """Time-series forecasting models and projected values."""

    time_column: str
    target: str
    model: str
    forecast_horizon: int
    frequency: Optional[str] = None
    forecast_results: List[Dict[str, Any]] = field(default_factory=list)  # {period, predicted_value, lower_bound, upper_bound}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_column": self.time_column,
            "target": self.target,
            "model": self.model,
            "forecast_horizon": self.forecast_horizon,
            "frequency": self.frequency,
            "forecast_count": len(self.forecast_results),
        }


@dataclass
class AskAnalystQueryItem:
    """A natural-language question asked and answered during the session."""

    question: str
    answer: str
    confidence: str = "High"
    intent: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "confidence": self.confidence,
            "intent": self.intent,
            "timestamp": self.timestamp,
        }


@dataclass
class AskAnalystSection:
    """Collection of queries and answers executed during Ask Analyst."""

    queries: List[AskAnalystQueryItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "queries": [q.to_dict() for q in self.queries],
            "total_queries": len(self.queries),
        }


@dataclass
class UnifiedReport:
    """Master analytical report containing only actual evaluated results."""

    dataset_name: str
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dataset_info: Optional[DatasetInfoSection] = None
    profile: Optional[DataProfileSection] = None
    cleaning: Optional[CleaningSection] = None
    anomaly: Optional[AnomalySection] = None
    prediction: Optional[PredictionSection] = None
    forecast: Optional[ForecastSection] = None
    ask_analyst: Optional[AskAnalystSection] = None

    def has_any_analysis(self) -> bool:
        """Return True if at least one analytical section contains actual data."""
        return any([
            self.profile is not None,
            self.cleaning is not None,
            self.anomaly is not None and len(self.anomaly.methods) > 0,
            self.prediction is not None,
            self.forecast is not None,
            self.ask_analyst is not None and len(self.ask_analyst.queries) > 0,
        ])

    def available_sections(self) -> List[str]:
        """Return human-readable names of currently populated report sections."""
        secs = []
        if self.profile is not None:
            secs.append("Data Profile")
        if self.cleaning is not None:
            secs.append("Data Cleaning")
        if self.anomaly is not None and len(self.anomaly.methods) > 0:
            secs.append("Anomalies")
        if self.prediction is not None:
            secs.append("Prediction")
        if self.forecast is not None:
            secs.append("Forecasting")
        if self.ask_analyst is not None and len(self.ask_analyst.queries) > 0:
            secs.append("Ask Analyst")
        return secs

    def to_dict(self) -> Dict[str, Any]:
        """Convert populated report sections into a serializable dictionary."""
        d: Dict[str, Any] = {
            "dataset_name": self.dataset_name,
            "generated_at": self.generated_at,
            "available_sections": self.available_sections(),
            "has_analysis": self.has_any_analysis(),
        }
        if self.dataset_info:
            d["dataset_info"] = self.dataset_info.to_dict()
        if self.profile:
            d["profile"] = self.profile.to_dict()
        if self.cleaning:
            d["cleaning"] = self.cleaning.to_dict()
        if self.anomaly:
            d["anomaly"] = self.anomaly.to_dict()
        if self.prediction:
            d["prediction"] = self.prediction.to_dict()
        if self.forecast:
            d["forecast"] = self.forecast.to_dict()
        if self.ask_analyst:
            d["ask_analyst"] = self.ask_analyst.to_dict()
        return d
