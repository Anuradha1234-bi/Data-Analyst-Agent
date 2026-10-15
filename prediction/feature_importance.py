"""Feature Importance Extraction Module.

Extracts feature influence weights from tree-based ensembles (MDI) and linear
models (|coef|) without fabricating causality or un-grounded claims.
"""

from typing import Dict, Any, List, Optional
import numpy as np
from models.prediction import FeatureImportanceItem


class FeatureImportanceService:
    """Computes normalized feature importance rankings."""

    @classmethod
    def extract_importance(
        cls,
        model: Any,
        feature_names: List[str],
        max_features: int = 10,
    ) -> List[FeatureImportanceItem]:
        """Extract and normalize feature importance weights from trained estimators."""
        if not feature_names or model is None:
            return []

        raw_weights: Optional[np.ndarray] = None

        # 1. Tree ensembles (RandomForest, HistGradientBoosting with inspection)
        if hasattr(model, "feature_importances_"):
            raw_weights = np.asarray(model.feature_importances_, dtype=float)
        # 2. Linear models
        elif hasattr(model, "coef_"):
            coef = np.asarray(model.coef_, dtype=float)
            raw_weights = np.abs(coef).flatten()

        if raw_weights is None or len(raw_weights) != len(feature_names):
            return []

        total_weight = float(np.sum(raw_weights))
        if total_weight < 1e-9:
            return []

        normalized = (raw_weights / total_weight) * 100.0

        items: List[FeatureImportanceItem] = []
        for name, score, pct in zip(feature_names, raw_weights, normalized):
            items.append(
                FeatureImportanceItem(
                    feature=name,
                    importance_score=round(float(score), 4),
                    percentage=round(float(pct), 2),
                )
            )

        items.sort(key=lambda x: x.percentage, reverse=True)
        return items[:max_features]
