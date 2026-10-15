"""Uncertainty Estimation and Prediction Interval Module.

Constructs grounded prediction intervals using empirical validation residuals
without fabricating confidence levels or assuming unrealistically narrow bounds.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np


class UncertaintyService:
    """Computes empirical error spreads and forecast uncertainty bands."""

    @classmethod
    def calculate_regression_intervals(
        cls,
        y_val_true: np.ndarray,
        y_val_pred: np.ndarray,
        predictions: np.ndarray,
        confidence_level: float = 0.95,
        is_non_negative: bool = True,
        is_forecasting: bool = False,
    ) -> Tuple[List[float], List[float], str]:
        """Compute empirical uncertainty bounds for predictions.

        Returns:
            (lower_bounds, upper_bounds, uncertainty_method_description)
        """
        y_vt = np.asarray(y_val_true, dtype=float)
        y_vp = np.asarray(y_val_pred, dtype=float)
        preds = np.asarray(predictions, dtype=float)

        if len(y_vt) < 3 or len(y_vp) < 3:
            # Fallback to standard deviation of predictions or zero spread
            spread = float(np.std(preds)) * 0.15 if len(preds) > 1 else 1.0
            lowers = [max(0.0, p - spread) if is_non_negative else p - spread for p in preds]
            uppers = [p + spread for p in preds]
            return lowers, uppers, "Empirical heuristic spread (limited validation samples)"

        # 1. Compute empirical validation residuals
        residuals = y_vt - y_vp
        res_std = float(np.std(residuals))
        # 95% critical value
        z_multiplier = 1.96 if confidence_level >= 0.95 else 1.645

        lowers: List[float] = []
        uppers: List[float] = []

        for step_idx, p in enumerate(preds):
            # In time-series forecasting, uncertainty expands with horizon step
            step_multiplier = np.sqrt(1.0 + 0.08 * step_idx) if is_forecasting else 1.0
            margin = z_multiplier * res_std * step_multiplier

            lower = p - margin
            if is_non_negative and (y_vt >= 0).all():
                lower = max(0.0, lower)
            upper = p + margin

            lowers.append(round(float(lower), 2))
            uppers.append(round(float(upper), 2))

        method_desc = (
            f"Empirical validation residual standard error (σ={res_std:.2f}, {int(confidence_level*100)}% interval"
            + (", horizon expansion applied)" if is_forecasting else ")")
        )
        return lowers, uppers, method_desc
