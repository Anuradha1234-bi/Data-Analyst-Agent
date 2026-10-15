"""Query Configuration Module for Phase 6 Natural Language Query Engine.

Provides default settings, validation, and normalization for safe query execution.
"""

from typing import Dict, Any, Tuple, List
import copy

DEFAULT_QUERY_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "max_result_rows": 1000,
    "max_top_n": 100,
    "allow_arbitrary_code": False,
    "allow_arbitrary_sql": False,
    "require_query_validation": True,
    "require_validated_relationship": True,
    "allow_many_to_many": False,
    "max_join_row_growth_ratio": 2.0,
    "use_cleaned_data_by_default": True,
    "use_phase4_results": True,
    "use_phase5_results": True,
    "enable_query_history": True,
    "max_history_items": 20,
    "enable_follow_up_context": True,
    "max_context_items": 10,
    "enable_charts": True,
    "enable_ai_answers": True,
    "allow_speculation": False,
    "minimum_confidence": 0.60,
}


def get_default_query_config() -> Dict[str, Any]:
    """Return a deep copy of the default query configuration."""
    return copy.deepcopy(DEFAULT_QUERY_CONFIG)


def validate_query_config(config: Any) -> Tuple[bool, List[str]]:
    """Validate query configuration dictionary.
    
    Returns:
        (is_valid, list_of_errors)
    """
    if not isinstance(config, dict):
        return False, ["Configuration must be a dictionary."]

    errors: List[str] = []

    # Mandatory security keys
    if config.get("allow_arbitrary_code", False) is True:
        errors.append("Security violation: 'allow_arbitrary_code' cannot be enabled.")
    if config.get("allow_arbitrary_sql", False) is True:
        errors.append("Security violation: 'allow_arbitrary_sql' cannot be enabled.")

    # Numeric bounds
    max_rows = config.get("max_result_rows")
    if not isinstance(max_rows, int) or max_rows <= 0:
        errors.append("'max_result_rows' must be a positive integer.")

    max_top_n = config.get("max_top_n")
    if not isinstance(max_top_n, int) or max_top_n <= 0:
        errors.append("'max_top_n' must be a positive integer.")

    min_conf = config.get("minimum_confidence")
    if not isinstance(min_conf, (int, float)) or not (0.0 <= min_conf <= 1.0):
        errors.append("'minimum_confidence' must be a float between 0.0 and 1.0.")

    growth_ratio = config.get("max_join_row_growth_ratio")
    if not isinstance(growth_ratio, (int, float)) or growth_ratio < 1.0:
        errors.append("'max_join_row_growth_ratio' must be a number >= 1.0.")

    return len(errors) == 0, errors


def normalize_query_config(config: Any) -> Dict[str, Any]:
    """Normalize and merge user-provided config with default configuration."""
    base = get_default_query_config()
    if not isinstance(config, dict):
        return base

    for key, val in config.items():
        if key in base:
            # Enforce hard security limits
            if key in ("allow_arbitrary_code", "allow_arbitrary_sql"):
                base[key] = False
            else:
                base[key] = val
        else:
            base[key] = val

    # Ensure security parameters are strictly enforced
    base["allow_arbitrary_code"] = False
    base["allow_arbitrary_sql"] = False
    return base
