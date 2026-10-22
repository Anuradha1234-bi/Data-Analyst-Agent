"""Filter Engine for Phase 6 Natural Language Query Engine.

Applies structured filters deterministically without using eval(), exec(), or arbitrary code.
Supports numeric comparisons, string equality, list membership, date ranges, and string containment.
"""

from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np


def _build_filter_mask(
    df: pd.DataFrame,
    f: Dict[str, Any],
) -> Tuple[Optional[pd.Series], List[str]]:
    """Build a boolean Series mask for a single structured filter dict."""
    col = f.get("column")
    op = f.get("operator")
    val = f.get("value")
    warnings: List[str] = []

    if col not in df.columns:
        warnings.append(f"Filter column '{col}' not in DataFrame; skipping.")
        return None, warnings

    series = df[col]

    MONTH_MAP = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }

    try:
        # Month handling
        if op in ("month", "month_equals") or (isinstance(val, str) and val.lower() in MONTH_MAP and (pd.api.types.is_datetime64_any_dtype(series) or "date" in str(col).lower() or "time" in str(col).lower())):
            month_num = MONTH_MAP.get(str(val).lower())
            if month_num is not None:
                s_dt = pd.to_datetime(series, errors="coerce")
                return (s_dt.dt.month == month_num), warnings

        # Datetime handling
        if pd.api.types.is_datetime64_any_dtype(series) or (isinstance(val, str) and "-" in val and not str(val).isdigit()):
            try:
                s_dt = pd.to_datetime(series, errors="coerce")
                v_dt = pd.to_datetime(val, errors="coerce")
                if not pd.isna(v_dt):
                    if op in (">", "gt"):
                        return (s_dt > v_dt), warnings
                    elif op in (">=", "gte"):
                        return (s_dt >= v_dt), warnings
                    elif op in ("<", "lt"):
                        return (s_dt < v_dt), warnings
                    elif op in ("<=", "lte"):
                        return (s_dt <= v_dt), warnings
                    elif op in ("==", "=", "eq"):
                        return (s_dt == v_dt), warnings
                    elif op in ("!=", "neq"):
                        return (s_dt != v_dt), warnings
            except Exception:
                pass

        # Numeric handling
        if pd.api.types.is_numeric_dtype(series) or (isinstance(val, (int, float)) and not isinstance(val, bool)):
            try:
                num_series = pd.to_numeric(series, errors="coerce")
                num_val = float(val) if not isinstance(val, (int, float)) else val
                if op in (">", "gt"):
                    return (num_series > num_val), warnings
                elif op in (">=", "gte"):
                    return (num_series >= num_val), warnings
                elif op in ("<", "lt"):
                    return (num_series < num_val), warnings
                elif op in ("<=", "lte"):
                    return (num_series <= num_val), warnings
                elif op in ("==", "=", "eq"):
                    return (num_series == num_val), warnings
                elif op in ("!=", "neq"):
                    return (num_series != num_val), warnings
                elif op == "in" and isinstance(val, (list, tuple, set)):
                    return num_series.isin(val), warnings
                elif op == "not in" and isinstance(val, (list, tuple, set)):
                    return ~num_series.isin(val), warnings
                elif op == "between" and isinstance(val, (list, tuple)) and len(val) == 2:
                    return ((num_series >= val[0]) & (num_series <= val[1])), warnings
                else:
                    warnings.append(f"Unsupported numeric operator '{op}' for column '{col}'.")
                    return None, warnings
            except Exception as e:
                warnings.append(f"Failed to apply numeric filter on '{col}': {str(e)}")
                return None, warnings

        # Categorical / String handling
        s_str = series.astype(str).str.lower().str.strip()
        val_str = str(val).lower().strip()

        if op in ("==", "=", "eq"):
            return (s_str == val_str), warnings
        elif op in ("!=", "neq"):
            return (s_str != val_str), warnings
        elif op == "in" and isinstance(val, (list, tuple, set)):
            val_set = {str(v).lower().strip() for v in val}
            return s_str.isin(val_set), warnings
        elif op == "not in" and isinstance(val, (list, tuple, set)):
            val_set = {str(v).lower().strip() for v in val}
            return ~s_str.isin(val_set), warnings
        elif op == "contains":
            return series.astype(str).str.contains(str(val), case=False, na=False), warnings
        elif op in (">", ">=", "<", "<="):
            try:
                num_series = pd.to_numeric(series, errors="coerce")
                num_val = float(val)
                if op == ">":
                    return (num_series > num_val), warnings
                elif op == ">=":
                    return (num_series >= num_val), warnings
                elif op == "<":
                    return (num_series < num_val), warnings
                elif op == "<=":
                    return (num_series <= num_val), warnings
            except Exception:
                warnings.append(f"Comparison '{op}' cannot be applied to non-numeric column '{col}'.")
                return None, warnings
        else:
            warnings.append(f"Unsupported operator '{op}' for column '{col}'.")
            return None, warnings

    except Exception as e:
        warnings.append(f"Error evaluating filter on '{col}': {str(e)}")
        return None, warnings

    return None, warnings


def apply_filters(
    df: pd.DataFrame,
    filters: List[Dict[str, Any]],
    logic: str = "AND",
) -> Tuple[pd.DataFrame, List[str]]:
    """Apply a list of structured filters to a DataFrame safely with AND / OR conjunctions.
    
    Each filter dict: {"column": str, "operator": str, "value": Any}
    Returns:
        (filtered_df, warnings)
    """
    if df is None or df.empty or not filters:
        return df, []

    warnings: List[str] = []
    is_or = str(logic).strip().upper() == "OR"
    overall_mask = pd.Series(False, index=df.index) if is_or else pd.Series(True, index=df.index)
    valid_filter_count = 0

    for f in filters:
        if not isinstance(f, dict):
            continue
        mask, f_warns = _build_filter_mask(df, f)
        warnings.extend(f_warns)
        if mask is not None:
            valid_filter_count += 1
            if is_or:
                overall_mask = overall_mask | mask
            else:
                overall_mask = overall_mask & mask

    if valid_filter_count == 0:
        return df, warnings

    filtered = df[overall_mask]
    return filtered, warnings
