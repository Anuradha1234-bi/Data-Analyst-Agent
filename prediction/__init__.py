"""Prediction & Forecasting Package - Phase 5 Intelligent Prediction & Forecasting Engine."""

from prediction.config import (
    DEFAULT_PREDICTION_CONFIG,
    get_default_prediction_config,
    validate_prediction_config,
    normalize_prediction_config,
)
from prediction.target_detector import TargetDetector
from prediction.problem_detector import ProblemDetector
from prediction.feature_selector import FeatureSelector
from prediction.leakage_detector import LeakageDetector
from prediction.preprocessing import PreprocessingService
from prediction.time_series import TimeSeriesService
from prediction.forecasting import ForecastingEngine
from prediction.regression import RegressionEngine
from prediction.classification import ClassificationEngine
from prediction.model_registry import ModelRegistry
from prediction.model_evaluation import ModelEvaluator
from prediction.model_selection import ModelSelector
from prediction.uncertainty import UncertaintyService
from prediction.feature_importance import FeatureImportanceService
from prediction.explanation import ExplanationService
from prediction.visualization import PredictionVisualizer
from prediction.prediction_engine import PredictionEngine
from prediction.orchestrator import run_prediction

__all__ = [
    "DEFAULT_PREDICTION_CONFIG",
    "get_default_prediction_config",
    "validate_prediction_config",
    "normalize_prediction_config",
    "TargetDetector",
    "ProblemDetector",
    "FeatureSelector",
    "LeakageDetector",
    "PreprocessingService",
    "TimeSeriesService",
    "ForecastingEngine",
    "RegressionEngine",
    "ClassificationEngine",
    "ModelRegistry",
    "ModelEvaluator",
    "ModelSelector",
    "UncertaintyService",
    "FeatureImportanceService",
    "ExplanationService",
    "PredictionVisualizer",
    "PredictionEngine",
    "run_prediction",
]
