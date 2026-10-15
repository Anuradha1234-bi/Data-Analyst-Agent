"""Data Leakage Detection Module.

Identifies features that leak target information, future outcomes, or duplicate
definitions into training data, protecting model generalization and empirical validity.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from models.prediction import LeakageReport, ProblemType


POST_OUTCOME_INDICATORS = [
    "return_date", "cancelled_date", "exit_date", "churn_date", "reason",
    "refund", "resolution", "payout", "post_", "outcome_", "future_"
]


class LeakageDetector:
    """Audits feature candidates to intercept ground-truth leakage and target-derived artifacts."""

    @classmethod
    def detect_leakage(
        cls,
        df: pd.DataFrame,
        target_col: str,
        feature_cols: List[str],
        problem_type: ProblemType,
    ) -> LeakageReport:
        """Scan candidate features against target for circular or post-outcome leakage."""
        flagged: Dict[str, str] = {}
        recommendations: List[str] = []

        if df is None or df.empty or target_col not in df.columns or not feature_cols:
            return LeakageReport(has_leakage=False, flagged_features={}, recommendations=[])

        target_series = df[target_col]
        target_name_lower = target_col.lower()
        is_target_num = pd.api.types.is_numeric_dtype(target_series)

        for col in feature_cols:
            if col == target_col:
                continue

            col_lower = str(col).lower()
            feat_series = df[col]

            # 1. Exact Duplicate / Near Duplicate
            if feat_series.equals(target_series):
                flagged[col] = f"Exact duplicate of target '{target_col}' (100% identical values)."
                continue

            # 2. Perfect or Near-Perfect Correlation for Numeric Features
            if is_target_num and pd.api.types.is_numeric_dtype(feat_series):
                valid_mask = target_series.notna() & feat_series.notna()
                if valid_mask.sum() > 5:
                    std_t = target_series[valid_mask].std()
                    std_f = feat_series[valid_mask].std()
                    if std_t > 1e-9 and std_f > 1e-9:
                        corr = abs(float(np.corrcoef(target_series[valid_mask], feat_series[valid_mask])[0, 1]))
                        if corr >= 0.999:
                            flagged[col] = f"Extreme correlation ({corr:.4f}) with target. Highly likely a direct derivation or duplicate."
                            continue

            # 3. Target Name Variation / Derived Feature Name
            if (target_name_lower in col_lower and col_lower != target_name_lower) or (col_lower in target_name_lower):
                # E.g. "sales_copy", "total_sales", "target_pct"
                if any(suffix in col_lower for suffix in ["_copy", "_dup", "_orig", "_raw", "_scaled", "_log", "_next"]):
                    flagged[col] = f"Column name suggests direct derivation from target '{target_col}'."
                    continue

            # 4. Post-Outcome / Future Event Flags
            for ind in POST_OUTCOME_INDICATORS:
                if ind in col_lower and ind not in target_name_lower:
                    flagged[col] = f"Column name contains post-outcome indicator '{ind}'. Represents information unavailable at prediction time."
                    break

        has_leakage = len(flagged) > 0
        if has_leakage:
            recommendations.append(f"Excluded {len(flagged)} potentially leaking feature(s) from candidate predictors.")
            recommendations.append("Inspect flagged columns to verify whether they represent retrospective business logs.")

        return LeakageReport(
            has_leakage=has_leakage,
            flagged_features=flagged,
            recommendations=recommendations,
        )
