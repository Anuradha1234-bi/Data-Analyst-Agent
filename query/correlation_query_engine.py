"""Correlation Query Engine for Phase 6 Natural Language Query Engine.

Computes pairwise correlations and identifies strong linear associations.
Reuses Phase 5 correlation results if available.
Always clarifies that correlation does NOT imply causation.
Metadata-aware: excludes technical extraction metadata from automatic pairs,
while honoring explicit user requests.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from query.column_resolver import is_metadata_column, filter_metadata_columns


def compute_correlation_query(
    df: pd.DataFrame,
    col_a: Optional[str] = None,
    col_b: Optional[str] = None,
    threshold: float = 0.5,
    phase5_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calculate and filter correlation relationships across numeric columns."""
    if df is None or df.empty:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": ["DataFrame is empty."],
        }

    # CASE 1: Both col_a and col_b explicitly requested by user
    if col_a and col_b:
        missing_explicit = [c for c in (col_a, col_b) if c not in df.columns]
        if missing_explicit:
            return {
                "result_type": "empty",
                "data": pd.DataFrame(),
                "columns": [],
                "row_count": 0,
                "evidence": {"message": f"Requested column(s) {missing_explicit} not found in dataset."},
                "warnings": [f"Columns {missing_explicit} do not exist in dataset."],
            }

        s_a = pd.to_numeric(df[col_a], errors="coerce")
        s_b = pd.to_numeric(df[col_b], errors="coerce")
        valid_mask = s_a.notna() & s_b.notna()
        if valid_mask.sum() < 3:
            return {
                "result_type": "empty",
                "data": pd.DataFrame(),
                "columns": [],
                "row_count": 0,
                "evidence": {"message": f"Insufficient non-null observations between '{col_a}' and '{col_b}' (minimum 3 required)."},
                "warnings": [f"Not enough valid numerical pairs between '{col_a}' and '{col_b}'."],
            }

        r_val = float(s_a[valid_mask].corr(s_b[valid_mask], method="pearson"))
        if np.isnan(r_val):
            r_val = 0.0

        abs_r = abs(r_val)
        strength = "Strong" if abs_r >= 0.70 else ("Moderate" if abs_r >= 0.40 else "Weak")
        direction = "Positive" if r_val > 0 else "Negative"

        pair_row = {
            "Feature A": col_a,
            "Feature B": col_b,
            "Correlation (r)": round(r_val, 4),
            "Strength": strength,
            "Direction": direction,
        }
        res_df = pd.DataFrame([pair_row])
        evidence = {
            "pairs_analyzed": 1,
            "strongest_pair": pair_row,
            "causation_warning": "Correlation does NOT imply causation. Associations reflect statistical covariance, not cause-and-effect.",
        }
        return {
            "result_type": "table",
            "data": res_df,
            "columns": list(res_df.columns),
            "row_count": 1,
            "evidence": evidence,
            "warnings": [],
        }

    # Numeric columns in dataset
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    # Exclude technical/extraction metadata from automatic pairwise correlations
    domain_num_cols = filter_metadata_columns(num_cols)
    meta_cols = [c for c in num_cols if is_metadata_column(c)]

    if len(domain_num_cols) < 2:
        if meta_cols:
            return {
                "result_type": "empty",
                "data": pd.DataFrame(),
                "columns": [],
                "row_count": 0,
                "evidence": {
                    "message": f"Dataset contains extraction metadata columns ({', '.join(meta_cols)}) but lacks domain numerical variables required for correlation analysis.",
                    "available_columns": list(df.columns),
                    "metadata_columns": meta_cols,
                },
                "warnings": [f"Dataset contains extraction metadata columns ({', '.join(meta_cols)}) but lacks domain numerical variables required for correlation analysis."],
            }
        else:
            return {
                "result_type": "empty",
                "data": pd.DataFrame(),
                "columns": [],
                "row_count": 0,
                "evidence": {"message": "At least two numeric columns required for correlation analysis."},
                "warnings": ["Insufficient numeric columns for correlation analysis."],
            }

    # Re-use Phase 5 correlation results if available and clean
    if phase5_results and not col_a and not col_b:
        corr_res = phase5_results.get("correlations")
        if isinstance(corr_res, dict) and "relationships" in corr_res:
            rels = corr_res["relationships"]
            clean_rels = [
                r for r in rels
                if not is_metadata_column(r.get("Feature A", r.get("col_a", "")))
                and not is_metadata_column(r.get("Feature B", r.get("col_b", "")))
            ]
            if clean_rels:
                res_df = pd.DataFrame(clean_rels)
                evidence = {
                    "strongest_pair": clean_rels[0],
                    "relationships_count": len(clean_rels),
                    "causation_warning": "Correlation does NOT imply causation. Relationships reflect statistical association only.",
                }
                return {
                    "result_type": "table",
                    "data": res_df,
                    "columns": list(res_df.columns),
                    "row_count": len(res_df),
                    "evidence": evidence,
                    "warnings": [],
                }

    # Direct calculation on domain numeric columns
    corr_matrix = df[domain_num_cols].corr(method="pearson")

    # Pairwise list
    pairs: List[Dict[str, Any]] = []

    for i, c1 in enumerate(domain_num_cols):
        for j, c2 in enumerate(domain_num_cols):
            if i < j:
                if col_a and col_a not in (c1, c2):
                    continue
                val = corr_matrix.loc[c1, c2]
                if not pd.isna(val):
                    r_val = float(val)
                    abs_r = abs(r_val)
                    if abs_r >= 0.70:
                        strength = "Strong"
                    elif abs_r >= 0.40:
                        strength = "Moderate"
                    else:
                        strength = "Weak"

                    direction = "Positive" if r_val > 0 else "Negative"

                    pairs.append({
                        "Feature A": c1,
                        "Feature B": c2,
                        "Correlation (r)": round(r_val, 4),
                        "Strength": strength,
                        "Direction": direction,
                    })

    pairs.sort(key=lambda x: abs(x["Correlation (r)"]), reverse=True)
    res_df = pd.DataFrame(pairs)

    evidence = {
        "pairs_analyzed": len(pairs),
        "strongest_pair": pairs[0] if pairs else {},
        "causation_warning": "Correlation does NOT imply causation. Associations reflect statistical covariance, not cause-and-effect.",
    }

    return {
        "result_type": "table",
        "data": res_df,
        "columns": list(res_df.columns),
        "row_count": len(res_df),
        "evidence": evidence,
        "warnings": [],
    }
