"""Model Selection Strategy Module.

Ranks model candidate evaluations according to objective validation metrics
(lowest MAE for continuous measures, highest F1 for classification).
"""

from typing import Dict, Any, List, Optional, Tuple
from models.prediction import ProblemType, ModelCandidateResult


class ModelSelector:
    """Applies transparent, non-arbitrary model selection criteria."""

    @classmethod
    def select_best_model(
        cls,
        candidates: List[ModelCandidateResult],
        problem_type: ProblemType,
    ) -> Tuple[ModelCandidateResult, str, str]:
        """Select top model and explain the empirical rationale."""
        successful = [c for c in candidates if c.status == "success"]
        if not successful:
            raise ValueError("No successful candidate models available for selection.")

        if problem_type in [ProblemType.TIME_SERIES_FORECAST, ProblemType.REGRESSION]:
            valid_candidates = [c for c in successful if c.metrics.mae is not None]
            if not valid_candidates:
                raise ValueError("No models produced valid MAE metrics.")

            best = min(valid_candidates, key=lambda c: c.metrics.mae)
            metric_name = "Lowest Validation Mean Absolute Error (MAE)"
            explanation = (
                f"Selected '{best.model_name}' based on {metric_name} ({best.metrics.mae:.4f}) "
                f"across holdout observations. Lower MAE indicates higher average point accuracy."
            )
            return best, metric_name, explanation

        else:
            # Classification
            valid_candidates = [c for c in successful if c.metrics.f1 is not None]
            if not valid_candidates:
                raise ValueError("No models produced valid F1 metrics.")

            best = max(valid_candidates, key=lambda c: c.metrics.f1)
            metric_name = "Highest Validation F1 Score"
            explanation = (
                f"Selected '{best.model_name}' based on {metric_name} ({best.metrics.f1:.4f}) "
                f"across holdout observations, balancing precision and recall across classes."
            )
            return best, metric_name, explanation
