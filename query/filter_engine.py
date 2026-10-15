"""Filter Engine for Phase 6 Natural Language Query Engine.

Applies structured filters deterministically without using eval(), exec(), or arbitrary code.
Supports numeric comparisons, string equality, list membership, date ranges, and string containment.
"""

from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np


def apply_filters(
    df: pd.DataFrame,
    filters: List[Dict[str, Any]],
) -> Tuple[pd.DataFrame, List[str]]:
    """Apply a list of structured filters to a DataFrame safely.
    
    Each filter dict: {"column": str, "operator": str, "value": Any}
    Returns:
        (filtered_df, warnings)
    """
    if df is None or df.empty or not filters:
        return df, []

    filtered = df.copy()
    warnings: List[str] = []

    for f in filters:
        if not isinstance(f, dict):
            continue

        col = f.get("column")
        op = f.get("operator")
        val = f.get("value")

        if col not in filtered.columns:
            warnings.append(f"Filter column '{col}' not in DataFrame; skipping.")
            continue

        try:
            series = filtered[col]

            # Datetime & Month handling
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

            if op in ("month", "month_equals") or (isinstance(val, str) and val.lower() in MONTH_MAP and (pd.api.types.is_datetime64_any_dtype(series) or "date" in str(col).lower() or "time" in str(col).lower())):
                month_num = MONTH_MAP.get(str(val).lower())
                if month_num is not None:
                    s_dt = pd.to_datetime(series, errors="coerce")
                    filtered = filtered[s_dt.dt.month == month_num]
                    continue

            if pd.api.types.is_datetime64_any_dtype(series) or (isinstance(val, str) and "-" in val):
                try:
                    s_dt = pd.to_datetime(series, errors="coerce")
                    v_dt = pd.to_datetime(val, errors="coerce")
                    if not pd.isna(v_dt):
                        if op in (">", "gt"):
                            mask = s_dt > v_dt
                        elif op in (">=", "gte"):
                            mask = s_dt >= v_dt
                        elif op in ("<", "lt"):
                            mask = s_dt < v_dt
                        elif op in ("<=", "lte"):
                            mask = s_dt <= v_dt
                        elif op in ("==", "=", "eq"):
                            mask = s_dt == v_dt
                        elif op in ("!=", "neq"):
                            mask = s_dt != v_dt
                        else:
                            mask = pd.Series(True, index=filtered.index)
                        filtered = filtered[mask]
                        continue
                except Exception:
                    pass

            # Numeric handling
            if pd.api.types.is_numeric_dtype(series):
                try:
                    num_val = float(val) if not isinstance(val, (int, float)) else val
                    if op in (">", "gt"):
                        filtered = filtered[filtered[col] > num_val]
                    elif op in (">=", "gte"):
                        filtered = filtered[filtered[col] >= num_val]
                    elif op in ("<", "lt"):
                        filtered = filtered[filtered[col] < num_val]
                    elif op in ("<=", "lte"):
                        filtered = filtered[filtered[col] <= num_val]
                    elif op in ("==", "=", "eq"):
                        filtered = filtered[filtered[col] == num_val]
                    elif op in ("!=", "neq"):
                        filtered = filtered[filtered[col] != num_val]
                    elif op == "in" and isinstance(val, (list, tuple, set)):
                        filtered = filtered[filtered[col].isin(val)]
                    elif op == "not in" and isinstance(val, (list, tuple, set)):
                        filtered = filtered[~filtered[col].isin(val)]
                    elif op == "between" and isinstance(val, (list, tuple)) and len(val) == 2:
                        filtered = filtered[(filtered[col] >= val[0]) & (filtered[col] <= val[1])]
                    else:
                        warnings.append(f"Unsupported numeric operator '{op}' for column '{col}'.")
                except Exception as e:
                    warnings.append(f"Failed to apply numeric filter on '{col}': {str(e)}")
                continue

            # Categorical / String handling
            if op in ("==", "=", "eq"):
                # Case-insensitive string match if both are strings
                if isinstance(val, str):
                    filtered = filtered[filtered[col].astype(str).str.lower() == str(val).lower()]
                else:
                    filtered = filtered[filtered[col] == val]
            elif op in ("!=", "neq"):
                if isinstance(val, str):
                    filtered = filtered[filtered[col].astype(str).str.lower() != str(val).lower()]
                else:
                    filtered = filtered[filtered[col] != val]
            elif op == "in" and isinstance(val, (list, tuple, set)):
                val_set = {str(v).lower() for v in val}
                filtered = filtered[filtered[col].astype(str).str.lower().isin(val_set)]
            elif op == "not in" and isinstance(val, (list, tuple, set)):
                val_set = {str(v).lower() for v in val}
                filtered = filtered[~filtered[col].astype(str).str.lower().isin(val_set)]
            elif op == "contains":
                filtered = filtered[filtered[col].astype(str).str.contains(str(val), case=False, na=False)]
            elif op in (">", ">=", "<", "<="):
                # Lexicographical or converted numeric
                try:
                    num_series = pd.to_numeric(filtered[col], errors="coerce")
                    num_val = float(val)
                    if op == ">":
                        filtered = filtered[num_series > num_val]
                    elif op == ">=":
                        filtered = filtered[num_series >= num_val]
                    elif op == "<":
                        filtered = filtered[num_series < num_val]
                    elif op == "<=":
                        filtered = filtered[num_series <= num_val]
                except Exception:
                    warnings.append(f"Comparison '{op}' cannot be applied to non-numeric column '{col}'.")
            else:
                warnings.append(f"Unsupported operator '{op}' for column '{col}'.")

        except Exception as e:
            warnings.append(f"Error applying filter on '{col}': {str(e)}")

    return filtered, warnings
