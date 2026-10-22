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
        n_pairs = int(valid_mask.sum())
        total_rows = len(df)
        missing_pairs = total_rows - n_pairs

        if n_pairs < 3:
            return {
                "result_type": "empty",
                "data": pd.DataFrame(),
                "columns": [],
                "row_count": 0,
                "evidence": {
                    "message": f"Insufficient non-null observations between '{col_a}' and '{col_b}' (N={n_pairs}, minimum 3 required).",
                    "valid_pairs": n_pairs,
                    "total_rows": total_rows,
                },
                "warnings": [f"Not enough valid numerical pairs between '{col_a}' and '{col_b}'."],
            }

        val_a = s_a[valid_mask]
        val_b = s_b[valid_mask]
        std_a = float(val_a.std(ddof=1)) if n_pairs > 1 else 0.0
        std_b = float(val_b.std(ddof=1)) if n_pairs > 1 else 0.0

        alpha = 0.05

        if std_a == 0.0 or std_b == 0.0:
            zero_var_cols = []
            if std_a == 0.0: zero_var_cols.append(col_a)
            if std_b == 0.0: zero_var_cols.append(col_b)
            warn_msg = f"Standard deviation is 0.0 for column(s) {zero_var_cols} (constant values). Correlation is undefined."
            summary_row = {
                "Analysis Type": "Pearson & Spearman",
                "Feature A": col_a,
                "Feature B": col_b,
                "Coefficient": 0.0,
                "P-Value": "N/A",
                "Statistically Significant (α=0.05)": "Undefined (Zero Variance)",
                "Strength": "None",
                "Direction": "None",
                "Valid Pairs (N)": n_pairs,
                "Relationship Evaluated": warn_msg,
            }
            res_df = pd.DataFrame([summary_row])
            return {
                "result_type": "table",
                "data": res_df,
                "columns": list(res_df.columns),
                "row_count": 1,
                "evidence": {
                    "col_a": col_a,
                    "col_b": col_b,
                    "valid_pairs_n": n_pairs,
                    "total_rows": total_rows,
                    "missing_pairs": missing_pairs,
                    "zero_variance_columns": zero_var_cols,
                    "causation_warning": "Correlation does NOT establish causation. Associations reflect statistical covariance, not cause-and-effect.",
                },
                "warnings": [warn_msg],
            }

        # Calculate Pearson and Spearman using scipy.stats
        try:
            import scipy.stats as stats
            p_res = stats.pearsonr(val_a, val_b)
            r_val = float(p_res.statistic if hasattr(p_res, "statistic") else p_res[0])
            p_pearson = float(p_res.pvalue if hasattr(p_res, "pvalue") else p_res[1])

            s_res = stats.spearmanr(val_a, val_b)
            rho_val = float(s_res.statistic if hasattr(s_res, "statistic") else s_res[0])
            p_spearman = float(s_res.pvalue if hasattr(s_res, "pvalue") else s_res[1])
        except Exception:
            r_val = float(val_a.corr(val_b, method="pearson"))
            rho_val = float(val_a.corr(val_b, method="spearman"))
            p_pearson = 0.0
            p_spearman = 0.0

        if np.isnan(r_val): r_val = 0.0
        if np.isnan(rho_val): rho_val = 0.0

        sig_pearson = bool(p_pearson < alpha)
        sig_spearman = bool(p_spearman < alpha)

        def _get_strength(coeff: float) -> str:
            abs_c = abs(coeff)
            if abs_c >= 0.70: return "Strong"
            if abs_c >= 0.40: return "Moderate"
            if abs_c >= 0.20: return "Weak"
            return "Negligible"

        rows = [
            {
                "Analysis Type": "Pearson Correlation",
                "Feature A": col_a,
                "Feature B": col_b,
                "Coefficient": round(r_val, 4),
                "P-Value": round(p_pearson, 4) if p_pearson >= 0.0001 else "< 0.0001",
                "Statistically Significant (α=0.05)": "Yes" if sig_pearson else "No",
                "Strength": _get_strength(r_val),
                "Direction": "Positive" if r_val > 0 else ("Negative" if r_val < 0 else "None"),
                "Valid Pairs (N)": n_pairs,
                "Relationship Evaluated": "Linear association",
            },
            {
                "Analysis Type": "Spearman Rank Correlation",
                "Feature A": col_a,
                "Feature B": col_b,
                "Coefficient": round(rho_val, 4),
                "P-Value": round(p_spearman, 4) if p_spearman >= 0.0001 else "< 0.0001",
                "Statistically Significant (α=0.05)": "Yes" if sig_spearman else "No",
                "Strength": _get_strength(rho_val),
                "Direction": "Positive" if rho_val > 0 else ("Negative" if rho_val < 0 else "None"),
                "Valid Pairs (N)": n_pairs,
                "Relationship Evaluated": "Monotonic association",
            },
        ]
        res_df = pd.DataFrame(rows)

        causation_text = (
            "Correlation does NOT establish causation. A statistically significant correlation indicates an association "
            "between the two variables, but does not prove that changes in one variable cause changes in the other. "
            "Confounding factors, common underlying drivers, or coincidence may account for the relationship. "
            "Furthermore, statistical significance (p < 0.05) demonstrates that the observed correlation is unlikely to be "
            "a random artifact of sampling variation, but does not automatically imply practical or operational importance."
        )

        evidence = {
            "col_a": col_a,
            "col_b": col_b,
            "pearson_r": round(r_val, 4),
            "pearson_p_value": float(p_pearson),
            "pearson_significant": sig_pearson,
            "spearman_rho": round(rho_val, 4),
            "spearman_p_value": float(p_spearman),
            "spearman_significant": sig_spearman,
            "valid_pairs_n": n_pairs,
            "total_rows": total_rows,
            "missing_pairs": missing_pairs,
            "significance_threshold_alpha": alpha,
            "mean_a": round(float(val_a.mean()), 2),
            "std_a": round(std_a, 2),
            "mean_b": round(float(val_b.mean()), 2),
            "std_b": round(std_b, 2),
            "pairs_analyzed": 1,
            "strongest_pair": rows[0],
            "causation_warning": causation_text,
            "summary_table": rows,
        }

        return {
            "result_type": "table",
            "data": res_df,
            "columns": list(res_df.columns),
            "row_count": len(res_df),
            "evidence": evidence,
            "warnings": [],
        }

    if col_a and not col_b:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {
                "message": f"Requested correlation for '{col_a}', but could not resolve a second numerical column. Please specify a second numeric column."
            },
            "warnings": [f"Secondary column for correlation analysis with '{col_a}' is missing."],
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
