"""Anomaly Service - Orchestrates Tabular Anomaly Detection & State Management.

Coordinates detection algorithms, caches dataset-specific results, formats signals,
and safely executes controlled outlier treatments without altering raw data.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd

from tools.anomaly_tool import AnomalyTool
from models.anomaly import (
    IQROutlierColumnResult,
    IQRAnalysisResult,
    IsolationForestResult,
    DeepStatisticalMetric,
    DeepStatisticalResult,
    MultivariateAnomalyRecord,
    MultivariateAnalysisResult,
    AnomalyTreatmentSummary,
    ZScoreAnalysisResult,
    RobustZScoreAnalysisResult,
    CombinedAnomalyResult,
)
from core.session_manager import SessionManager


class AnomalyService:
    """Orchestration service for Phase 4 statistical anomaly & outlier detection."""

    @classmethod
    def get_dataset_features(cls, df: pd.DataFrame) -> Tuple[List[str], List[str], List[str]]:
        """Retrieve suitable numeric features, excluded ID columns, and excluded non-numeric features."""
        return AnomalyTool.identify_suitable_features(df)

    @classmethod
    def run_iqr_detection(
        cls,
        df: pd.DataFrame,
        dataset_name: str,
        columns: Optional[List[str]] = None,
        multiplier: float = 1.5,
        save_to_session: bool = True,
    ) -> IQRAnalysisResult:
        """Execute IQR outlier detection and cache results in session state."""
        result = AnomalyTool.detect_iqr_outliers(
            df=df,
            columns=columns,
            multiplier=multiplier,
            dataset_name=dataset_name,
        )

        if save_to_session:
            curr = SessionManager.get_anomaly_results(dataset_name) or {}
            curr["iqr"] = result
            curr["last_method"] = "iqr"
            SessionManager.set_anomaly_results(curr, dataset_name)

        return result

    @classmethod
    def run_isolation_forest(
        cls,
        df: pd.DataFrame,
        dataset_name: str,
        columns: Optional[List[str]] = None,
        contamination: Union[float, str] = 0.05,
        random_state: int = 42,
        save_to_session: bool = True,
    ) -> IsolationForestResult:
        """Execute Isolation Forest detection and cache results in session state."""
        result = AnomalyTool.detect_isolation_forest(
            df=df,
            columns=columns,
            contamination=contamination,
            random_state=random_state,
            dataset_name=dataset_name,
        )

        if save_to_session:
            curr = SessionManager.get_anomaly_results(dataset_name) or {}
            curr["isolation_forest"] = result
            curr["last_method"] = "isolation_forest"
            SessionManager.set_anomaly_results(curr, dataset_name)

        return result

    @classmethod
    def run_deep_statistics(
        cls,
        df: pd.DataFrame,
        dataset_name: str,
        columns: Optional[List[str]] = None,
        save_to_session: bool = True,
    ) -> DeepStatisticalResult:
        """Compute deep statistical properties and signal flags for numerical features."""
        result = AnomalyTool.compute_deep_statistics(
            df=df,
            columns=columns,
            dataset_name=dataset_name,
        )

        if save_to_session:
            curr = SessionManager.get_anomaly_results(dataset_name) or {}
            curr["deep_statistics"] = result
            curr["last_method"] = "deep_statistics"
            SessionManager.set_anomaly_results(curr, dataset_name)

        return result

    @classmethod
    def run_multivariate_detection(
        cls,
        df: pd.DataFrame,
        dataset_name: str,
        columns: Optional[List[str]] = None,
        contamination: Union[float, str] = 0.05,
        random_state: int = 42,
        save_to_session: bool = True,
    ) -> MultivariateAnalysisResult:
        """Execute multivariate outlier detection and signal attribution."""
        result = AnomalyTool.compute_multivariate_anomalies(
            df=df,
            columns=columns,
            contamination=contamination,
            random_state=random_state,
            dataset_name=dataset_name,
        )

        if save_to_session:
            curr = SessionManager.get_anomaly_results(dataset_name) or {}
            curr["multivariate"] = result
            curr["last_method"] = "multivariate"
            SessionManager.set_anomaly_results(curr, dataset_name)

        return result

    @classmethod
    def run_zscore_detection(
        cls,
        df: pd.DataFrame,
        dataset_name: str,
        columns: Optional[List[str]] = None,
        threshold: float = 3.0,
        save_to_session: bool = True,
    ) -> ZScoreAnalysisResult:
        """Execute Z-score anomaly detection and cache results in session state."""
        from analysis.anomaly_detection import detect_zscore_anomalies
        result = detect_zscore_anomalies(
            df=df,
            columns=columns,
            threshold=threshold,
            dataset_name=dataset_name,
        )
        if save_to_session:
            curr = SessionManager.get_anomaly_results(dataset_name) or {}
            curr["z_score"] = result
            curr["last_method"] = "z_score"
            SessionManager.set_anomaly_results(curr, dataset_name)
        return result

    @classmethod
    def run_robust_zscore_detection(
        cls,
        df: pd.DataFrame,
        dataset_name: str,
        columns: Optional[List[str]] = None,
        threshold: float = 3.5,
        save_to_session: bool = True,
    ) -> RobustZScoreAnalysisResult:
        """Execute Robust Z-score (MAD) anomaly detection and cache results."""
        from analysis.anomaly_detection import detect_robust_zscore_anomalies
        result = detect_robust_zscore_anomalies(
            df=df,
            columns=columns,
            threshold=threshold,
            dataset_name=dataset_name,
        )
        if save_to_session:
            curr = SessionManager.get_anomaly_results(dataset_name) or {}
            curr["robust_z_score"] = result
            curr["last_method"] = "robust_z_score"
            SessionManager.set_anomaly_results(curr, dataset_name)
        return result

    @classmethod
    def run_orchestrated_detection(
        cls,
        df: pd.DataFrame,
        dataset_name: str,
        methods: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
        save_to_session: bool = True,
    ) -> Dict[str, Any]:
        """Execute full multi-method detection pipeline and store combined results in session state."""
        from analysis.anomaly_detection import run_anomaly_detection
        res_dict = run_anomaly_detection(
            df=df,
            dataset_name=dataset_name,
            methods=methods,
            columns=columns,
            config=config,
        )
        if save_to_session:
            curr = SessionManager.get_anomaly_results(dataset_name) or {}
            for m_key, m_res in res_dict.get("method_results", {}).items():
                curr[m_key] = m_res
            curr["combined"] = res_dict.get("combined_results")
            curr["orchestrated"] = res_dict
            curr["last_method"] = "combined"
            SessionManager.set_anomaly_results(curr, dataset_name)

            # Also register anomaly-flagged dataset view
            combined_obj = res_dict.get("combined_results")
            if combined_obj and hasattr(combined_obj, "all_anomaly_indices"):
                from analysis.anomaly_treatment import apply_anomaly_treatment
                flagged_df, _ = apply_anomaly_treatment(
                    df=df,
                    anomaly_result=combined_obj,
                    treatment_config={"action": "flag_only"},
                    dataset_name=dataset_name,
                )
                SessionManager.set_anomaly_dataset(flagged_df, dataset_name)

        return res_dict

    @classmethod
    def apply_controlled_treatment(
        cls,
        dataset_name: str,
        treatment_type: str,
        outlier_indices: List[Any],
        columns: Optional[List[str]] = None,
        iqr_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> Tuple[pd.DataFrame, AnomalyTreatmentSummary]:
        """Apply user-confirmed treatment to active dataset and update cleaned dataset in SessionManager."""
        # Treatment always acts on the current active/cleaned dataset or original
        active_df = SessionManager.get_dataset_by_name(dataset_name, view="active")
        if active_df is None:
            active_df = SessionManager.get_original_df(dataset_name)

        if active_df is None:
            raise ValueError(f"Dataset '{dataset_name}' not found in active session.")

        treated_df, summary = AnomalyTool.apply_treatment(
            df=active_df,
            treatment_type=treatment_type,
            outlier_indices=outlier_indices,
            columns=columns,
            iqr_bounds=iqr_bounds,
            dataset_name=dataset_name,
        )

        # Register treated dataset in SessionManager
        SessionManager.set_treated_dataset(treated_df, dataset_name)
        if treatment_type == "flag_only":
            SessionManager.set_anomaly_dataset(treated_df, dataset_name)

        # Sync cleaned dataset
        SessionManager.set_cleaned_dataset(
            df=treated_df,
            summary=summary,
            filename=dataset_name,
        )
        SessionManager.add_anomaly_treatment_audit(summary)

        # Clear cached anomaly results for this dataset so user can re-analyze the treated data
        curr = SessionManager.get_anomaly_results(dataset_name) or {}
        curr["last_treatment"] = summary
        SessionManager.set_anomaly_results(curr, dataset_name)

        return treated_df, summary

