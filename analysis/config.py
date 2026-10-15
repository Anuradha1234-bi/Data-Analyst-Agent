"""Centralized Anomaly Detection Configuration, Validation, and Normalization."""

from typing import Dict, Any
import copy

DEFAULT_ANOMALY_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "methods": {
        "iqr": True,
        "z_score": True,
        "robust_z_score": True,
        "isolation_forest": True,
    },
    "iqr": {
        "multiplier": 1.5,
    },
    "z_score": {
        "threshold": 3.0,
    },
    "robust_z_score": {
        "threshold": 3.5,
    },
    "isolation_forest": {
        "n_estimators": 200,
        "contamination": "auto",
        "random_state": 42,
    },
    "features": {
        "numeric_only": True,
        "exclude_identifiers": True,
        "exclude_index_columns": True,
        "exclude_constant_columns": True,
    },
    "treatment": {
        "default_action": "flag_only",
        "allow_remove": True,
        "allow_median_replace": True,
        "allow_iqr_cap": True,
        "allow_winsorize": True,
    },
    "safety": {
        "require_confirmation": True,
        "preserve_original": True,
        "max_join_row_growth_ratio": 2.0,
    },
    "display": {
        "max_anomaly_rows": 500,
        "max_chart_count": 10,
    },
}


def get_default_anomaly_config() -> Dict[str, Any]:
    """Retrieve an immutable deep-copy of the default anomaly configuration."""
    return copy.deepcopy(DEFAULT_ANOMALY_CONFIG)


def validate_anomaly_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate user anomaly detection configuration.

    Returns:
        Dict with keys 'valid' (bool), 'errors' (list), 'warnings' (list).
    """
    errors = []
    warnings = []

    if not isinstance(config, dict):
        return {"valid": False, "errors": ["Configuration must be a dictionary."], "warnings": []}

    # Validate methods
    methods = config.get("methods", {})
    if not isinstance(methods, dict) or not any(methods.values()):
        errors.append("At least one anomaly detection method must be enabled (iqr, z_score, robust_z_score, or isolation_forest).")

    # Validate IQR
    iqr_cfg = config.get("iqr", {})
    if "multiplier" in iqr_cfg:
        try:
            m = float(iqr_cfg["multiplier"])
            if m <= 0:
                errors.append("IQR multiplier must be greater than 0.")
            elif m < 1.0 or m > 5.0:
                warnings.append(f"IQR multiplier {m} is atypical (standard range is 1.5 to 3.0).")
        except (ValueError, TypeError):
            errors.append("IQR multiplier must be a numeric value.")

    # Validate Z-score
    z_cfg = config.get("z_score", {})
    if "threshold" in z_cfg:
        try:
            z_thresh = float(z_cfg["threshold"])
            if z_thresh <= 0:
                errors.append("Z-score threshold must be greater than 0.")
            elif z_thresh < 1.5 or z_thresh > 5.0:
                warnings.append(f"Z-score threshold {z_thresh} is outside common range (2.0 - 3.5).")
        except (ValueError, TypeError):
            errors.append("Z-score threshold must be a numeric value.")

    # Validate Robust Z-score
    rz_cfg = config.get("robust_z_score", {})
    if "threshold" in rz_cfg:
        try:
            rz_thresh = float(rz_cfg["threshold"])
            if rz_thresh <= 0:
                errors.append("Robust Z-score threshold must be greater than 0.")
            elif rz_thresh < 2.0 or rz_thresh > 6.0:
                warnings.append(f"Robust Z-score threshold {rz_thresh} is outside common range (2.5 - 4.5).")
        except (ValueError, TypeError):
            errors.append("Robust Z-score threshold must be a numeric value.")

    # Validate Isolation Forest
    if_cfg = config.get("isolation_forest", {})
    if "n_estimators" in if_cfg:
        try:
            n_est = int(if_cfg["n_estimators"])
            if n_est < 10 or n_est > 1000:
                warnings.append("Isolation Forest n_estimators recommended between 50 and 500.")
        except (ValueError, TypeError):
            errors.append("Isolation Forest n_estimators must be an integer.")

    if "contamination" in if_cfg:
        contam = if_cfg["contamination"]
        if contam != "auto":
            try:
                c_val = float(contam)
                if c_val <= 0.0 or c_val > 0.5:
                    errors.append("Isolation Forest contamination ratio must be 'auto' or a float between 0.001 and 0.5.")
            except (ValueError, TypeError):
                errors.append("Isolation Forest contamination must be 'auto' or numeric.")

    # Validate safety
    safety = config.get("safety", {})
    if "max_join_row_growth_ratio" in safety:
        try:
            r = float(safety["max_join_row_growth_ratio"])
            if r < 1.0:
                errors.append("max_join_row_growth_ratio cannot be less than 1.0.")
        except (ValueError, TypeError):
            errors.append("max_join_row_growth_ratio must be a numeric value.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def normalize_anomaly_config(config: Dict[str, Any] | None) -> Dict[str, Any]:
    """Deep-merge a user-provided or partial configuration with defaults."""
    default = get_default_anomaly_config()
    if not config or not isinstance(config, dict):
        return default

    def _merge(source: dict, target: dict) -> dict:
        for k, v in source.items():
            if k in target and isinstance(target[k], dict) and isinstance(v, dict):
                target[k] = _merge(v, target[k])
            else:
                target[k] = copy.deepcopy(v)
        return target

    return _merge(config, default)
