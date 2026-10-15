"""Insight Service - Orchestrator for Phase 5 Statistical Analysis and Insight Synthesis.

Coordinates data extraction, statistical summaries, trend detection, correlation matrices,
top/bottom rankings, cross-dataset linkages, and session-state caching.
"""

from typing import Dict, Any, List, Optional
import pandas as pd

from models.insight import (
    Insight,
    TrendAnalysisResult,
    TopBottomCategoryResult,
    DistributionAnalysisResult,
    CorrelationAnalysisResult,
    CategoryBreakdownResult,
    CrossDatasetInsightResult,
    DatasetAnalysisResult,
)
from tools.statistics_tool import StatisticsTool
from agents.insight_agent import InsightAgent
from core.session_manager import SessionManager


class InsightService:
    """High-level analytical orchestrator for dataset analysis and insight generation."""

    @classmethod
    def analyze_dataset(
        cls,
        df: pd.DataFrame,
        dataset_name: str,
        force_recompute: bool = False,
    ) -> DatasetAnalysisResult:
        """Execute full statistical and insight pipeline for an individual dataset with caching."""
        if df is None or df.empty:
            return DatasetAnalysisResult(dataset_name=dataset_name, row_count=0, column_count=0)

        # 1. Check cache in SessionManager
        cached = SessionManager.get(f"analysis_result_{dataset_name}")
        if cached is not None and not force_recompute:
            return cached

        # 2. Compute statistical summary, trends, distributions, correlations, and categories
        analysis_result = StatisticsTool.compute_summary(df, dataset_name=dataset_name)

        # 3. Retrieve Phase 4 anomaly results if available
        anomaly_results = SessionManager.get_anomaly_results(dataset_name)

        # 4. Retrieve data quality profile if available
        active_view = SessionManager.get_active_view()
        quality_profile = SessionManager.get_profile(active_view, filename=dataset_name)

        # 5. Generate structured insights
        insights = InsightAgent.generate_insights(
            analysis_result=analysis_result,
            anomaly_results=anomaly_results,
            quality_profile=quality_profile,
        )
        analysis_result.insights = insights

        # 6. Cache in session state
        SessionManager.set(f"analysis_result_{dataset_name}", analysis_result)

        # Also register in global analysis_results dictionary
        all_analysis = SessionManager.get("analysis_results", {})
        all_analysis[dataset_name] = analysis_result
        SessionManager.set("analysis_results", all_analysis)

        all_insights = SessionManager.get("insights", {})
        all_insights[dataset_name] = insights
        SessionManager.set("insights", all_insights)

        return analysis_result

    @classmethod
    def analyze_all_datasets(
        cls,
        datasets: Dict[str, pd.DataFrame],
        relationships: Optional[List[Any]] = None,
        force_recompute: bool = False,
    ) -> Dict[str, DatasetAnalysisResult]:
        """Analyze all loaded datasets and execute cross-dataset linkages when valid."""
        results: Dict[str, DatasetAnalysisResult] = {}
        if not datasets:
            return results

        # 1. Analyze each dataset independently
        for name, df in datasets.items():
            results[name] = cls.analyze_dataset(df, dataset_name=name, force_recompute=force_recompute)

        # 2. Check cross-dataset relationships (Multi-Dataset Mode)
        rels = relationships or SessionManager.get_relationships()
        cross_insights: List[CrossDatasetInsightResult] = []

        if len(datasets) > 1 and rels:
            for r in rels:
                # Only use HIGH confidence or user-confirmed relationships
                is_confirmed = SessionManager.is_relationship_confirmed(getattr(r, "key_id", ""))
                is_high_conf = getattr(r, "confidence", "") == "HIGH"
                if not (is_high_conf or is_confirmed):
                    continue

                src_name = r.source_dataset
                tgt_name = r.target_dataset
                if src_name in datasets and tgt_name in datasets:
                    cross_res = StatisticsTool.analyze_cross_dataset(
                        left_df=datasets[src_name],
                        left_name=src_name,
                        right_df=datasets[tgt_name],
                        right_name=tgt_name,
                        relationship=r,
                    )
                    cross_insights.append(cross_res)

            # Synthesize cross-dataset insights into first dataset or global store
            if cross_insights:
                primary_name = next(iter(datasets.keys()))
                primary_res = results.get(primary_name)
                if primary_res:
                    primary_res.cross_dataset_results = cross_insights
                    extra_insights = InsightAgent.generate_insights(
                        analysis_result=primary_res,
                        cross_dataset_results=cross_insights,
                    )
                    # Merge cross-dataset insights uniquely
                    existing_titles = {ins.title for ins in primary_res.insights}
                    for ins in extra_insights:
                        if ins.category == "Cross-Dataset" and ins.title not in existing_titles:
                            primary_res.insights.append(ins)

        return results

    @classmethod
    def get_kpi_summary(cls, datasets: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Compute aggregated dashboard KPIs across all analyzed datasets."""
        total_rows = sum(len(df) for df in datasets.values())
        total_cols = sum(len(df.columns) for df in datasets.values())
        datasets_count = len(datasets)

        # Calculate average health score from profiles
        health_scores = []
        for name in datasets.keys():
            prof = SessionManager.get_profile(SessionManager.get_active_view(), filename=name)
            if prof and hasattr(prof, "quality"):
                health_scores.append(prof.quality.health_score)

        avg_health = int(sum(health_scores) / len(health_scores)) if health_scores else 95

        # Total anomalies from Phase 4
        all_anomalies = SessionManager.get_all_anomaly_results()
        total_anom = 0
        for ds_anom in all_anomalies.values():
            if isinstance(ds_anom, dict):
                if "iqr" in ds_anom:
                    total_anom += getattr(ds_anom["iqr"], "total_outlier_rows", 0)
                elif "isolation_forest" in ds_anom:
                    total_anom += getattr(ds_anom["isolation_forest"], "anomaly_count", 0)

        # Important trends and key insights counts
        total_trends = 0
        total_insights = 0
        all_analysis = SessionManager.get("analysis_results", {})
        for res in all_analysis.values():
            if isinstance(res, DatasetAnalysisResult):
                total_trends += len(res.trends)
                total_insights += len(res.insights)

        return {
            "datasets_analyzed": datasets_count,
            "total_rows": total_rows,
            "total_columns": total_cols,
            "data_quality_score": avg_health,
            "anomalies_detected": total_anom,
            "important_trends": total_trends,
            "key_insights": total_insights,
        }

    # =========================================================================
    # CONCRETE MODULE CONTRACT (MODULE 10)
    # =========================================================================

    @classmethod
    def analysis_orchestrator(
        cls,
        datasets: Dict[str, pd.DataFrame],
        analysis_configuration: Optional[Dict[str, Any]] = None,
        anomaly_results: Optional[Dict[str, Any]] = None,
        validated_relationships: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """MODULE 10 CONTRACT: Central analysis orchestration pipeline.

        Coordinates input validation, dataset identification, statistical calculations,
        trend analysis, correlation discovery, categorical breakdowns, Phase 4 anomaly
        ingestion, cross-dataset safety verification, and insight generation.
        """
        # 1. Validate Input
        if not datasets or not isinstance(datasets, dict):
            return {
                "status": "error",
                "error_type": "ValidationError",
                "message": "Input 'datasets' must be a non-empty dictionary of DataFrames",
                "details": "Provided datasets argument is empty or not a valid dictionary.",
            }

        # 2. Identify Dataset
        datasets_analyzed = list(datasets.keys())
        cfg = analysis_configuration or {}
        target_name = cfg.get("target_dataset")
        if not target_name or target_name not in datasets:
            target_name = datasets_analyzed[0]

        primary_df = datasets[target_name]
        if primary_df is None or primary_df.empty:
            return {
                "status": "error",
                "error_type": "EmptyDataError",
                "message": f"Target dataset '{target_name}' is empty or None",
                "details": "Cannot perform analysis pipeline on an empty DataFrame.",
            }

        # 3. Run Statistical Analysis
        selected_cols = cfg.get("selected_columns")
        stats_res = StatisticsTool.statistical_analysis(primary_df, selected_columns=selected_cols)

        # 4. Run Trend Analysis
        date_col = cfg.get("date_column")
        num_cols = cfg.get("numeric_columns")
        trends_res = StatisticsTool.trend_analysis(primary_df, date_column=date_col, numeric_columns=num_cols)

        # 5. Run Correlation Analysis
        corr_thresh = cfg.get("correlation_threshold", 0.70)
        corrs_res = StatisticsTool.correlation_analysis(primary_df, numeric_columns=num_cols, threshold=corr_thresh)

        # 6. Run Category Analysis
        cat_cols = cfg.get("categorical_columns")
        cats_res = StatisticsTool.category_analysis(primary_df, categorical_columns=cat_cols, numeric_columns=num_cols)

        # 7. Integrate Anomaly Results
        ds_anom = None
        if anomaly_results and isinstance(anomaly_results, dict):
            ds_anom = anomaly_results.get(target_name) if target_name in anomaly_results else anomaly_results
        else:
            ds_anom = SessionManager.get_anomaly_results(target_name)
        anom_res = StatisticsTool.anomaly_integration(ds_anom)

        # 8. Perform Cross-Dataset Analysis if required
        cross_res: Dict[str, Any] = {}
        rels = validated_relationships or SessionManager.get_relationships()
        if len(datasets) > 1 and rels:
            cross_res = StatisticsTool.cross_dataset_analysis(
                datasets=datasets,
                validated_relationships=rels,
            )
        else:
            cross_res = {
                "status": "unavailable",
                "reason": "Single dataset mode or no validated relationships available",
            }

        # 9. Generate Insights
        data_quality_payload = {
            "duplicate_rows": int(primary_df.duplicated().sum()),
            "duplicate_rate": round(float(primary_df.duplicated().mean() * 100), 2),
            "missing_count": int(primary_df.isna().sum().sum()),
            "missing_rate": round(float(primary_df.isna().mean().mean() * 100), 2),
            "columns": list(primary_df.columns),
        }

        insight_payload = {
            "dataset_name": target_name,
            "statistics": stats_res,
            "trends": trends_res,
            "correlations": corrs_res,
            "categories": cats_res,
            "anomalies": anom_res,
            "data_quality": data_quality_payload,
            "cross_dataset": cross_res,
        }
        insights_res = InsightAgent.insight_engine(insight_payload)

        # 10. Return Structured Analysis Result
        return {
            "status": "success",
            "datasets_analyzed": datasets_analyzed,
            "statistics": stats_res,
            "trends": trends_res,
            "correlations": corrs_res,
            "categories": cats_res,
            "anomalies": anom_res,
            "cross_dataset": cross_res,
            "insights": insights_res,
        }


    @classmethod
    def run_phase5_analysis(
        cls,
        datasets: Dict[str, pd.DataFrame],
        analysis_configuration: Optional[Dict[str, Any]] = None,
        anomaly_results: Optional[Dict[str, Any]] = None,
        validated_relationships: Optional[List[Any]] = None,
        join_audit: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Execute complete Phase 5 analysis pipeline via Phase 5 engine."""
        from services.phase5_engine import run_phase5_analysis as _run_p5
        return _run_p5(
            datasets=datasets,
            analysis_configuration=analysis_configuration,
            anomaly_results=anomaly_results,
            validated_relationships=validated_relationships,
            join_audit=join_audit,
        )


def analysis_orchestrator(
    datasets: Dict[str, pd.DataFrame],
    analysis_configuration: Optional[Dict[str, Any]] = None,
    anomaly_results: Optional[Dict[str, Any]] = None,
    validated_relationships: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """MODULE 10 CONTRACT: Standalone wrapper for analysis orchestrator."""
    return InsightService.analysis_orchestrator(
        datasets=datasets,
        analysis_configuration=analysis_configuration,
        anomaly_results=anomaly_results,
        validated_relationships=validated_relationships,
    )


def run_phase5_analysis(
    datasets: Dict[str, pd.DataFrame],
    analysis_configuration: Optional[Dict[str, Any]] = None,
    anomaly_results: Optional[Dict[str, Any]] = None,
    validated_relationships: Optional[List[Any]] = None,
    join_audit: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Top-level pipeline coordinator for Phase 5 intelligent data analysis."""
    return InsightService.run_phase5_analysis(
        datasets=datasets,
        analysis_configuration=analysis_configuration,
        anomaly_results=anomaly_results,
        validated_relationships=validated_relationships,
        join_audit=join_audit,
    )


