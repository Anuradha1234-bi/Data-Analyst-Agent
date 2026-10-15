"""Feature Selection and Safe Filtering Module.

Categorizes candidate predictors into numeric and categorical features while safely
excluding technical identifiers, row numbers, date coordinates, and leaking variables.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from models.prediction import ProblemType
from analysis.anomaly_utils import AnomalyUtils
from prediction.leakage_detector import LeakageDetector


class FeatureSelector:
    """Selects eligible predictive features and provides transparent exclusion audits."""

    @classmethod
    def select_features(
        cls,
        df: pd.DataFrame,
        target_col: str,
        date_col: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        problem_type: ProblemType = ProblemType.REGRESSION,
    ) -> Tuple[List[str], Dict[str, str], List[str], List[str]]:
        """Filter dataset columns into usable features and categorized lists.

        Returns:
            (features_used, features_excluded, numeric_features, categorical_features)
        """
        if df is None or df.empty:
            return [], {}, [], []

        cfg = config or {}
        feat_cfg = cfg.get("features", {})
        exclude_ids = feat_cfg.get("exclude_identifiers", True)
        exclude_idx = feat_cfg.get("exclude_index_columns", True)
        detect_leak = feat_cfg.get("detect_leakage", True)
        user_selected = feat_cfg.get("selected_features")
        user_excluded = set(feat_cfg.get("excluded_features") or [])

        features_used: List[str] = []
        features_excluded: Dict[str, str] = {}
        candidate_cols = [c for c in df.columns if c != target_col and c != date_col]

        # First pass: technical artifact, identifier, and variance filtering
        for col in candidate_cols:
            col_str = str(col)
            if col_str in user_excluded:
                features_excluded[col_str] = "Explicitly excluded by user."
                continue
            if user_selected is not None and col_str not in user_selected:
                features_excluded[col_str] = "Not selected by user."
                continue
            series = df[col]

            # 1. Identifier / Index column exclusion
            is_id, id_reason = AnomalyUtils.is_id_or_index_column(series, col_str)
            if is_id and (exclude_ids or exclude_idx):
                # Do not exclude domain features that happen to be sequential integers
                col_lower = col_str.lower()
                has_semantic = any(kw in col_lower for kw in [
                    "hour", "study", "exp", "score", "age", "attendance", "grade", "level",
                    "year", "month", "day", "rate", "rank", "val", "step", "count", "num"
                ])
                if "sequential integer" in id_reason.lower() and has_semantic:
                    pass  # Retain as valid domain predictor
                else:
                    features_excluded[col_str] = id_reason
                    continue

            # 2. Constant / Zero-variance exclusion
            if series.nunique(dropna=True) <= 1:
                features_excluded[col_str] = "Zero variance (constant column)."
                continue

            # 3. Excessive missingness
            missing_pct = (series.isna().sum() / max(1, len(df))) * 100
            if missing_pct > 80.0:
                features_excluded[col_str] = f"Excessive missing values ({missing_pct:.1f}%)."
                continue

            # 4. Exclude metadata/anomaly tracking columns
            if col_str.startswith("_anomaly_") or col_str.startswith("_metadata_"):
                features_excluded[col_str] = "Internal metadata tracking column."
                continue

            features_used.append(col_str)

        # Second pass: Data leakage check
        if detect_leak and features_used:
            leakage_report = LeakageDetector.detect_leakage(
                df=df,
                target_col=target_col,
                feature_cols=features_used,
                problem_type=problem_type,
            )
            for leak_col, reason in leakage_report.flagged_features.items():
                if leak_col in features_used:
                    features_used.remove(leak_col)
                    features_excluded[leak_col] = f"Potential data leakage: {reason}"

        # Sub-divide into numeric and categorical predictors
        numeric_features: List[str] = []
        categorical_features: List[str] = []

        for col in features_used:
            series = df[col]
            if pd.api.types.is_numeric_dtype(series):
                numeric_features.append(col)
            elif (
                isinstance(series.dtype, pd.CategoricalDtype)
                or pd.api.types.is_object_dtype(series)
                or pd.api.types.is_bool_dtype(series)
            ):
                # Only include categorical if cardinality is manageable (<= 50)
                if series.nunique(dropna=True) <= 50:
                    categorical_features.append(col)
                else:
                    features_used.remove(col)
                    features_excluded[col] = f"High-cardinality categorical ({series.nunique()} unique categories)."

        return features_used, features_excluded, numeric_features, categorical_features
