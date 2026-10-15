"""Insight and Intelligent Analysis Data Models.

Defines structured containers for Insight Engine findings, Trends,
Distributions, Correlations, Top/Bottom Category Rankings, and Cross-Dataset Linkages.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import pandas as pd


@dataclass
class Insight:
    """Standardized enterprise insight container.
    
    Adheres strictly to the schema:
    Title, Category, Finding, Evidence, Severity, Relevant Dataset,
    Relevant Columns, Recommended Investigation.
    """

    title: str
    category: str  # Data Quality, Trend, Distribution, Correlation, Category, Anomaly, Comparison, Cross-Dataset, Statistical
    finding: str
    evidence: str
    severity: str  # High, Medium, Low
    relevant_dataset: str
    relevant_columns: List[str]
    recommended_investigation: str
    chart_type: Optional[str] = None  # line, bar, scatter, heatmap, box, None
    chart_data: Optional[Dict[str, Any]] = None
    ai_explanation: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class TrendAnalysisResult:
    """Time-series and sequential trend detection output."""

    dataset_name: str
    date_column: str
    metric_column: str
    start_date: str
    end_date: str
    start_value: float
    end_value: float
    change_pct: float
    direction: str  # Increasing, Decreasing, Stable, Volatile
    peak_date: str
    peak_value: float
    trough_date: str
    trough_value: float
    sudden_changes: List[Dict[str, Any]] = field(default_factory=list)
    stable_periods_count: int = 0
    records_analyzed: int = 0
    timeseries_df: Optional[pd.DataFrame] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class TopBottomCategoryResult:
    """Categorical performance and top/bottom rankings container."""

    dataset_name: str
    category_column: str
    metric_column: str
    aggregation: str  # sum, mean
    top_items: List[Dict[str, Any]] = field(default_factory=list)  # [{"category": "...", "value": 100, "share_pct": 25.0}]
    bottom_items: List[Dict[str, Any]] = field(default_factory=list)
    total_metric_value: float = 0.0
    concentration_ratio_top3: float = 0.0  # % of total held by top 3
    total_categories: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class DistributionAnalysisResult:
    """Parametric and non-parametric shape metrics for a numeric column."""

    dataset_name: str
    column: str
    count: int
    mean: float
    median: float
    std: float
    variance: float
    min_val: float
    max_val: float
    q1: float
    q3: float
    iqr: float
    skewness: float
    kurtosis: float
    shape_label: str  # Normal-like, Right-skewed, Left-skewed, High Variance, Low Variance / Concentrated
    is_skewed: bool
    is_high_variance: bool
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class CorrelationPair:
    """Statistical correlation relationship between two numeric features."""

    feature_x: str
    feature_y: str
    correlation: float
    strength: str  # Strong Positive, Strong Negative, Moderate Positive, Moderate Negative, Weak
    non_causal_statement: str


@dataclass
class CorrelationAnalysisResult:
    """Dataset-wide correlation analysis result."""

    dataset_name: str
    features_analyzed: List[str]
    correlation_matrix: Dict[str, Dict[str, float]]
    strong_positive_pairs: List[CorrelationPair] = field(default_factory=list)
    strong_negative_pairs: List[CorrelationPair] = field(default_factory=list)
    moderate_pairs: List[CorrelationPair] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class CategoryBreakdownItem:
    """Frequency and share for an individual category label."""

    category: str
    count: int
    percentage: float


@dataclass
class CategoryBreakdownResult:
    """Categorical distribution and imbalance diagnostic."""

    dataset_name: str
    column: str
    unique_count: int
    total_non_null: int
    items: List[CategoryBreakdownItem] = field(default_factory=list)
    most_frequent: str = ""
    most_frequent_pct: float = 0.0
    least_frequent: str = ""
    least_frequent_pct: float = 0.0
    is_imbalanced: bool = False
    imbalance_explanation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class CrossDatasetInsightResult:
    """Cross-dataset analytical linkage and aggregated metrics."""

    left_dataset: str
    right_dataset: str
    join_key: str
    relationship_confidence: str
    join_type: str
    is_blocked: bool
    block_reason: Optional[str]
    rows_before: int
    rows_after: int
    metric_column: Optional[str] = None
    group_column: Optional[str] = None
    breakdown: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@dataclass
class DatasetAnalysisResult:
    """Comprehensive analytical payload combining all Phase 5 modules for a dataset."""

    dataset_name: str
    row_count: int
    column_count: int
    numeric_columns: List[str] = field(default_factory=list)
    categorical_columns: List[str] = field(default_factory=list)
    date_columns: List[str] = field(default_factory=list)
    missing_count: int = 0
    missing_rate: float = 0.0
    duplicate_rows: int = 0
    duplicate_rate: float = 0.0
    distributions: Dict[str, DistributionAnalysisResult] = field(default_factory=dict)
    trends: List[TrendAnalysisResult] = field(default_factory=list)
    top_bottom_rankings: List[TopBottomCategoryResult] = field(default_factory=list)
    correlations: Optional[CorrelationAnalysisResult] = None
    categories: Dict[str, CategoryBreakdownResult] = field(default_factory=dict)
    insights: List[Insight] = field(default_factory=list)
    cross_dataset_results: List[CrossDatasetInsightResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
