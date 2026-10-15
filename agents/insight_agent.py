"""Insight Agent - Autonomous Data-Driven Insight Generation Engine.

Synthesizes deterministic, mathematically backed insights from statistical summaries,
time-series trend detections, correlation networks, distribution shapes, data hygiene audits,
and Phase 4 anomaly detection results.
"""

from typing import Dict, Any, List, Optional
import os
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
from core.config import config


class InsightAgent:
    """Agent responsible for deriving actionable, prioritized, and hallucination-free executive insights."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.version = "Phase 5 - Intelligent Data Analysis & Insight Generation"

    # =========================================================================
    # DETERMINISTIC INSIGHT GENERATION
    # =========================================================================

    @classmethod
    def generate_insights(
        cls,
        analysis_result: DatasetAnalysisResult,
        anomaly_results: Optional[Dict[str, Any]] = None,
        quality_profile: Optional[Any] = None,
        cross_dataset_results: Optional[List[CrossDatasetInsightResult]] = None,
    ) -> List[Insight]:
        """Synthesize structured, prioritized insights strictly from computed mathematical facts."""
        insights: List[Insight] = []
        ds_name = analysis_result.dataset_name

        # ---------------------------------------------------------------------
        # 1. DATA QUALITY INSIGHTS
        # ---------------------------------------------------------------------
        if analysis_result.duplicate_rows > 0:
            insights.append(Insight(
                title=f"Duplicate Records Detected ({analysis_result.duplicate_rows:,} rows)",
                category="Data Quality",
                finding=f"Identified {analysis_result.duplicate_rows:,} identical duplicate rows representing {analysis_result.duplicate_rate}% of the dataset.",
                evidence=f"Total Records: {analysis_result.row_count:,} | Duplicate Count: {analysis_result.duplicate_rows:,} ({analysis_result.duplicate_rate}%)",
                severity="High" if analysis_result.duplicate_rate >= 5.0 else "Medium",
                relevant_dataset=ds_name,
                relevant_columns=analysis_result.numeric_columns[:3] or ["All Columns"],
                recommended_investigation="Review upstream ingestion pipelines to eliminate duplicate transmissions or apply deduplication in Phase 3 Cleaning.",
                chart_type="bar",
            ))

        if analysis_result.missing_count > 0:
            severity = "High" if analysis_result.missing_rate >= 10.0 else ("Medium" if analysis_result.missing_rate >= 2.0 else "Low")
            insights.append(Insight(
                title=f"Missing Value Concentration ({analysis_result.missing_rate}% overall)",
                category="Data Quality",
                finding=f"Found {analysis_result.missing_count:,} null/empty cells across the dataset.",
                evidence=f"Total Cells: {analysis_result.row_count * max(1, analysis_result.column_count):,} | Null Cells: {analysis_result.missing_count:,} ({analysis_result.missing_rate}%)",
                severity=severity,
                relevant_dataset=ds_name,
                relevant_columns=["Multiple Columns"],
                recommended_investigation="Evaluate missingness mechanisms (MCAR/MAR) and select appropriate imputation strategies (median/mode/forward fill).",
                chart_type="bar",
            ))

        # Check constant columns or high missing columns from quality_profile
        if quality_profile and hasattr(quality_profile, "quality"):
            for const_col in getattr(quality_profile.quality, "constant_columns", []):
                insights.append(Insight(
                    title=f"Zero-Variance Feature: `{const_col}`",
                    category="Data Quality",
                    finding=f"Column `{const_col}` contains a single constant value across all {analysis_result.row_count:,} rows.",
                    evidence=f"Unique values: 1 across {analysis_result.row_count:,} observations.",
                    severity="Low",
                    relevant_dataset=ds_name,
                    relevant_columns=[const_col],
                    recommended_investigation="Consider dropping this feature before modeling, as zero variance yields zero analytical signal.",
                ))

        # ---------------------------------------------------------------------
        # 2. TREND & TIME-SERIES INSIGHTS
        # ---------------------------------------------------------------------
        for tr in analysis_result.trends:
            if abs(tr.change_pct) >= 10.0 or tr.direction in ("Increasing", "Decreasing"):
                verb = "surged by" if tr.change_pct > 0 else "declined by"
                severity = "High" if abs(tr.change_pct) >= 25.0 else "Medium"
                insights.append(Insight(
                    title=f"Significant {tr.direction} Trend in `{tr.metric_column}`",
                    category="Trend",
                    finding=f"Average `{tr.metric_column}` {verb} {abs(tr.change_pct)}% from {tr.start_date} to {tr.end_date}.",
                    evidence=f"Initial: {tr.start_value:,.2f} on {tr.start_date} -> Final: {tr.end_value:,.2f} on {tr.end_date} (Peak: {tr.peak_value:,.2f} on {tr.peak_date}, Trough: {tr.trough_value:,.2f} on {tr.trough_date})",
                    severity=severity,
                    relevant_dataset=ds_name,
                    relevant_columns=[tr.date_column, tr.metric_column],
                    recommended_investigation=f"Examine underlying operational or market drivers surrounding the peak ({tr.peak_date}) and trough ({tr.trough_date}).",
                    chart_type="line",
                ))

            # Sudden changes
            for sc in tr.sudden_changes[:2]:
                insights.append(Insight(
                    title=f"{sc['type']} Detected in `{tr.metric_column}`",
                    category="Trend",
                    finding=f"Observed an abrupt step change of {sc['change_pct']:+.1f}% on {sc['date']}.",
                    evidence=f"Shifted from {sc['previous_value']:,.2f} ({sc['previous_date']}) to {sc['current_value']:,.2f} ({sc['date']}).",
                    severity="High" if abs(sc["change_pct"]) >= 30.0 else "Medium",
                    relevant_dataset=ds_name,
                    relevant_columns=[tr.date_column, tr.metric_column],
                    recommended_investigation=f"Cross-reference date {sc['date']} against promotional events, supply shocks, or reporting policy revisions.",
                    chart_type="line",
                ))

        # ---------------------------------------------------------------------
        # 3. DISTRIBUTION & VOLATILITY INSIGHTS
        # ---------------------------------------------------------------------
        for col_name, dist in analysis_result.distributions.items():
            if dist.is_skewed:
                skew_desc = "strongly positive/right-skewed" if dist.skewness > 0 else "strongly negative/left-skewed"
                severity = "High" if abs(dist.skewness) >= 2.0 else "Medium"
                insights.append(Insight(
                    title=f"Asymmetric Distribution in `{col_name}` (Skewness: {dist.skewness:+.2f})",
                    category="Distribution",
                    finding=f"`{col_name}` exhibits a {skew_desc} distribution where the mean ({dist.mean:,.2f}) diverges substantially from the median ({dist.median:,.2f}).",
                    evidence=f"Mean: {dist.mean:,.2f} | Median: {dist.median:,.2f} | Std: {dist.std:,.2f} | Skewness: {dist.skewness:+.2f} | Kurtosis: {dist.kurtosis:+.2f}",
                    severity=severity,
                    relevant_dataset=ds_name,
                    relevant_columns=[col_name],
                    recommended_investigation="Rely on non-parametric median/IQR rather than mean/standard deviation for central tendency, or consider logarithmic transformation.",
                    chart_type="box",
                ))
            elif dist.is_high_variance:
                insights.append(Insight(
                    title=f"Elevated Variance & Wide Range in `{col_name}`",
                    category="Distribution",
                    finding=f"`{col_name}` spans a substantial range ({dist.min_val:,.2f} to {dist.max_val:,.2f}) with a high standard deviation ({dist.std:,.2f}).",
                    evidence=f"Min: {dist.min_val:,.2f} | Max: {dist.max_val:,.2f} | IQR: {dist.iqr:,.2f} | Variance: {dist.variance:,.2f}",
                    severity="Medium",
                    relevant_dataset=ds_name,
                    relevant_columns=[col_name],
                    recommended_investigation="Segment this feature across categorical cohorts to determine whether variance is driven by sub-population differences.",
                    chart_type="box",
                ))

        # ---------------------------------------------------------------------
        # 4. CORRELATION & RELATIONSHIP INSIGHTS
        # ---------------------------------------------------------------------
        if analysis_result.correlations:
            for pair in analysis_result.correlations.strong_positive_pairs[:3]:
                insights.append(Insight(
                    title=f"Strong Positive Association: `{pair.feature_x}` & `{pair.feature_y}`",
                    category="Correlation",
                    finding=pair.non_causal_statement,
                    evidence=f"Pearson correlation coefficient r = +{pair.correlation:.3f} across {analysis_result.row_count:,} observations.",
                    severity="Medium",
                    relevant_dataset=ds_name,
                    relevant_columns=[pair.feature_x, pair.feature_y],
                    recommended_investigation="Evaluate collinearity implications if building predictive models; verify whether both features provide independent analytical value.",
                    chart_type="scatter",
                ))

            for pair in analysis_result.correlations.strong_negative_pairs[:3]:
                insights.append(Insight(
                    title=f"Strong Inverse Association: `{pair.feature_x}` & `{pair.feature_y}`",
                    category="Correlation",
                    finding=pair.non_causal_statement,
                    evidence=f"Pearson correlation coefficient r = {pair.correlation:.3f} across {analysis_result.row_count:,} observations.",
                    severity="High" if abs(pair.correlation) >= 0.85 else "Medium",
                    relevant_dataset=ds_name,
                    relevant_columns=[pair.feature_x, pair.feature_y],
                    recommended_investigation="Investigate trade-offs or reciprocal dynamics between these two features (e.g. price elasticity or discount vs. margin).",
                    chart_type="scatter",
                ))

        # ---------------------------------------------------------------------
        # 5. CATEGORY & PERFORMANCE CONCENTRATION INSIGHTS
        # ---------------------------------------------------------------------
        for tb in analysis_result.top_bottom_rankings:
            if tb.concentration_ratio_top3 >= 50.0 and len(tb.top_items) >= 3:
                top_names = ", ".join(f"'{it['category']}' ({it['share_pct']}%)" for it in tb.top_items[:3])
                insights.append(Insight(
                    title=f"High Segment Concentration in `{tb.category_column}` ({tb.concentration_ratio_top3}% in Top 3)",
                    category="Category",
                    finding=f"The top 3 `{tb.category_column}` categories account for {tb.concentration_ratio_top3}% of total `{tb.metric_column}`.",
                    evidence=f"Dominant leaders: {top_names} out of {tb.total_categories} total categories.",
                    severity="High" if tb.concentration_ratio_top3 >= 70.0 else "Medium",
                    relevant_dataset=ds_name,
                    relevant_columns=[tb.category_column, tb.metric_column],
                    recommended_investigation="Assess dependency and customer/product concentration risk; formulate growth strategies for under-indexed lower segments.",
                    chart_type="bar",
                ))

        for cat_col, cb in analysis_result.categories.items():
            if cb.is_imbalanced:
                insights.append(Insight(
                    title=f"Category Distribution Imbalance in `{cat_col}`",
                    category="Category",
                    finding=cb.imbalance_explanation,
                    evidence=f"Top category '{cb.most_frequent}' ({cb.most_frequent_pct}%) vs lowest '{cb.least_frequent}' ({cb.least_frequent_pct}%) across {cb.total_non_null:,} records.",
                    severity="Medium",
                    relevant_dataset=ds_name,
                    relevant_columns=[cat_col],
                    recommended_investigation="Check for sampling bias or domain-specific market dominance.",
                    chart_type="bar",
                ))

        # ---------------------------------------------------------------------
        # 6. ANOMALY-BASED INSIGHTS (PHASE 4 INTEGRATION)
        # ---------------------------------------------------------------------
        if anomaly_results and isinstance(anomaly_results, dict):
            if "iqr" in anomaly_results:
                iqr_r = anomaly_results["iqr"]
                outlier_rows = getattr(iqr_r, "total_outlier_rows", 0)
                outlier_rate = getattr(iqr_r, "outlier_rate", 0.0)
                if outlier_rows > 0:
                    top_out_cols = sorted(
                        getattr(iqr_r, "column_results", {}).items(),
                        key=lambda x: x[1].total_outliers,
                        reverse=True,
                    )
                    top_col_summary = ", ".join(f"`{c}` ({res.total_outliers} outliers)" for c, res in top_out_cols[:2])
                    insights.append(Insight(
                        title=f"Statistical Outliers Flagged via IQR ({outlier_rows:,} records, {outlier_rate}%)",
                        category="Anomaly",
                        finding=f"Identified {outlier_rows:,} records with numerical values exceeding 1.5× IQR boundary cutoffs.",
                        evidence=f"Total Outlier Rows: {outlier_rows:,} ({outlier_rate}%) | Highest concentration in: {top_col_summary}",
                        severity="High" if outlier_rate >= 5.0 else "Medium",
                        relevant_dataset=ds_name,
                        relevant_columns=[c for c, _ in top_out_cols[:3]],
                        recommended_investigation="Inspect flagged records in Phase 4 Anomalies workspace; apply controlled capping or winsorization if verified as measurement noise.",
                        chart_type="box",
                    ))

            if "isolation_forest" in anomaly_results:
                if_r = anomaly_results["isolation_forest"]
                anom_count = getattr(if_r, "anomaly_count", 0)
                anom_pct = getattr(if_r, "anomaly_pct", 0.0)
                feats = getattr(if_r, "features_used", [])
                if anom_count > 0:
                    insights.append(Insight(
                        title=f"Isolation Forest Multi-Feature Anomalies ({anom_count:,} records)",
                        category="Anomaly",
                        finding=f"Isolation Forest detected {anom_count:,} multi-dimensional anomalies ({anom_pct}%) departing from expected density patterns.",
                        evidence=f"Anomalies: {anom_count:,} ({anom_pct}%) evaluated across {len(feats)} features: {', '.join(feats[:4])}",
                        severity="High" if anom_pct >= 5.0 else "Medium",
                        relevant_dataset=ds_name,
                        relevant_columns=feats[:4],
                        recommended_investigation="Review multivariate clusters in Phase 4 workspace to distinguish legitimate rare high-value transactions from systemic errors.",
                        chart_type="scatter",
                    ))

        # ---------------------------------------------------------------------
        # 7. CROSS-DATASET LINKAGE INSIGHTS
        # ---------------------------------------------------------------------
        if cross_dataset_results:
            for cd in cross_dataset_results:
                if cd.is_blocked:
                    insights.append(Insight(
                        title=f"Cross-File Linkage Blocked: `{cd.left_dataset}` & `{cd.right_dataset}`",
                        category="Cross-Dataset",
                        finding=f"Automated cross-dataset joining was safely halted to prevent analytical corruption.",
                        evidence=f"Reason: {cd.block_reason} | Key: `{cd.join_key}`",
                        severity="High",
                        relevant_dataset=f"{cd.left_dataset} & {cd.right_dataset}",
                        relevant_columns=[cd.join_key],
                        recommended_investigation="Resolve duplicate keys in source files or confirm many-to-one relationship explicitly before joining.",
                    ))
                elif cd.breakdown and cd.metric_column and cd.group_column:
                    top_entity = cd.breakdown[0]
                    insights.append(Insight(
                        title=f"Cross-Dataset Performance: `{cd.metric_column}` by `{cd.group_column}`",
                        category="Cross-Dataset",
                        finding=f"Joined `{cd.left_dataset}` and `{cd.right_dataset}` via `{cd.join_key}` to reveal leading segment `{top_entity['entity']}`.",
                        evidence=f"Joined records: {cd.rows_after:,} | Top Segment: '{top_entity['entity']}' generated {top_entity['total']:,.2f} total (avg {top_entity['average']:,.2f}).",
                        severity="Medium",
                        relevant_dataset=f"{cd.left_dataset} + {cd.right_dataset}",
                        relevant_columns=[cd.metric_column, cd.group_column],
                        recommended_investigation="Leverage linked entity dimensions to enrich marketing, procurement, or operational segmentation models.",
                        chart_type="bar",
                    ))

        # Fallback if no specific insight triggered
        if not insights:
            insights.append(Insight(
                title=f"Baseline Health Confirmation for `{ds_name}`",
                category="Statistical",
                finding=f"Dataset exhibits balanced distributions without extreme skewness, severe missingness, or duplicate records.",
                evidence=f"{analysis_result.row_count:,} records across {analysis_result.column_count} features.",
                severity="Low",
                relevant_dataset=ds_name,
                relevant_columns=analysis_result.numeric_columns[:3] or ["All Columns"],
                recommended_investigation="Data is ready for downstream analytical querying and modeling.",
            ))

        # Sort insights by severity priority: High -> Medium -> Low
        severity_order = {"High": 0, "Medium": 1, "Low": 2}
        insights.sort(key=lambda x: severity_order.get(x.severity, 3))

        return insights

    # =========================================================================
    # CONCRETE MODULE CONTRACTS (MODULES 7 & 9)
    # =========================================================================

    @classmethod
    def insight_engine(cls, analysis_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """MODULE 7 CONTRACT: Structured, evidence-based insight generation from analysis payload.

        Input:
            analysis_payload: Dict containing 'statistics', 'trends', 'correlations',
                              'categories', 'anomalies', 'data_quality', 'cross_dataset'
        Output:
            List of insight dicts with title, category, finding, evidence, severity,
            dataset, columns, recommended_investigation.
        """
        raw_insights: List[Dict[str, Any]] = []
        dataset_name = analysis_payload.get("dataset_name", "dataset.csv")

        # 1. Data Quality Insights
        dq = analysis_payload.get("data_quality", {})
        dups = dq.get("duplicate_rows", 0)
        dup_pct = dq.get("duplicate_rate", 0.0)
        if dups > 0:
            raw_insights.append({
                "title": f"Duplicate Records Detected ({dups:,} rows)",
                "category": "Data Quality",
                "finding": f"Identified {dups:,} duplicate records representing {dup_pct}% of the dataset.",
                "evidence": {"duplicate_count": dups, "duplicate_percentage": dup_pct},
                "severity": "High" if dup_pct >= 5.0 else "Medium",
                "dataset": dataset_name,
                "columns": dq.get("columns", ["All Columns"])[:3],
                "recommended_investigation": "Review upstream data pipelines to prevent repeated transmissions or apply deduplication.",
            })

        missing_cnt = dq.get("missing_count", 0)
        missing_pct = dq.get("missing_rate", 0.0)
        if missing_cnt > 0:
            raw_insights.append({
                "title": f"Missing Value Concentration ({missing_pct}% overall)",
                "category": "Data Quality",
                "finding": f"Detected {missing_cnt:,} missing cells ({missing_pct}% of total values).",
                "evidence": {"missing_count": missing_cnt, "missing_percentage": missing_pct},
                "severity": "High" if missing_pct >= 10.0 else ("Medium" if missing_pct >= 2.0 else "Low"),
                "dataset": dataset_name,
                "columns": dq.get("high_missing_columns", ["Multiple Columns"])[:3],
                "recommended_investigation": "Evaluate imputation strategies (median/mode) or drop high-null columns before downstream tasks.",
            })

        # 2. Trend Insights
        trends = analysis_payload.get("trends", {})
        for tr in trends.get("trends", []):
            chg = tr.get("change_percentage", 0.0)
            if abs(chg) >= 10.0 or tr.get("direction") in ("increasing", "decreasing"):
                dir_label = tr.get("direction", "stable").capitalize()
                raw_insights.append({
                    "title": f"{dir_label} Trend in `{tr.get('column')}` ({chg:+.1f}%)",
                    "category": "Trend",
                    "finding": f"`{tr.get('column')}` showed an overall {tr.get('direction')} trajectory with a net shift of {chg:+.1f}%.",
                    "evidence": {
                        "change_percentage": chg,
                        "start_value": tr.get("start_value"),
                        "end_value": tr.get("end_value"),
                        "start_date": tr.get("start_date"),
                        "end_date": tr.get("end_date"),
                    },
                    "severity": "High" if abs(chg) >= 25.0 else "Medium",
                    "dataset": dataset_name,
                    "columns": [trends.get("date_column", "Date"), tr.get("column")],
                    "recommended_investigation": f"Investigate market or operational drivers during the period from {tr.get('start_date')} to {tr.get('end_date')}.",
                })

        for sc in trends.get("changes", [])[:2]:
            raw_insights.append({
                "title": f"{sc.get('type', 'Sudden Shift')} in Time-Series",
                "category": "Trend",
                "finding": f"Abrupt step shift of {sc.get('change_pct', 0.0):+.1f}% occurred on {sc.get('date')}.",
                "evidence": sc,
                "severity": "High" if abs(sc.get("change_pct", 0)) >= 30.0 else "Medium",
                "dataset": dataset_name,
                "columns": [trends.get("date_column", "Date")],
                "recommended_investigation": f"Cross-examine events on {sc.get('date')} to establish operational causality.",
            })

        # 3. Distribution Insights
        dists = analysis_payload.get("statistics", {}).get("distribution_statistics", {})
        col_stats = analysis_payload.get("statistics", {}).get("column_statistics", {})
        for col, d in dists.items():
            if d.get("is_skewed"):
                stats = col_stats.get(col, {})
                skew_val = stats.get("skewness", 0.0)
                raw_insights.append({
                    "title": f"Asymmetric Distribution in `{col}`",
                    "category": "Distribution",
                    "finding": f"`{col}` has a skewed distribution (skewness = {skew_val:+.2f}) with significant departure from normality.",
                    "evidence": {
                        "skewness": skew_val,
                        "mean": stats.get("mean"),
                        "median": stats.get("median"),
                    },
                    "severity": "High" if abs(skew_val) >= 2.0 else "Medium",
                    "dataset": dataset_name,
                    "columns": [col],
                    "recommended_investigation": "Use median/IQR rather than mean/std for robust summaries, or apply monotonic transforms.",
                })

        # 4. Correlation Insights
        corrs = analysis_payload.get("correlations", {})
        for rel in corrs.get("relationships", [])[:3]:
            if rel.get("strength") == "strong":
                raw_insights.append({
                    "title": f"Strong Statistical Association: `{rel.get('column_a')}` & `{rel.get('column_b')}`",
                    "category": "Correlation",
                    "finding": rel.get("statement", f"Features show a strong {rel.get('direction')} association (r = {rel.get('correlation')})."),
                    "evidence": {
                        "correlation": rel.get("correlation"),
                        "strength": rel.get("strength"),
                        "direction": rel.get("direction"),
                    },
                    "severity": "High" if abs(rel.get("correlation", 0)) >= 0.85 else "Medium",
                    "dataset": dataset_name,
                    "columns": [rel.get("column_a"), rel.get("column_b")],
                    "recommended_investigation": "Evaluate potential multi-collinearity in downstream modeling; distinguish association from causality.",
                })

        # 5. Category Insights
        cats = analysis_payload.get("categories", {})
        for tb in cats.get("top_categories", []):
            conc = tb.get("concentration_ratio_top3", 0.0)
            if conc >= 50.0:
                raw_insights.append({
                    "title": f"Segment Concentration in `{tb.get('category_column')}` ({conc}% in Top 3)",
                    "category": "Category",
                    "finding": f"The top 3 `{tb.get('category_column')}` segments account for {conc}% of `{tb.get('metric_column')}`.",
                    "evidence": {"concentration_ratio_top3": conc, "top_items": tb.get("items", [])[:3]},
                    "severity": "High" if conc >= 70.0 else "Medium",
                    "dataset": dataset_name,
                    "columns": [tb.get("category_column"), tb.get("metric_column")],
                    "recommended_investigation": "Assess customer/vendor concentration risks and identify expansion opportunities in lower-volume tiers.",
                })

        # 6. Anomaly Insights
        anom = analysis_payload.get("anomalies", {})
        anom_sum = anom.get("anomaly_summary", {})
        tot_anom = anom_sum.get("total_anomalies", 0)
        if tot_anom > 0:
            raw_insights.append({
                "title": f"Statistical Anomalies Detected ({tot_anom:,} records flagged)",
                "category": "Anomaly",
                "finding": f"Identified {tot_anom:,} anomalous observations departing from empirical normal distribution profiles.",
                "evidence": anom_sum,
                "severity": "High" if tot_anom >= 10 else "Medium",
                "dataset": dataset_name,
                "columns": anom.get("affected_columns", [])[:4],
                "recommended_investigation": "Review flagged rows in Phase 4 Anomalies workspace; apply controlled capping or winsorization if verified as measurement noise.",
            })

        # 7. Cross-Dataset Insights
        cross = analysis_payload.get("cross_dataset", {})
        if cross.get("status") == "blocked":
            raw_insights.append({
                "title": "Cross-Dataset Linkage Blocked",
                "category": "Cross-Dataset",
                "finding": "Automated join was halted to prevent analytical corruption.",
                "evidence": {"reason": cross.get("reason"), "datasets": cross.get("datasets_used")},
                "severity": "High",
                "dataset": " & ".join(cross.get("datasets_used", [])),
                "columns": cross.get("relationships_used", []),
                "recommended_investigation": "Resolve duplicate keys or confirm cardinality before proceeding.",
            })
        elif cross.get("status") == "success" and cross.get("analysis", {}).get("breakdown"):
            b_list = cross["analysis"]["breakdown"]
            top_b = b_list[0]
            raw_insights.append({
                "title": f"Cross-File Entity Performance: Leading Segment `{top_b.get('entity')}`",
                "category": "Cross-Dataset",
                "finding": f"Joined across `{cross.get('relationships_used', [''])[0]}` to reveal top segment `{top_b.get('entity')}`.",
                "evidence": {"joined_rows": cross.get("rows_after"), "leading_entity": top_b},
                "severity": "Medium",
                "dataset": " & ".join(cross.get("datasets_used", [])),
                "columns": [cross["analysis"].get("metric_column", ""), cross["analysis"].get("group_column", "")],
                "recommended_investigation": "Enrich cross-functional segmentation profiles using joined relational attributes.",
            })

        # Fallback baseline
        if not raw_insights:
            raw_insights.append({
                "title": f"Baseline Health Confirmation for `{dataset_name}`",
                "category": "Statistical",
                "finding": "Dataset exhibits balanced distributions without extreme skewness, severe missingness, or duplicate records.",
                "evidence": {"status": "normal"},
                "severity": "Low",
                "dataset": dataset_name,
                "columns": ["All Columns"],
                "recommended_investigation": "Data is ready for downstream analytical querying and modeling.",
            })

        # Sort by severity priority
        sev_rank = {"High": 0, "Medium": 1, "Low": 2}
        raw_insights.sort(key=lambda x: sev_rank.get(x.get("severity", "Low"), 3))
        return raw_insights

    @classmethod
    def ai_insight_explainer(cls, structured_context: Dict[str, Any]) -> str:
        """MODULE 9 CONTRACT: Generates human-readable narrative explanation strictly from computed results.

        Guaranteed non-hallucinatory: LLM/template strictly converts structured facts
        into coherent business English without inventing numbers or claims.
        """
        lines = ["### Executive Narrative Summary\n"]
        ds_name = structured_context.get("dataset_name", "the dataset")

        insights = structured_context.get("insights", [])
        if not insights:
            return f"Analysis completed for `{ds_name}`. All features reflect standard baseline distributions."

        lines.append(f"A comprehensive statistical audit of `{ds_name}` generated **{len(insights)} primary analytical findings**:\n")

        high_priority = [i for i in insights if (i.get("severity") == "High" if isinstance(i, dict) else i.severity == "High")]
        if high_priority:
            lines.append(f"**Critical Areas Requiring Immediate Review ({len(high_priority)}):**")
            for h in high_priority[:3]:
                title = h.get("title") if isinstance(h, dict) else h.title
                finding = h.get("finding") if isinstance(h, dict) else h.finding
                lines.append(f"- **{title}**: {finding}")
            lines.append("")

        trends = structured_context.get("trends", {})
        if isinstance(trends, dict) and trends.get("trends"):
            primary_tr = trends["trends"][0]
            lines.append(
                f"- **Chronological Trajectory:** `{primary_tr.get('column')}` showed a **{primary_tr.get('direction')}** shift "
                f"of **{primary_tr.get('change_percentage', 0.0):+.1f}%** between {primary_tr.get('start_date')} and {primary_tr.get('end_date')}."
            )

        corrs = structured_context.get("correlations", {})
        if isinstance(corrs, dict) and corrs.get("relationships"):
            top_rel = corrs["relationships"][0]
            lines.append(
                f"- **Statistical Association:** `{top_rel.get('column_a')}` and `{top_rel.get('column_b')}` exhibit a "
                f"**{top_rel.get('strength')} {top_rel.get('direction')}** association ($r = {top_rel.get('correlation'):+.2f}$). "
                f"*(Note: Reflects statistical covariance, not direct causal direction.)*"
            )

        lines.append("\n*All numerical values and percentage bounds reflect actual computed properties.*")
        return "\n".join(lines)
