"""Query Package - Phase 6 Intelligent Ask Analyst & Natural-Language Data Query Engine."""

from query.config import (
    DEFAULT_QUERY_CONFIG,
    get_default_query_config,
    validate_query_config,
    normalize_query_config,
)
from query.query_models import (
    QueryIntent,
    QueryFilter,
    QueryOutputConfig,
    StructuredQueryPlan,
    IntentDetectionResult,
    ColumnResolutionResult,
    QueryValidationResult,
    QueryExecutionResult,
)
from query.intent_detector import detect_query_intent
from query.query_planner import build_query_plan
from query.query_validator import validate_query_plan
from query.column_resolver import resolve_column, is_metadata_column, filter_metadata_columns
from query.query_executor import execute_query
from query.aggregation_engine import compute_aggregation
from query.filter_engine import apply_filters
from query.comparison_engine import compare_groups, compare_dates
from query.trend_query_engine import compute_trend_query
from query.correlation_query_engine import compute_correlation_query
from query.anomaly_query_engine import compute_anomaly_query
from query.cross_dataset_query_engine import execute_cross_dataset_query
from query.evidence_extractor import extract_query_evidence
from query.answer_generator import generate_query_answer
from query.chart_recommender import recommend_query_visualization
from query.orchestrator import run_ask_analyst_query

__all__ = [
    "DEFAULT_QUERY_CONFIG",
    "get_default_query_config",
    "validate_query_config",
    "normalize_query_config",
    "QueryIntent",
    "QueryFilter",
    "QueryOutputConfig",
    "StructuredQueryPlan",
    "IntentDetectionResult",
    "ColumnResolutionResult",
    "QueryValidationResult",
    "QueryExecutionResult",
    "detect_query_intent",
    "build_query_plan",
    "validate_query_plan",
    "resolve_column",
    "is_metadata_column",
    "filter_metadata_columns",
    "execute_query",
    "compute_aggregation",
    "apply_filters",
    "compare_groups",
    "compare_dates",
    "compute_trend_query",
    "compute_correlation_query",
    "compute_anomaly_query",
    "execute_cross_dataset_query",
    "extract_query_evidence",
    "generate_query_answer",
    "recommend_query_visualization",
    "run_ask_analyst_query",
]
