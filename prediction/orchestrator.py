"""Prediction & Forecasting Public Orchestration Entrypoint.

Exposes the clean public function run_prediction() to UI pages, Insight Engine,
and Ask Analyst query agents.
"""

from typing import Dict, Any, List, Optional, Callable
import pandas as pd

from models.prediction import PredictionResult
from prediction.prediction_engine import PredictionEngine


def run_prediction(
    df: pd.DataFrame,
    dataset_name: str = "dataset.csv",
    target_col: Optional[str] = None,
    date_col: Optional[str] = None,
    mode: str = "auto",
    horizon: int = 7,
    config: Optional[Dict[str, Any]] = None,
    exclude_anomalies: bool = False,
    anomaly_indices: Optional[List[Any]] = None,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> PredictionResult:
    """Execute end-to-end predictive modeling and forecasting on the dataset.

    Args:
        df: Input tabular DataFrame.
        dataset_name: Identifier for dataset in session state.
        target_col: Specific target column name (auto-detected if None).
        date_col: Specific date column for time-series (auto-detected if None).
        mode: "auto" | "forecasting" | "regression" | "classification".
        horizon: Forecast step horizon for time-series forecasting (1 to 365).
        config: Custom parameter configuration dictionary.
        exclude_anomalies: Whether to filter out Phase 4 detected anomalies.
        anomaly_indices: Explicit list of row indices to exclude if requested.
        progress_callback: Optional UI status update hook.

    Returns:
        Structured PredictionResult with metrics, predictions, uncertainty, and explanations.
    """
    return PredictionEngine.execute_prediction(
        df=df,
        dataset_name=dataset_name,
        target_col=target_col,
        date_col=date_col,
        mode=mode,
        horizon=horizon,
        config=config,
        exclude_anomalies=exclude_anomalies,
        anomaly_indices=anomaly_indices,
        progress_callback=progress_callback,
    )
