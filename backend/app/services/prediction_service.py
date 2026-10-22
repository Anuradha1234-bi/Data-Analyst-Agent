"""Prediction Service - Orchestrates machine learning, forecasting, and diagnostics."""

import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logger import logger
from app.models.dataset import Dataset
from app.models.prediction_run import PredictionRun
from app.models.user import User
from app.schemas.prediction import (
    AnalyzeDatasetRequest,
    AnalyzeDatasetResponse,
    ColumnSummaryItem,
    DateCandidateResponse,
    DatasetSuitabilityResponse,
    ModelCandidateMetricItem,
    PredictionPointItem,
    PredictionRunDetailResponse,
    PredictionRunSummaryResponse,
    PredictionTrainRequest,
    PredictNewDataResponse,
    TargetCandidateResponse,
    FeatureImportanceResponseItem,
)
from models.prediction import ProblemType
from prediction.feature_importance import FeatureImportanceService
from prediction.feature_selector import FeatureSelector
from prediction.forecasting import ForecastingEngine
from prediction.leakage_detector import LeakageDetector
from prediction.model_registry import ModelRegistry
from prediction.problem_detector import ProblemDetector
from prediction.regression import RegressionEngine
from prediction.classification import ClassificationEngine
from prediction.target_detector import TargetDetector
from prediction.time_series import TimeSeriesService
from prediction.uncertainty import UncertaintyService
from prediction.explanation import ExplanationService
from utils.file_loader import FileLoader


