"""Prediction Explanation and Caveat Synthesis Module.

Produces clear, factual explanations grounded strictly in computed metrics,
feature importances, and validation residuals without inventing external causal narratives.
"""

from typing import Dict, Any, List, Optional, Tuple
from models.prediction import PredictionResult, FeatureImportanceItem, ModelEvaluationMetrics


class ExplanationService:
    """Generates non-speculative explanations and explicit boundary disclaimers."""

    @classmethod
    def generate_explanation(
        cls,
        mode: str,
        target_col: str,
        selected_model: str,
        metrics: ModelEvaluationMetrics,
        feature_importance: List[FeatureImportanceItem],
        forecast_horizon: Optional[int] = None,
        predictions_sample: Optional[List[float]] = None,
        date_col: Optional[str] = None,
    ) -> Tuple[str, List[str]]:
        """Synthesize plain-language summary and standard methodological limitations."""
        lines: List[str] = []
        limitations: List[str] = []

        if mode == "forecasting":
            lines.append(
                f"Trained time-series models on chronological sequence '{date_col}' to forecast target '{target_col}'."
            )
            lines.append(
                f"'{selected_model}' achieved the strongest validation performance with a Mean Absolute Error of {metrics.mae:.2f}."
            )
            if predictions_sample and len(predictions_sample) > 0:
                avg_proj = sum(predictions_sample) / len(predictions_sample)
                min_p = min(predictions_sample)
                max_p = max(predictions_sample)
                lines.append(
                    f"Over the next {forecast_horizon} periods, projected values average {avg_proj:.2f} (ranging from {min_p:.2f} to {max_p:.2f})."
                )

            limitations.append("Time-series projections assume continuation of historical periodicity and trend patterns.")
            limitations.append("Unforeseen market shocks, regime shifts, or external disruptions outside the dataset cannot be anticipated.")
            limitations.append("Prediction intervals widen as the forecast horizon extends into the future.")

        elif mode == "regression":
            lines.append(
                f"Evaluated regression algorithms to predict numeric target '{target_col}' using tabular predictors."
            )
            lines.append(
                f"Selected '{selected_model}' with validation MAE of {metrics.mae:.4f} and R² of {metrics.r2 if metrics.r2 is not None else 0.0:.2f}."
            )
            limitations.append("Regression estimates quantify statistical association, not confirmed physical or causal relationships.")
            limitations.append("Predictions on records with extreme or out-of-distribution feature values carry higher estimation error.")

        else:
            # Classification
            lines.append(
                f"Evaluated classification models to predict categorical target '{target_col}'."
            )
            lines.append(
                f"Selected '{selected_model}' achieving a validation F1-score of {metrics.f1 if metrics.f1 is not None else 0.0:.4f} and accuracy of {metrics.accuracy if metrics.accuracy is not None else 0.0:.1%}."
            )
            limitations.append("Predicted classes represent highest probability assignments given historical patterns.")
            limitations.append("Low representation of minority classes can diminish precision on rare categories.")

        # Influential features commentary
        if feature_importance:
            top_feats = [f"{item.feature} ({item.percentage:.1f}%)" for item in feature_importance[:3]]
            lines.append(f"Top influential model features include: {', '.join(top_feats)}.")

        explanation_text = " ".join(lines)
        return explanation_text, limitations
