"""Centralized Prediction & Forecasting Configuration.

Defines default parameters, validation rules, and normalizers for:
- Forecasting horizon, frequencies, and lag window parameters
- Validation strategy (chronological vs random test split)
- Model enable/disable flags
- Feature selection & leakage detection guards
- Phase 4 Anomaly integration policy
"""

import copy
from typing import Dict, Any, List, Tuple, Optional


DEFAULT_PREDICTION_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "mode": "auto",  # "auto" | "forecasting" | "regression" | "classification"
    "target": None,
    "date_column": None,
    "forecast_horizon": 7,
    "validation": {
        "test_size": 0.20,
        "time_aware": True,
        "n_splits": 5,
        "random_state": 42,
    },
    "forecasting": {
        "enabled": True,
        "frequency": "auto",
        "lags": [1, 2, 3, 7, 14, 30],
        "rolling_windows": [7, 14, 30],
    },
    "regression": {
        "enabled": True,
    },
    "classification": {
        "enabled": True,
    },
    "models": {
        "naive": True,
        "moving_average": True,
        "linear_regression": True,
        "ridge": True,
        "random_forest": True,
        "gradient_boosting": True,
    },
    "features": {
        "exclude_identifiers": True,
        "exclude_index_columns": True,
        "detect_leakage": True,
    },
    "anomalies": {
        "use_phase4_results": True,
        "exclude_flagged_by_default": False,
    },
    "explainability": {
        "enabled": True,
        "max_features": 10,
    },
    "visualization": {
        "enabled": True,
        "max_charts": 8,
    },
}


def get_default_prediction_config() -> Dict[str, Any]:
    """Return an isolated deep copy of the standard prediction configuration."""
    return copy.deepcopy(DEFAULT_PREDICTION_CONFIG)


def validate_prediction_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate prediction configuration parameters against safety boundaries.

    Returns:
        (is_valid, list_of_error_strings)
    """
    errors: List[str] = []
    if not isinstance(config, dict):
        return False, ["Prediction config must be a dictionary."]

    # Validate mode
    mode = config.get("mode", "auto")
    if mode not in ["auto", "forecasting", "regression", "classification"]:
        errors.append(f"Invalid mode '{mode}'. Allowed: 'auto', 'forecasting', 'regression', 'classification'.")

    # Validate horizon
    horizon = config.get("forecast_horizon", 7)
    if not isinstance(horizon, int) or horizon < 1 or horizon > 365:
        errors.append(f"Forecast horizon must be an integer between 1 and 365. Received: {horizon}.")

    # Validate validation settings
    val_cfg = config.get("validation", {})
    if isinstance(val_cfg, dict):
        test_size = val_cfg.get("test_size", 0.20)
        if not isinstance(test_size, (int, float)) or not (0.05 <= test_size <= 0.50):
            errors.append(f"Validation test_size must be a float between 0.05 and 0.50. Received: {test_size}.")
    else:
        errors.append("Config 'validation' must be a dictionary.")

    # Validate lags
    fc_cfg = config.get("forecasting", {})
    if isinstance(fc_cfg, dict):
        lags = fc_cfg.get("lags", [])
        if not isinstance(lags, list) or any(not isinstance(lag, int) or lag < 1 for lag in lags):
            errors.append("Forecasting lags must be a list of positive integers.")
    else:
        errors.append("Config 'forecasting' must be a dictionary.")

    return len(errors) == 0, errors


def normalize_prediction_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensure all required configuration keys are present, falling back to defaults."""
    base = get_default_prediction_config()
    if not config or not isinstance(config, dict):
        return base

    for k, v in config.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            base[k].update(v)
        else:
            base[k] = v

    return base