class PredictionService:
    """Enterprise service managing end-to-end predictive modeling workflows."""

    @classmethod
    def get_candidate_models_catalog(cls) -> List[Dict[str, Any]]:
        """Return all supported predictive models and metadata."""
        catalog = []
        for model_id, meta in ModelRegistry.MODELS_METADATA.items():
            entry = dict(meta)
            entry["id"] = model_id
            entry["supported_problems"] = [
                p.value if hasattr(p, "value") else str(p) for p in meta.get("supported_problems", [])
            ]
            catalog.append(entry)
        return catalog

    @classmethod
    def _get_user_dataset_df(cls, db: Session, user: User, dataset_id: int) -> Tuple[Dataset, pd.DataFrame]:
        """Fetch dataset record ensuring user ownership and load physical DataFrame."""
        dataset = (
            db.query(Dataset)
            .filter(Dataset.id == dataset_id, Dataset.user_id == user.id)
            .first()
        )
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset with ID {dataset_id} not found or you do not have permission to access it.",
            )

        active_path = dataset.cleaned_file_path if (dataset.has_cleaned and dataset.cleaned_file_path) else dataset.file_path
        if not active_path or not Path(active_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset physical storage file '{dataset.filename}' was not found on disk.",
            )

        load_res = FileLoader.load_file(active_path, dataset.filename, dataset.file_size_bytes or 0)
        if not load_res.success or load_res.df is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to load dataset: {load_res.error_message or 'Unknown parsing error.'}",
            )

        if load_res.df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected dataset is empty (0 rows). Machine learning requires at least several observations.",
            )

        return dataset, load_res.df

    @classmethod
    def analyze_dataset(
        cls,
        db: Session,
        user: User,
        request: AnalyzeDatasetRequest,
    ) -> AnalyzeDatasetResponse:
        """Inspect dataset for target viability, date columns, leakage risk, and suitability."""
        dataset, df = cls._get_user_dataset_df(db, user, request.dataset_id)

        target_candidates_raw = TargetDetector.detect_targets(df)
        target_candidates: List[TargetCandidateResponse] = [
            TargetCandidateResponse(
                column=tc.column,
                problem_type=tc.problem_type.value if hasattr(tc.problem_type, "value") else str(tc.problem_type),
                score=round(float(tc.score), 2),
                reasons=tc.reasons,
                missing_pct=round(float(tc.missing_pct), 2),
                unique_count=int(tc.unique_count),
            )
            for tc in target_candidates_raw
        ]

        date_candidates_raw = TargetDetector.detect_date_columns(df)
        date_candidates: List[DateCandidateResponse] = [
            DateCandidateResponse(
                column=dc.column,
                frequency=dc.frequency,
                min_date=dc.min_date,
                max_date=dc.max_date,
                valid_count=dc.valid_count,
                is_regular=dc.is_regular,
                sample_values=[str(v) for v in dc.sample_values[:3]],
            )
            for dc in date_candidates_raw
        ]

        # Resolve selected target and date
        resolved_target = request.target_column
        if not resolved_target and target_candidates:
            resolved_target = target_candidates[0].column

        resolved_date = request.date_column
        if not resolved_date and date_candidates:
            resolved_date = date_candidates[0].column

        # Detect problem type
        problem_type = ProblemDetector.detect_problem_type(
            df=df,
            target_col=resolved_target,
            date_col=resolved_date,
            requested_mode=request.mode or "auto",
        )

        suitability = ProblemDetector.check_dataset_suitability(
            df=df,
            target_col=resolved_target,
            problem_type=problem_type,
            date_col=resolved_date,
        )

        # Audit feature columns for data leakage
        candidate_feature_cols = [c for c in df.columns if c != resolved_target and c != resolved_date]
        leakage_report = LeakageDetector.detect_leakage(
            df=df,
            target_col=resolved_target or "",
            feature_cols=candidate_feature_cols,
            problem_type=problem_type,
        )

        # Build column profile items
        columns_summary: List[ColumnSummaryItem] = []
        for col in df.columns:
            series = df[col]
            missing_count = int(series.isna().sum())
            missing_pct = round((missing_count / max(1, len(df))) * 100.0, 2)
            unique_count = int(series.nunique(dropna=True))

            # Role detection
            if col == resolved_target:
                role = "target"
            elif col == resolved_date:
                role = "datetime"
            elif unique_count <= 1:
                role = "constant"
            elif pd.api.types.is_numeric_dtype(series):
                role = "numeric"
            elif (
                pd.api.types.is_datetime64_any_dtype(series)
                or "date" in str(col).lower()
                or "time" in str(col).lower()
            ):
                role = "datetime"
            else:
                role = "categorical"

            # Clean sample values
            raw_samples = series.dropna().head(3).tolist()
            clean_samples = [
                round(float(s), 4) if isinstance(s, (float, np.floating)) else str(s)
                for s in raw_samples
            ]

            leak_risk = leakage_report.flagged_features.get(str(col))

            columns_summary.append(
                ColumnSummaryItem(
                    name=str(col),
                    data_type=str(series.dtype),
                    role=role,
                    unique_count=unique_count,
                    missing_count=missing_count,
                    missing_pct=missing_pct,
                    sample_values=clean_samples,
                    leakage_risk=leak_risk,
                )
            )

        suitability_resp = DatasetSuitabilityResponse(
            is_suitable=suitability.is_suitable,
            problem_type=problem_type.value if hasattr(problem_type, "value") else str(problem_type),
            target_column=resolved_target,
            date_column=resolved_date,
            total_rows=suitability.total_rows,
            usable_rows=suitability.usable_rows,
            features_count=suitability.features_count,
            reasons=suitability.reasons,
            warnings=suitability.warnings,
            has_leakage=leakage_report.has_leakage,
            flagged_leakage_features=leakage_report.flagged_features,
        )

        return AnalyzeDatasetResponse(
            dataset_id=dataset.id,
            dataset_name=dataset.filename,
            total_rows=int(len(df)),
            total_columns=int(len(df.columns)),
            target_candidates=target_candidates,
            date_candidates=date_candidates,
            recommended_target=resolved_target,
            recommended_date_column=resolved_date,
            recommended_problem_type=problem_type.value if hasattr(problem_type, "value") else str(problem_type),
            columns_summary=columns_summary,
            suitability=suitability_resp,
        )

    @classmethod
    def train_model(
        cls,
        db: Session,
        user: User,
        request: PredictionTrainRequest,
    ) -> PredictionRunDetailResponse:
        """Train models on held-out/chronological validation partitions and persist versioned run."""
        dataset, df = cls._get_user_dataset_df(db, user, request.dataset_id)
        df_work = df.copy()

        # Handle user anomaly exclusion choice
        if request.exclude_anomalies:
            if "_anomaly_flag" in df_work.columns:
                df_work = df_work[df_work["_anomaly_flag"] != True].reset_index(drop=True)

        target_col = request.target_column
        if not target_col or target_col not in df_work.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target column '{target_col}' is invalid or not found in dataset.",
            )

        date_col = request.date_column
        if date_col and date_col not in df_work.columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Date column '{date_col}' is not present in dataset.",
            )

        # Detect problem type
        problem_type = ProblemDetector.detect_problem_type(
            df=df_work,
            target_col=target_col,
            date_col=date_col,
            requested_mode=request.mode or "auto",
        )

        # Suitability diagnostic check
        suitability = ProblemDetector.check_dataset_suitability(
            df=df_work,
            target_col=target_col,
            problem_type=problem_type,
            date_col=date_col,
        )
        if not suitability.is_suitable:
            reasons_msg = "; ".join(suitability.reasons)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dataset is not suitable for {problem_type.value}: {reasons_msg}",
            )

        # Feature selection & Leakage exclusion
        feat_config = {
            "features": {
                "selected_features": request.selected_features,
                "excluded_features": request.excluded_features,
                "detect_leakage": True,
            }
        }
        features_used, features_excluded, num_feats, cat_feats = FeatureSelector.select_features(
            df=df_work,
            target_col=target_col,
            date_col=date_col,
            config=feat_config,
            problem_type=problem_type,
        )

        if not features_used and problem_type != ProblemType.TIME_SERIES_FORECAST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No eligible predictor features available after excluding identifiers, constant columns, and leakage risks.",
            )

        test_size = float(request.test_size or 0.20)
        candidate_model_id = request.candidate_model

        # Branch by problem type
        task_str = "regression"
        selection_metric = "Lowest Validation MAE"
        prediction_points: List[PredictionPointItem] = []
        feature_importance_items: List[FeatureImportanceResponseItem] = []
        candidate_metrics_list: List[ModelCandidateMetricItem] = []
        pipeline_artifact: Dict[str, Any] = {}
        best_candidate_name = "Model"
        best_metrics_dict: Dict[str, Any] = {}
        explanation_text = ""
        limitations: List[str] = list(suitability.warnings)
        uncert_desc = "None"
        train_rows = 0
        validation_rows = 0
        forecast_horizon_val: Optional[int] = None

        try:
            if problem_type == ProblemType.TIME_SERIES_FORECAST:
                task_str = "time_series"
                selection_metric = "Lowest Validation MAE"
                forecast_horizon_val = request.forecast_horizon

                candidates, best_id, future_preds, y_val_t, y_val_p, future_dates, best_est = (
                    ForecastingEngine.train_and_forecast(
                        df=df_work,
                        date_col=date_col,
                        target_col=target_col,
                        horizon=request.forecast_horizon,
                        test_size=test_size,
                        preferred_model_id=candidate_model_id,
                    )
                )

                train_rows = len(df_work) - len(y_val_t)
                validation_rows = len(y_val_t)

                lowers, uppers, uncert_desc = UncertaintyService.calculate_regression_intervals(
                    y_val_true=y_val_t,
                    y_val_pred=y_val_p,
                    predictions=np.array(future_preds),
                    confidence_level=0.95,
                    is_non_negative=True,
                    is_forecasting=True,
                )

                prediction_points = [
                    PredictionPointItem(
                        index_or_date=str(d),
                        predicted_value=round(float(v), 4),
                        lower_bound=round(float(l), 4) if l is not None else None,
                        upper_bound=round(float(u), 4) if u is not None else None,
                    )
                    for d, v, l, u in zip(future_dates, future_preds, lowers, uppers)
                ]

                # Extract TS importance
                if best_est is not None:
                    _, ts_feats, _, _ = TimeSeriesService.prepare_time_series_features(df_work, date_col, target_col)
                    raw_imp = FeatureImportanceService.extract_importance(best_est, ts_feats, max_features=8)
                    feature_importance_items = [
                        FeatureImportanceResponseItem(
                            feature=fi.feature,
                            importance_score=round(float(fi.importance_score), 4),
                            percentage=round(float(fi.percentage), 2),
                        )
                        for fi in raw_imp
                    ]

                best_cand = next(c for c in candidates if c.model_id == best_id)
                best_candidate_name = best_cand.model_name
                best_metrics_dict = best_cand.metrics.to_dict()

                candidate_metrics_list = [
                    ModelCandidateMetricItem(
                        model_id=c.model_id,
                        model_name=c.model_name,
                        problem_type=task_str,
                        metrics=c.metrics.to_dict(),
                        training_time_seconds=round(float(c.training_time_seconds), 4),
                        status=c.status,
                        warning=c.warning,
                        error=c.error,
                        is_best=(c.model_id == best_id),
                    )
                    for c in candidates
                ]

                explanation_text, lims = ExplanationService.generate_explanation(
                    mode="forecasting",
                    target_col=target_col,
                    selected_model=best_candidate_name,
                    metrics=best_cand.metrics,
                    feature_importance=[
                        type("FI", (), {"feature": f.feature, "percentage": f.percentage})
                        for f in feature_importance_items
                    ],
                    forecast_horizon=request.forecast_horizon,
                    predictions_sample=future_preds,
                    date_col=date_col,
                )
                limitations.extend(lims)

                pipeline_artifact = {
                    "task_type": "forecasting",
                    "model_id": best_id,
                    "model_name": best_candidate_name,
                    "target_column": target_col,
                    "date_column": date_col,
                    "features_used": features_used or ["historical_lags", "rolling_windows", "calendar_trend"],
                    "model": best_est,
                }

            elif problem_type == ProblemType.REGRESSION:
                task_str = "regression"
                selection_metric = "Lowest Validation MAE"

                candidates, best_id, best_preds, y_val, best_est, feat_names, preprocessor = (
                    RegressionEngine.train_and_evaluate(
                        df=df_work,
                        target_col=target_col,
                        numeric_features=num_feats,
                        categorical_features=cat_feats,
                        test_size=test_size,
                        preferred_model_id=candidate_model_id,
                        return_preprocessor=True,
                    )
                )

                train_rows = len(df_work) - len(y_val)
                validation_rows = len(y_val)

                lowers, uppers, uncert_desc = UncertaintyService.calculate_regression_intervals(
                    y_val_true=y_val,
                    y_val_pred=best_preds,
                    predictions=best_preds,
                    confidence_level=0.95,
                    is_non_negative=False,
                    is_forecasting=False,
                )

                prediction_points = [
                    PredictionPointItem(
                        index_or_date=str(i + 1),
                        predicted_value=round(float(p), 4),
                        actual_value=round(float(a), 4),
                        lower_bound=round(float(l), 4) if l is not None else None,
                        upper_bound=round(float(u), 4) if u is not None else None,
                    )
                    for i, (p, a, l, u) in enumerate(zip(best_preds, y_val, lowers, uppers))
                ]

                raw_imp = FeatureImportanceService.extract_importance(best_est, feat_names, max_features=10)
                feature_importance_items = [
                    FeatureImportanceResponseItem(
                        feature=fi.feature,
                        importance_score=round(float(fi.importance_score), 4),
                        percentage=round(float(fi.percentage), 2),
                    )
                    for fi in raw_imp
                ]

                best_cand = next(c for c in candidates if c.model_id == best_id)
                best_candidate_name = best_cand.model_name
                best_metrics_dict = best_cand.metrics.to_dict()

                candidate_metrics_list = [
                    ModelCandidateMetricItem(
                        model_id=c.model_id,
                        model_name=c.model_name,
                        problem_type=task_str,
                        metrics=c.metrics.to_dict(),
                        training_time_seconds=round(float(c.training_time_seconds), 4),
                        status=c.status,
                        warning=c.warning,
                        error=c.error,
                        is_best=(c.model_id == best_id),
                    )
                    for c in candidates
                ]

                explanation_text, lims = ExplanationService.generate_explanation(
                    mode="regression",
                    target_col=target_col,
                    selected_model=best_candidate_name,
                    metrics=best_cand.metrics,
                    feature_importance=[
                        type("FI", (), {"feature": f.feature, "percentage": f.percentage})
                        for f in feature_importance_items
                    ],
                )
                limitations.extend(lims)

                pipeline_artifact = {
                    "task_type": "regression",
                    "model_id": best_id,
                    "model_name": best_candidate_name,
                    "target_column": target_col,
                    "features_used": features_used,
                    "numeric_features": num_feats,
                    "categorical_features": cat_feats,
                    "preprocessor": preprocessor,
                    "model": best_est,
                }

            else:
                # Classification (Binary or Multiclass)
                task_str = "classification"
                selection_metric = "Highest Validation F1 Score"

                candidates, best_id, best_preds, y_val, best_est, feat_names, le, preprocessor = (
                    ClassificationEngine.train_and_evaluate(
                        df=df_work,
                        target_col=target_col,
                        numeric_features=num_feats,
                        categorical_features=cat_feats,
                        problem_type=problem_type,
                        test_size=test_size,
                        preferred_model_id=candidate_model_id,
                        return_preprocessor=True,
                    )
                )

                train_rows = len(df_work) - len(y_val)
                validation_rows = len(y_val)
                uncert_desc = "Probability distribution across target classes"

                pred_labels = le.inverse_transform(best_preds)
                actual_labels = le.inverse_transform(y_val)

                prediction_points = [
                    PredictionPointItem(
                        index_or_date=str(i + 1),
                        predicted_value=str(pl),
                        actual_value=str(al),
                    )
                    for i, (pl, al) in enumerate(zip(pred_labels, actual_labels))
                ]

                raw_imp = FeatureImportanceService.extract_importance(best_est, feat_names, max_features=10)
                feature_importance_items = [
                    FeatureImportanceResponseItem(
                        feature=fi.feature,
                        importance_score=round(float(fi.importance_score), 4),
                        percentage=round(float(fi.percentage), 2),
                    )
                    for fi in raw_imp
                ]

                best_cand = next(c for c in candidates if c.model_id == best_id)
                best_candidate_name = best_cand.model_name
                best_metrics_dict = best_cand.metrics.to_dict()

                candidate_metrics_list = [
                    ModelCandidateMetricItem(
                        model_id=c.model_id,
                        model_name=c.model_name,
                        problem_type=task_str,
                        metrics=c.metrics.to_dict(),
                        training_time_seconds=round(float(c.training_time_seconds), 4),
                        status=c.status,
                        warning=c.warning,
                        error=c.error,
                        is_best=(c.model_id == best_id),
                    )
                    for c in candidates
                ]

                explanation_text, lims = ExplanationService.generate_explanation(
                    mode="classification",
                    target_col=target_col,
                    selected_model=best_candidate_name,
                    metrics=best_cand.metrics,
                    feature_importance=[
                        type("FI", (), {"feature": f.feature, "percentage": f.percentage})
                        for f in feature_importance_items
                    ],
                )
                limitations.extend(lims)

                pipeline_artifact = {
                    "task_type": "classification",
                    "model_id": best_id,
                    "model_name": best_candidate_name,
                    "target_column": target_col,
                    "features_used": features_used,
                    "numeric_features": num_feats,
                    "categorical_features": cat_feats,
                    "preprocessor": preprocessor,
                    "model": best_est,
                    "label_encoder": le,
                }

        except Exception as exc:
            logger.error(f"Prediction model training failed: {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Model training process encountered an error: {str(exc)}",
            )

        # Save pipeline artifact to disk
        settings.ensure_directories()
        artifact_filename = f"model_run_{uuid.uuid4().hex[:12]}.joblib"
        artifact_file_path = settings.MODELS_DIR / artifact_filename
        joblib.dump(pipeline_artifact, artifact_file_path)

        # Persist run in SQLite
        db_run = PredictionRun(
            user_id=user.id,
            dataset_id=dataset.id,
            dataset_name=dataset.filename,
            run_name=f"{best_candidate_name} ({task_str.title()})",
            task_type=task_str,
            mode=request.mode or "auto",
            target_column=target_col,
            date_column=date_col,
            selected_model=best_candidate_name,
            selection_metric=selection_metric,
            train_rows=train_rows,
            validation_rows=validation_rows,
            forecast_horizon=forecast_horizon_val,
            metrics_json=json.dumps(best_metrics_dict),
            model_comparison_json=json.dumps([c.model_dump() for c in candidate_metrics_list]),
            predictions_json=json.dumps([p.model_dump() for p in prediction_points]),
            feature_importance_json=json.dumps([f.model_dump() for f in feature_importance_items]),
            features_used_json=json.dumps(features_used),
            features_excluded_json=json.dumps(features_excluded),
            warnings_json=json.dumps(suitability.warnings),
            limitations_json=json.dumps(limitations),
            explanation=explanation_text,
            uncertainty_method=uncert_desc,
            artifact_path=str(artifact_file_path),
            status="success",
        )

        db.add(db_run)
        db.commit()
        db.refresh(db_run)

        return PredictionRunDetailResponse(
            run_id=db_run.id,
            dataset_id=db_run.dataset_id,
            dataset_name=db_run.dataset_name,
            task_type=db_run.task_type,
            mode=db_run.mode,
            target_column=db_run.target_column,
            date_column=db_run.date_column,
            selected_model=db_run.selected_model,
            selection_metric=db_run.selection_metric,
            train_rows=db_run.train_rows,
            validation_rows=db_run.validation_rows,
            forecast_horizon=db_run.forecast_horizon,
            metrics=best_metrics_dict,
            model_comparison=candidate_metrics_list,
            predictions=prediction_points,
            feature_importance=feature_importance_items,
            features_used=features_used,
            features_excluded=features_excluded,
            warnings=suitability.warnings,
            limitations=limitations,
            explanation=explanation_text,
            uncertainty_method=uncert_desc,
            artifact_saved=True,
            created_at=db_run.created_at,
        )

    @classmethod
    def get_user_runs(
        cls,
        db: Session,
        user: User,
        dataset_id: Optional[int] = None,
    ) -> List[PredictionRunSummaryResponse]:
        """List historical prediction runs for user."""
        query = db.query(PredictionRun).filter(PredictionRun.user_id == user.id)
        if dataset_id:
            query = query.filter(PredictionRun.dataset_id == dataset_id)

        runs = query.order_by(PredictionRun.created_at.desc()).all()
        results = []
        for r in runs:
            metrics_dict = {}
            if r.metrics_json:
                try:
                    metrics_dict = json.loads(r.metrics_json)
                except Exception:
                    metrics_dict = {}

            results.append(
                PredictionRunSummaryResponse(
                    id=r.id,
                    dataset_id=r.dataset_id,
                    dataset_name=r.dataset_name,
                    task_type=r.task_type,
                    mode=r.mode,
                    target_column=r.target_column,
                    date_column=r.date_column,
                    selected_model=r.selected_model,
                    selection_metric=r.selection_metric,
                    metrics=metrics_dict,
                    created_at=r.created_at,
                )
            )
        return results

    @classmethod
    def get_run_detail(
        cls,
        db: Session,
        user: User,
        run_id: int,
    ) -> PredictionRunDetailResponse:
        """Fetch full details and artifact references of a specific run."""
        run = (
            db.query(PredictionRun)
            .filter(PredictionRun.id == run_id, PredictionRun.user_id == user.id)
            .first()
        )
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prediction run {run_id} not found or permission denied.",
            )

        def safe_json_load(text: Optional[str], default: Any) -> Any:
            if not text:
                return default
            try:
                return json.loads(text)
            except Exception:
                return default

        metrics = safe_json_load(run.metrics_json, {})
        model_comp_raw = safe_json_load(run.model_comparison_json, [])
        model_comp = [ModelCandidateMetricItem(**m) for m in model_comp_raw]

        preds_raw = safe_json_load(run.predictions_json, [])
        preds = [PredictionPointItem(**p) for p in preds_raw]

        fi_raw = safe_json_load(run.feature_importance_json, [])
        fi = [FeatureImportanceResponseItem(**f) for f in fi_raw]

        features_used = safe_json_load(run.features_used_json, [])
        features_excluded = safe_json_load(run.features_excluded_json, {})
        warnings = safe_json_load(run.warnings_json, [])
        limitations = safe_json_load(run.limitations_json, [])

        return PredictionRunDetailResponse(
            run_id=run.id,
            dataset_id=run.dataset_id,
            dataset_name=run.dataset_name,
            task_type=run.task_type,
            mode=run.mode,
            target_column=run.target_column,
            date_column=run.date_column,
            selected_model=run.selected_model,
            selection_metric=run.selection_metric,
            train_rows=run.train_rows,
            validation_rows=run.validation_rows,
            forecast_horizon=run.forecast_horizon,
            metrics=metrics,
            model_comparison=model_comp,
            predictions=preds,
            feature_importance=fi,
            features_used=features_used,
            features_excluded=features_excluded,
            warnings=warnings,
            limitations=limitations,
            explanation=run.explanation,
            uncertainty_method=run.uncertainty_method,
            artifact_saved=bool(run.artifact_path and Path(run.artifact_path).exists()),
            created_at=run.created_at,
        )

    @classmethod
    def delete_run(cls, db: Session, user: User, run_id: int) -> Dict[str, Any]:
        """Delete prediction run and clean up disk artifact."""
        run = (
            db.query(PredictionRun)
            .filter(PredictionRun.id == run_id, PredictionRun.user_id == user.id)
            .first()
        )
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prediction run {run_id} not found.",
            )

        if run.artifact_path:
            try:
                p = Path(run.artifact_path)
                if p.exists():
                    p.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove model artifact file {run.artifact_path}: {e}")

        db.delete(run)
        db.commit()
        return {"status": "deleted", "run_id": run_id}

    @classmethod
    def export_predictions_csv(cls, db: Session, user: User, run_id: int) -> Tuple[str, str]:
        """Export predictions to a CSV string and generate appropriate download filename."""
        detail = cls.get_run_detail(db, user, run_id)
        if not detail.predictions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No predictions found in this run.",
            )

        rows = []
        for p in detail.predictions:
            item = {
                "period_or_index": p.index_or_date,
                f"predicted_{detail.target_column}": p.predicted_value,
            }
            if p.actual_value is not None:
                item[f"actual_{detail.target_column}"] = p.actual_value
            if p.lower_bound is not None:
                item["lower_bound_95%"] = p.lower_bound
            if p.upper_bound is not None:
                item["upper_bound_95%"] = p.upper_bound
            rows.append(item)

        pred_df = pd.DataFrame(rows)
        csv_buffer = io.StringIO()
        pred_df.to_csv(csv_buffer, index=False)
        filename = f"predictions_run_{run_id}_{detail.task_type}.csv"
        return csv_buffer.getvalue(), filename

    @classmethod
    def export_evaluation_report(cls, db: Session, user: User, run_id: int) -> Tuple[str, str]:
        """Compile comprehensive markdown model evaluation report."""
        d = cls.get_run_detail(db, user, run_id)
        lines = [
            f"# Machine Learning Evaluation Report — Run #{d.run_id}",
            f"**Dataset**: {d.dataset_name} | **Task**: {d.task_type.upper()} | **Mode**: {d.mode.upper()}",
            f"**Generated**: {d.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## 1. Model Summary",
            f"- **Selected Algorithm**: {d.selected_model}",
            f"- **Selection Metric**: {d.selection_metric or 'Standard Performance'}",
            f"- **Target Column**: `{d.target_column}`",
            f"- **Training Samples**: {d.train_rows:,} rows",
            f"- **Validation Samples**: {d.validation_rows:,} rows",
            f"- **Uncertainty Method**: {d.uncertainty_method or 'N/A'}",
            "",
            "## 2. Validation Performance Metrics",
            "| Metric | Computed Value | Description |",
            "| :--- | :--- | :--- |",
        ]

        metric_descriptions = {
            "mae": "Mean Absolute Error (Average magnitude of errors)",
            "rmse": "Root Mean Squared Error (Penalizes larger errors)",
            "mse": "Mean Squared Error",
            "r2": "Coefficient of Determination (Variance explained by model)",
            "smape": "Symmetric Mean Absolute Percentage Error (%)",
            "accuracy": "Overall prediction accuracy ratio",
            "precision": "True positives over all positive predictions",
            "recall": "True positives over all actual positive cases",
            "f1": "Harmonic mean of precision and recall",
            "roc_auc": "Area under Receiver Operating Characteristic curve",
        }

        for k, v in d.metrics.items():
            if k == "confusion_matrix":
                continue
            desc = metric_descriptions.get(k.lower(), "Standard quantitative metric")
            lines.append(f"| **{k.upper()}** | `{v}` | {desc} |")

        if "confusion_matrix" in d.metrics and d.metrics["confusion_matrix"]:
            cm = d.metrics["confusion_matrix"]
            labels = cm.get("labels", [])
            matrix = cm.get("matrix", [])
            if labels and matrix:
                lines.extend([
                    "",
                    "## 3. Confusion Matrix",
                    f"Predicted along columns, Actual along rows. Labels: {', '.join(labels)}",
                    "",
                    "| Actual \\ Predicted | " + " | ".join(labels) + " |",
                    "| :--- | " + " | ".join([":---:" for _ in labels]) + " |",
                ])
                for lbl, row in zip(labels, matrix):
                    lines.append(f"| **{lbl}** | " + " | ".join([str(val) for val in row]) + " |")

        lines.extend([
            "",
            "## 4. Evaluated Candidate Models",
            "| Model Name | Status | Primary Metric | Training Time | Winning Model? |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        for c in d.model_comparison:
            primary_val = list(c.metrics.values())[0] if c.metrics else "N/A"
            star = "**YES (Selected)**" if c.is_best else "No"
            lines.append(
                f"| {c.model_name} | `{c.status}` | `{primary_val}` | {c.training_time_seconds}s | {star} |"
            )

        if d.feature_importance:
            lines.extend([
                "",
                "## 5. Feature Importance Rankings",
                "| Feature | Relative Weight | Contribution % |",
                "| :--- | :--- | :--- |",
            ])
            for f in d.feature_importance:
                lines.append(f"| `{f.feature}` | {f.importance_score} | {f.percentage}% |")

        if d.explanation:
            lines.extend([
                "",
                "## 6. Model Interpretation",
                d.explanation,
            ])

        if d.limitations:
            lines.extend([
                "",
                "## 7. Assumptions & Limitations",
            ])
            for lim in d.limitations:
                lines.append(f"- {lim}")

        filename = f"model_report_run_{d.run_id}_{d.task_type}.md"
        return "\n".join(lines), filename

    @classmethod
    def predict_new_data(
        cls,
        db: Session,
        user: User,
        run_id: int,
        file: UploadFile,
    ) -> PredictNewDataResponse:
        """Score uploaded unseen tabular data using the versioned trained model pipeline."""
        run = (
            db.query(PredictionRun)
            .filter(PredictionRun.id == run_id, PredictionRun.user_id == user.id)
            .first()
        )
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trained model run {run_id} was not found.",
            )

        if not run.artifact_path or not Path(run.artifact_path).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model pipeline artifact is missing from server storage. Cannot score new data.",
            )

        # Ingest new tabular file
        contents = file.file.read()
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file for prediction is empty (0 bytes).",
            )

        load_res = FileLoader.load_file(io.BytesIO(contents), file.filename or "new_data.csv", len(contents))
        if not load_res.success or load_res.df is None or load_res.df.empty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not parse uploaded file: {load_res.error_message or 'Unknown structure.'}",
            )

        new_df = load_res.df.copy()

        # Load serialized pipeline artifact
        try:
            artifact = joblib.load(run.artifact_path)
        except Exception as e:
            logger.error(f"Failed to load joblib model artifact: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load trained model pipeline artifact.",
            )

        task_type = artifact.get("task_type", run.task_type)
        features_used = artifact.get("features_used", [])

        if task_type == "forecasting":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time-series forecasting models project future horizon points from historical data. Use the horizon parameter rather than uploading separate batch records.",
            )

        # Check required features
        missing_features = [f for f in features_used if f not in new_df.columns]
        if missing_features:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Uploaded dataset is missing required predictor columns used during training: "
                    f"{', '.join(missing_features[:5])}"
                    + (f" and {len(missing_features) - 5} more" if len(missing_features) > 5 else "")
                ),
            )

        preprocessor = artifact.get("preprocessor")
        model = artifact.get("model")
        num_feats = artifact.get("numeric_features", [])
        cat_feats = artifact.get("categorical_features", [])
        pred_col_name = f"predicted_{run.target_column}"

        try:
            # Transform features using preprocessor fitted ONLY on training data
            X_input = new_df[num_feats + cat_feats]
            if preprocessor is not None:
                X_proc = preprocessor.transform(X_input)
            else:
                X_proc = X_input.values

            raw_preds = model.predict(X_proc)

            if task_type == "classification" and "label_encoder" in artifact:
                le = artifact["label_encoder"]
                final_preds = le.inverse_transform(raw_preds)
            else:
                final_preds = [round(float(p), 4) for p in raw_preds]

            new_df[pred_col_name] = final_preds

            # Prepare preview of first 100 rows
            preview_rows = new_df.head(100).to_dict(orient="records")
            clean_preview_rows = []
            for row in preview_rows:
                clean_row = {}
                for k, v in row.items():
                    if pd.isna(v):
                        clean_row[k] = None
                    elif isinstance(v, (np.floating, float)):
                        clean_row[k] = round(float(v), 4)
                    elif isinstance(v, (np.integer, int)):
                        clean_row[k] = int(v)
                    else:
                        clean_row[k] = str(v)
                clean_preview_rows.append(clean_row)

            return PredictNewDataResponse(
                run_id=run.id,
                total_rows=int(len(new_df)),
                predicted_rows=clean_preview_rows,
                target_column=run.target_column,
                predicted_column_name=pred_col_name,
                features_used=features_used,
                warnings=[],
            )

        except Exception as exc:
            logger.error(f"Inference prediction error on new data: {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to generate predictions on uploaded data: {str(exc)}",
            )
