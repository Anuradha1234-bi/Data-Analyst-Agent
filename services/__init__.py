"""Services package for AI Data Analyst Agent."""

from .relationship_detector import RelationshipDetector
from .analyst import AnalystService, AnalystResponse
from .chart_generator import ChartGeneratorService
from .report_generator import ReportGeneratorService
from .dataset_profiler import DatasetProfilerService
from .anomaly_service import AnomalyService

from .insight_service import InsightService
from .phase5_engine import (
    calculate_column_statistics,
    analyze_distributions,
    calculate_correlations,
    analyze_categories,
    analyze_trends,
    detect_date_columns,
    summarize_anomaly_results,
    summarize_data_quality,
    analyze_across_datasets,
    generate_insights,
    validate_insights,
    prepare_analysis_visualizations,
    explain_insights_with_ai,
    run_phase5_analysis,
)

__all__ = [
    "RelationshipDetector",
    "AnalystService",
    "AnalystResponse",
    "ChartGeneratorService",
    "ReportGeneratorService",
    "DatasetProfilerService",
    "AnomalyService",
    "InsightService",
    "calculate_column_statistics",
    "analyze_distributions",
    "calculate_correlations",
    "analyze_categories",
    "analyze_trends",
    "detect_date_columns",
    "summarize_anomaly_results",
    "summarize_data_quality",
    "analyze_across_datasets",
    "generate_insights",
    "validate_insights",
    "prepare_analysis_visualizations",
    "explain_insights_with_ai",
    "run_phase5_analysis",
]


