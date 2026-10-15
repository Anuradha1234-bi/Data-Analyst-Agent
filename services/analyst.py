"""Analyst Service - Intelligent Cross-Dataset Analytical Engine.

Translates natural language questions across arbitrary tabular datasets into safe,
deterministic Pandas executions with join safeguards, audit logging, and visualization synthesis.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import re
import pandas as pd
import numpy as np

from models.relationship import Relationship, JoinAudit
from services.relationship_detector import RelationshipDetector
from services.chart_generator import ChartGeneratorService
from core.session_manager import SessionManager
from tools.statistics_tool import StatisticsTool
from services.insight_service import InsightService


@dataclass
class AnalystResponse:
    """Standardized result container for Ask Analyst responses."""

    question: str
    datasets_used: List[str]
    join_info: Optional[Dict[str, Any]]
    headline: str
    summary_markdown: str
    result_df: Optional[pd.DataFrame] = None
    chart_figure: Optional[Any] = None
    confidence: str = "HIGH"
    warnings: List[str] = field(default_factory=list)
    is_safe: bool = True
    needs_confirmation: bool = False
    confirmation_options: List[Relationship] = field(default_factory=list)
    query_plan: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    structured_result: Optional[Dict[str, Any]] = None


class AnalystService:
    """Executes safe analytical queries across single or multiple datasets."""

    METRIC_KEYWORDS = [
        "sales", "revenue", "amount", "total", "price", "profit", "cost", "quantity",
        "qty", "salary", "score", "marks", "value", "balance", "count", "purchased",
    ]

    GROUP_KEYWORDS = [
        "region", "customer", "product", "category", "country", "city", "department",
        "segment", "branch", "employee", "student", "course", "month", "year", "date",
    ]

    @classmethod
    def answer_question(
        cls,
        question: str,
        datasets: Dict[str, pd.DataFrame],
        relationships: Optional[List[Relationship]] = None,
    ) -> AnalystResponse:
        """Analyze user query, identify relevant datasets, validate joins, and execute computation."""
        q_clean = question.strip()
        q_lower = q_clean.lower()

        if not datasets:
            return AnalystResponse(
                question=q_clean,
                datasets_used=[],
                join_info=None,
                headline="No Dataset Available",
                summary_markdown="Please upload at least one dataset before asking questions.",
                is_safe=False,
            )

        if relationships is None:
            relationships = RelationshipDetector.detect_all_relationships(datasets)

        # Check if query targets statistical anomalies or outliers (Phase 4)
        if any(w in q_lower for w in ["outlier", "outliers", "anomal", "unusual", "isolation forest", "iqr"]):
            anom_resp = cls._handle_anomaly_query(q_clean, q_lower, datasets)
            if anom_resp is not None:
                return anom_resp

        # Check if query targets Phase 5 Intelligent Analysis & Insights
        p5_resp = cls._handle_phase5_query(q_clean, q_lower, datasets, relationships)
        if p5_resp is not None:
            return p5_resp

        # 1. Identify query intent & target features
        intent = cls._parse_query_intent(q_lower, datasets)

        # 2. Check if sufficient data was found
        if not intent["has_sufficient_data"]:
            # Fallback to Phase 6 Intelligent Natural Language Query Engine
            try:
                from query.orchestrator import run_ask_analyst_query
                meta = SessionManager.get("dataset_metadata", {}) or {}
                if not meta and datasets:
                    from core.dataset_manager import DatasetManager
                    meta = {k: DatasetManager.extract_metadata(v, k, "CSV") for k, v in datasets.items()}
                p6_res = run_ask_analyst_query(
                    question=q_clean,
                    datasets=datasets,
                    metadata=meta,
                    cleaned_datasets=SessionManager.get("cleaned_datasets", {}),
                    phase4_results=SessionManager.get("anomaly_results", {}),
                    phase5_results=SessionManager.get_prediction_results() or SessionManager.get("phase5_analysis", {}),
                    relationships=relationships,
                    join_audit=SessionManager.get("join_audit", []),
                )
                if p6_res.get("status") in ("success", "needs_clarification"):
                    ans = p6_res.get("answer", {})
                    data_df = p6_res.get("result", {}).get("data")
                    fig = p6_res.get("visualization", {}).get("figure")
                    target_d = p6_res.get("query_plan", {}).get("dataset")
                    used_ds = [target_d] if target_d else list(datasets.keys())
                    return AnalystResponse(
                        question=q_clean,
                        datasets_used=used_ds,
                        join_info=None,
                        headline=ans.get("answer", "Query executed successfully."),
                        summary_markdown=ans.get("answer", ""),
                        result_df=data_df if isinstance(data_df, pd.DataFrame) else None,
                        chart_figure=fig,
                        confidence=str(ans.get("confidence", "HIGH")).upper(),
                        warnings=p6_res.get("warnings", []),
                        is_safe=True,
                        needs_confirmation=(p6_res.get("status") == "needs_clarification"),
                        confirmation_options=[],
                        query_plan=p6_res.get("query_plan"),
                        evidence=p6_res.get("evidence"),
                    )
            except Exception:
                pass

            missing_desc = intent.get("missing_info", "Required measure or grouping attributes")
            return AnalystResponse(
                question=q_clean,
                datasets_used=intent.get("candidate_datasets", list(datasets.keys())),
                join_info=None,
                headline="Insufficient Information",
                summary_markdown=(
                    f"I don't have enough information in the uploaded datasets to answer this question.\n\n"
                    f"**Missing information:** {missing_desc}\n\n"
                    f"Available datasets: {', '.join(datasets.keys())}"
                ),
                confidence="LOW",
                is_safe=True,
            )

        # 3. Determine if cross-dataset join is needed
        datasets_needed = intent["datasets_needed"]

        if len(datasets_needed) == 1:
            # Single-dataset analysis (no join required)
            ds_name = datasets_needed[0]
            df = datasets[ds_name]
            return cls._execute_single_dataset_analysis(
                q_clean, ds_name, df, intent
            )

        # Multi-dataset analysis: join required
        ds_left = datasets_needed[0]
        ds_right = datasets_needed[1]

        # Find candidate relationship between these two datasets
        matching_rels = [
            r for r in relationships
            if (r.source_dataset == ds_left and r.target_dataset == ds_right)
            or (r.source_dataset == ds_right and r.target_dataset == ds_left)
        ]

        if not matching_rels:
            return AnalystResponse(
                question=q_clean,
                datasets_used=datasets_needed,
                join_info=None,
                headline="No Reliable Relationship Found",
                summary_markdown=(
                    f"I couldn't find a reliable relationship between `{ds_left}` and `{ds_right}`, "
                    f"so I did not merge them automatically."
                ),
                confidence="LOW",
                is_safe=False,
            )

        # Check for ambiguity (multiple candidate keys)
        if len(matching_rels) > 1:
            recommended_rel = next((r for r in matching_rels if r.is_recommended), matching_rels[0])
            # Check if user already confirmed one
            confirmed_rel = next((r for r in matching_rels if SessionManager.is_relationship_confirmed(r.key_id)), None)
            if not confirmed_rel:
                # Ask user for confirmation
                opts_md = "\n".join([f"• `{r.source_dataset}.{r.source_column}` ↔ `{r.target_dataset}.{r.target_column}` (Confidence: {r.confidence})" for r in matching_rels])
                return AnalystResponse(
                    question=q_clean,
                    datasets_used=datasets_needed,
                    join_info=None,
                    headline="Multiple Possible Join Keys Detected",
                    summary_markdown=(
                        f"I found multiple possible relationships between `{ds_left}` and `{ds_right}`.\n\n"
                        f"**Possible joins:**\n{opts_md}\n\n"
                        f"**Recommended:** `{recommended_rel.display_name}`\n\n"
                        f"Please confirm which relationship should be used for this analysis."
                    ),
                    confidence="MEDIUM",
                    is_safe=False,
                    needs_confirmation=True,
                    confirmation_options=matching_rels,
                )
            selected_rel = confirmed_rel
        else:
            selected_rel = matching_rels[0]

        # Check confidence level safeguards
        if selected_rel.confidence == "LOW" and not SessionManager.is_relationship_confirmed(selected_rel.key_id):
            return AnalystResponse(
                question=q_clean,
                datasets_used=datasets_needed,
                join_info=None,
                headline="Join Rejected (Low Confidence)",
                summary_markdown=(
                    f"Relationship `{selected_rel.display_name}` has **LOW** confidence "
                    f"({selected_rel.value_overlap_pct}% value overlap). Cross-file join blocked automatically."
                ),
                confidence="LOW",
                warnings=selected_rel.warning_messages,
                is_safe=False,
            )

        if selected_rel.confidence == "MEDIUM" and not SessionManager.is_relationship_confirmed(selected_rel.key_id):
            return AnalystResponse(
                question=q_clean,
                datasets_used=datasets_needed,
                join_info=None,
                headline="Confirmation Required (Medium Confidence)",
                summary_markdown=(
                    f"Proposed join between `{ds_left}` and `{ds_right}` using `{selected_rel.display_name}` "
                    f"has **MEDIUM** confidence ({selected_rel.value_overlap_pct}% value overlap).\n\n"
                    f"Please confirm this relationship to proceed with the analysis."
                ),
                confidence="MEDIUM",
                warnings=selected_rel.warning_messages,
                is_safe=False,
                needs_confirmation=True,
                confirmation_options=[selected_rel],
            )

        # Execute safe join
        left_df = datasets[selected_rel.source_dataset]
        right_df = datasets[selected_rel.target_dataset]

        is_confirmed = SessionManager.is_relationship_confirmed(selected_rel.key_id)
        success, merged_df, audit, err_msg = RelationshipDetector.execute_safe_join(
            left_df=left_df,
            left_name=selected_rel.source_dataset,
            left_key=selected_rel.source_column,
            right_df=right_df,
            right_name=selected_rel.target_dataset,
            right_key=selected_rel.target_column,
            how="inner",
            confidence=selected_rel.confidence,
            user_confirmed=is_confirmed,
        )

        # Log audit record
        SessionManager.add_join_audit(audit)

        if not success or merged_df is None:
            return AnalystResponse(
                question=q_clean,
                datasets_used=datasets_needed,
                join_info=None,
                headline="Cross-Dataset Join Safeguard Triggered",
                summary_markdown=f"Cross-dataset analysis stopped: {err_msg}",
                confidence=selected_rel.confidence,
                warnings=selected_rel.warning_messages + ([err_msg] if err_msg else []),
                is_safe=False,
            )

        # Execute cross-dataset aggregation on merged temporary DataFrame
        join_info = {
            "source_dataset": selected_rel.source_dataset,
            "source_key": selected_rel.source_column,
            "target_dataset": selected_rel.target_dataset,
            "target_key": selected_rel.target_column,
            "left_dataset": selected_rel.source_dataset,
            "left_key": selected_rel.source_column,
            "right_dataset": selected_rel.target_dataset,
            "right_key": selected_rel.target_column,
            "join_type": selected_rel.relationship_type,
            "overlap_pct": selected_rel.value_overlap_pct,
            "relationship_type": selected_rel.relationship_type,
            "confidence": selected_rel.confidence,
            "rows_before": audit.rows_before,
            "rows_after": audit.rows_after,
        }

        return cls._execute_joined_analysis(
            q_clean, datasets_needed, merged_df, intent, join_info, selected_rel
        )

    # =========================================================================
    # INTENT PARSER & FEATURE MAPPING
    # =========================================================================

    @classmethod
    def _parse_query_intent(cls, q_lower: str, datasets: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Discover query aggregation type, metric column, and group column across datasets."""
        # 1. Identify aggregation function
        agg_type = "sum"
        if any(w in q_lower for w in ["average", "avg", "mean"]):
            agg_type = "mean"
        elif any(w in q_lower for w in ["count", "how many", "number of"]):
            agg_type = "count"
        elif any(w in q_lower for w in ["highest", "max", "top", "most", "largest", "greatest", "best"]):
            agg_type = "top"
        elif any(w in q_lower for w in ["lowest", "min", "bottom", "least", "smallest", "worst"]):
            agg_type = "bottom"
        elif any(w in q_lower for w in ["trend", "monthly", "yearly", "daily", "over time", "timeline"]):
            agg_type = "trend"

        # 2. Locate candidate metric columns across all datasets
        metric_candidates: List[Tuple[str, str, float]] = []  # (ds_name, col_name, score)
        for ds_name, df in datasets.items():
            for col in df.columns:
                col_l = str(col).lower()
                if pd.api.types.is_numeric_dtype(df[col]):
                    # Do not treat ID columns as metrics
                    if col_l.endswith("_id") or col_l == "id" or col_l.endswith("_code"):
                        continue
                    score = 0.0
                    for kw in cls.METRIC_KEYWORDS:
                        if kw in q_lower and kw in col_l:
                            score += 6.0
                    if col_l in q_lower:
                        score += 8.0
                    # Financial/sales/purchase synonyms match
                    purchase_terms = ["sale", "sales", "revenue", "earning", "turnover", "sold", "purchased", "purchase", "purchases", "bought", "spent", "spend", "order", "orders", "cost", "total"]
                    metric_cols = ["amount", "revenue", "sales", "total", "price", "quantity", "qty", "spend", "cost", "value"]
                    if any(s in q_lower for s in purchase_terms) and any(s in col_l for s in metric_cols):
                        score += 10.0
                    if score > 0:
                        metric_candidates.append((ds_name, col, score))

        # 3. Locate candidate grouping columns across all datasets
        group_candidates: List[Tuple[str, str, float]] = []  # (ds_name, col_name, score)
        for ds_name, df in datasets.items():
            for col in df.columns:
                col_l = str(col).lower()
                score = 0.0
                for kw in cls.GROUP_KEYWORDS:
                    if kw in q_lower and (kw in col_l or kw in ds_name.lower()):
                        score += 6.0
                if col_l in q_lower:
                    score += 8.0

                # Only apply bonuses if query actually had a match with the column or dataset
                if score > 0:
                    is_id_col = col_l.endswith("_id") or col_l == "id" or col_l.endswith("_code")
                    is_text_col = pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col])

                    if is_id_col:
                        score -= 5.0
                    if is_text_col and any(w in col_l for w in ["name", "title", "label", "category", "desc", "segment", "country", "city"]):
                        score += 7.0

                    if score > 0:
                        group_candidates.append((ds_name, col, score))

        # Date column check for trend queries
        if agg_type == "trend":
            for ds_name, df in datasets.items():
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]) or any(w in str(col).lower() for w in ["date", "time", "month", "year"]):
                        group_candidates.insert(0, (ds_name, col, 15.0))

        # If neither metric nor group found matching query keywords, return insufficient data
        if not metric_candidates or not group_candidates:
            return {
                "has_sufficient_data": False,
                "missing_info": f"Could not find columns or concepts matching '{q_lower}' in any of the uploaded datasets ({', '.join(datasets.keys())}).",
            }

        best_metric = max(metric_candidates, key=lambda x: x[2])
        best_group = max(group_candidates, key=lambda x: x[2])

        metric_ds, metric_col, _ = best_metric
        group_ds, group_col, _ = best_group

        datasets_needed = [metric_ds] if metric_ds == group_ds else [metric_ds, group_ds]

        return {
            "has_sufficient_data": True,
            "agg_type": agg_type,
            "metric_dataset": metric_ds,
            "metric_col": metric_col,
            "group_dataset": group_ds,
            "group_col": group_col,
            "datasets_needed": datasets_needed,
        }

    # =========================================================================
    # SINGLE-DATASET ANALYSIS EXECUTION
    # =========================================================================

    @classmethod
    def _execute_single_dataset_analysis(
        cls,
        question: str,
        ds_name: str,
        df: pd.DataFrame,
        intent: Dict[str, Any],
    ) -> AnalystResponse:
        """Execute analytical query on a single dataset without joins."""
        metric_col = intent["metric_col"]
        group_col = intent["group_col"]
        agg_type = intent["agg_type"]

        clean_df = df.dropna(subset=[group_col, metric_col]).copy()
        if clean_df.empty:
            return AnalystResponse(
                question=question,
                datasets_used=[ds_name],
                join_info=None,
                headline="No Non-Null Records Found",
                summary_markdown=f"Dataset `{ds_name}` has no overlapping non-null values for `{group_col}` and `{metric_col}`.",
                is_safe=True,
            )

        # Date handling for trends
        if agg_type == "trend":
            try:
                clean_df["_period"] = pd.to_datetime(clean_df[group_col], errors="coerce").dt.to_period("M").astype(str)
                agg_df = clean_df.groupby("_period")[metric_col].sum().reset_index()
                agg_df.columns = ["Month", f"Total {metric_col}"]
                agg_df = agg_df.sort_values(by="Month")
                top_period = agg_df.iloc[-1]["Month"]
                top_val = agg_df.iloc[-1][f"Total {metric_col}"]

                headline = f"Monthly Trend: {metric_col}"
                summary = (
                    f"I analyzed:\n\n"
                    f"✓ `{ds_name}`\n\n"
                    f"**Analysis:** Monthly trend of `{metric_col}`.\n"
                    f"**Latest Period:** {top_period} ({top_val:,.2f})\n"
                    f"**Total Records:** {len(clean_df):,}"
                )
                fig = ChartGeneratorService.create_line_chart(agg_df, "Month", f"Total {metric_col}", headline)
                return AnalystResponse(
                    question=question,
                    datasets_used=[ds_name],
                    join_info=None,
                    headline=headline,
                    summary_markdown=summary,
                    result_df=agg_df,
                    chart_figure=fig,
                )
            except Exception:
                pass

        # Standard categorical aggregation (sum)
        agg_df = clean_df.groupby(group_col)[metric_col].agg(["sum", "count"]).reset_index()
        agg_df.columns = [group_col, f"Total {metric_col}", "Count"]
        agg_df = agg_df.sort_values(by=f"Total {metric_col}", ascending=False).reset_index(drop=True)

        top_entity = agg_df.iloc[0][group_col]
        top_val = agg_df.iloc[0][f"Total {metric_col}"]

        headline = f"Top {group_col}: {top_entity}"
        summary = (
            f"I analyzed:\n\n"
            f"✓ `{ds_name}`\n\n"
            f"**Top {group_col}:** {top_entity}\n\n"
            f"**Total {metric_col}:** {top_val:,.2f}\n"
            f"**Records Analyzed:** {len(clean_df):,}"
        )

        fig = ChartGeneratorService.create_bar_chart(
            agg_df.head(10), group_col, f"Total {metric_col}", f"{metric_col} by {group_col}"
        )

        return AnalystResponse(
            question=question,
            datasets_used=[ds_name],
            join_info=None,
            headline=headline,
            summary_markdown=summary,
            result_df=agg_df.head(20),
            chart_figure=fig,
        )

    # =========================================================================
    # CROSS-DATASET ANALYSIS EXECUTION
    # =========================================================================

    @classmethod
    def _execute_joined_analysis(
        cls,
        question: str,
        datasets_used: List[str],
        merged_df: pd.DataFrame,
        intent: Dict[str, Any],
        join_info: Dict[str, Any],
        relationship: Relationship,
    ) -> AnalystResponse:
        """Execute analytical aggregation on validated temporary merged DataFrame."""
        metric_col = intent["metric_col"]
        group_col = intent["group_col"]

        # Ensure columns exist in merged frame
        if metric_col not in merged_df.columns or group_col not in merged_df.columns:
            # Fallback search for column names with suffix
            matching_metric = [c for c in merged_df.columns if metric_col in c]
            matching_group = [c for c in merged_df.columns if group_col in c]
            if matching_metric:
                metric_col = matching_metric[0]
            if matching_group:
                group_col = matching_group[0]

        clean_df = merged_df.dropna(subset=[group_col, metric_col]).copy()
        if clean_df.empty:
            return AnalystResponse(
                question=question,
                datasets_used=datasets_used,
                join_info=join_info,
                headline="No Non-Null Cross-File Records Found",
                summary_markdown=(
                    f"I analyzed:\n\n"
                    f"✓ `{datasets_used[0]}`\n"
                    f"✓ `{datasets_used[1]}`\n\n"
                    f"Join completed ({join_info['source_key']} → {join_info['target_key']}), "
                    f"but no non-null matching pairs exist for `{group_col}` and `{metric_col}`."
                ),
                confidence=relationship.confidence,
                is_safe=True,
            )

        # Group and aggregate
        agg_df = clean_df.groupby(group_col)[metric_col].agg(["sum", "count"]).reset_index()
        agg_df.columns = [group_col, f"Total {metric_col}", "Transactions"]
        agg_df = agg_df.sort_values(by=f"Total {metric_col}", ascending=False).reset_index(drop=True)

        top_entity = agg_df.iloc[0][group_col]
        top_val = agg_df.iloc[0][f"Total {metric_col}"]

        join_line = f"`{join_info['source_dataset']}.{join_info['source_key']}` → `{join_info['target_dataset']}.{join_info['target_key']}`"

        summary = (
            f"I analyzed:\n\n"
            f"✓ `{datasets_used[0]}`\n"
            f"✓ `{datasets_used[1]}`\n\n"
            f"**Join:** {join_line}\n"
            f"**Relationship:** {join_info['relationship_type']}\n"
            f"**Confidence:** {join_info['confidence']}\n\n"
            f"**Top {group_col}:** {top_entity}\n\n"
            f"**Total {metric_col}:** {top_val:,.2f}\n"
            f"**Records Joined:** {len(clean_df):,}"
        )

        headline = f"Top {group_col}: {top_entity} ({top_val:,.2f})"

        fig = ChartGeneratorService.create_bar_chart(
            agg_df.head(10), group_col, f"Total {metric_col}", f"{metric_col} by {group_col}"
        )

        return AnalystResponse(
            question=question,
            datasets_used=datasets_used,
            join_info=join_info,
            headline=headline,
            summary_markdown=summary,
            result_df=agg_df.head(20),
            chart_figure=fig,
            confidence=relationship.confidence,
            warnings=relationship.warning_messages,
            is_safe=True,
        )

    # =========================================================================
    # PHASE 4 ANOMALY DETECTION QUERY HANDLER
    # =========================================================================

    @classmethod
    def _handle_anomaly_query(
        cls,
        q_clean: str,
        q_lower: str,
        datasets: Dict[str, pd.DataFrame],
    ) -> Optional[AnalystResponse]:
        """Detect and execute statistical anomaly queries using actual computed results."""
        from tools.anomaly_tool import AnomalyTool

        # 1. Determine target dataset
        target_ds_name = None
        for name in datasets.keys():
            if name.lower() in q_lower:
                target_ds_name = name
                break
        if not target_ds_name:
            active_name = SessionManager.get_active_dataset_name()
            if active_name and active_name in datasets:
                target_ds_name = active_name
            elif datasets:
                target_ds_name = next(iter(datasets.keys()))

        if not target_ds_name or target_ds_name not in datasets:
            return None

        df = datasets[target_ds_name]
        suitable_cols, _, _ = AnomalyTool.identify_suitable_features(df)
        if not suitable_cols:
            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline="No Suitable Numerical Features",
                summary_markdown=f"Dataset `{target_ds_name}` does not contain suitable numeric attributes for anomaly detection.",
                confidence="HIGH",
                is_safe=True,
            )

        # 2. Check cached anomaly results in session state
        cached_results = SessionManager.get_anomaly_results(target_ds_name) or {}

        # Case A: "Which columns contain the most outliers?"
        if any(w in q_lower for w in ["most outlier", "columns with", "which column", "highest outlier"]):
            iqr_res = cached_results.get("iqr")
            if not iqr_res or not hasattr(iqr_res, "column_results"):
                iqr_res = AnomalyTool.detect_iqr_outliers(df, columns=suitable_cols, dataset_name=target_ds_name)

            rows = []
            for col, r in iqr_res.column_results.items():
                rows.append({
                    "Column": col,
                    "Total Outliers": r.total_outliers,
                    "Outlier %": r.outlier_pct,
                    "Lower Bound": r.lower_bound,
                    "Upper Bound": r.upper_bound,
                })
            res_df = pd.DataFrame(rows).sort_values(by="Total Outliers", ascending=False)
            top_col = res_df.iloc[0]["Column"] if not res_df.empty else "N/A"
            top_outliers = res_df.iloc[0]["Total Outliers"] if not res_df.empty else 0

            summary = (
                f"I evaluated IQR outlier thresholds across **{len(iqr_res.column_results)}** numerical features in `{target_ds_name}`:\n\n"
                f"- **Top Feature:** `{top_col}` has the most outliers with **{top_outliers}** records exceeding bounds.\n"
                f"- **Overall Outlier Records:** {iqr_res.total_outlier_rows:,} ({iqr_res.outlier_rate}% of dataset)."
            )
            fig = ChartGeneratorService.create_bar_chart(
                res_df.head(10), "Column", "Total Outliers", f"Outliers by Column: {target_ds_name}"
            )
            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline=f"Outlier Breakdown: {target_ds_name}",
                summary_markdown=summary,
                result_df=res_df,
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case B: "Which rows were flagged by Isolation Forest?" or query specifically for Isolation Forest
        if "isolation forest" in q_lower or "isolation" in q_lower:
            if_res = cached_results.get("isolation_forest")
            if not if_res or not hasattr(if_res, "anomaly_indices"):
                if_res = AnomalyTool.detect_isolation_forest(df, columns=suitable_cols, dataset_name=target_ds_name)

            anom_indices = if_res.anomaly_indices
            if anom_indices:
                anom_df = df.loc[anom_indices].copy()
                anom_df.insert(0, "Anomaly Status", "Anomaly")
                anom_df.insert(1, "Anomaly Score", [if_res.anomaly_scores[df.index.get_loc(idx)] for idx in anom_indices])
            else:
                anom_df = pd.DataFrame()

            summary = (
                f"Isolation Forest identified **{if_res.anomaly_count:,} anomalies** ({if_res.anomaly_pct}% of records) "
                f"across features: `{', '.join(if_res.features_used)}`.\n\n"
                f"- **Total Rows Analyzed:** {if_res.rows_analyzed:,}\n"
                f"- **Contamination Setting:** {if_res.contamination}\n"
                f"- **Thresholding:** Observations were flagged based on non-linear isolation depth."
            )
            fig = ChartGeneratorService.create_anomaly_score_histogram(
                if_res.anomaly_scores, 0.5, f"Isolation Forest Anomaly Scores ({target_ds_name})"
            )
            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline="Isolation Forest Anomalies Detected",
                summary_markdown=summary,
                result_df=anom_df.head(50) if not anom_df.empty else None,
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case C: Combinations of multiple features (e.g. "unusual price and quantity combinations")
        matched_metrics = [c for c in suitable_cols if c.lower() in q_lower]
        if len(matched_metrics) >= 2:
            mv_res = AnomalyTool.compute_multivariate_anomalies(df, columns=matched_metrics[:4], dataset_name=target_ds_name)
            anom_rows = []
            for anom in mv_res.anomalies:
                row_data = {"Row": anom.row_index, "Anomaly Score": anom.anomaly_score}
                row_data.update(anom.feature_values)
                row_data["Primary Signal"] = anom.signals[0] if anom.signals else "Joint feature deviation"
                anom_rows.append(row_data)
            res_df = pd.DataFrame(anom_rows)

            summary = (
                f"Analyzed multivariate combinations across `{', '.join(matched_metrics[:4])}` in `{target_ds_name}`:\n\n"
                f"- **Multivariate Anomalies:** {mv_res.anomaly_count:,} records ({mv_res.anomaly_pct}%)\n"
                f"- **Analysis:** Observations represent unusual feature pairings that violate normal correlation patterns."
            )
            plot_df = df.copy()
            plot_df["Status"] = "Normal"
            plot_df.loc[mv_res.all_anomaly_indices, "Status"] = "Anomaly"
            fig = ChartGeneratorService.create_anomaly_scatter(
                plot_df, matched_metrics[0], matched_metrics[1], "Status",
                f"Multivariate Outliers: {matched_metrics[0]} vs {matched_metrics[1]}"
            )
            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline=f"Unusual {matched_metrics[0]} & {matched_metrics[1]} Combinations",
                summary_markdown=summary,
                result_df=res_df.head(50),
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case D: Specific metric column outliers (e.g. "Which products have unusual prices?" or "unusual sales")
        target_metric = None
        for c in suitable_cols:
            if c.lower() in q_lower or (("price" in q_lower and "price" in c.lower()) or ("sale" in q_lower and "sale" in c.lower())):
                target_metric = c
                break
        if not target_metric:
            target_metric = suitable_cols[0]

        # Find optional grouping column (e.g. product name)
        group_col = None
        for c in df.columns:
            c_l = str(c).lower()
            if any(w in c_l for w in ["product", "item", "name", "customer", "category", "region", "title", "label"]):
                group_col = c
                break

        iqr_res = AnomalyTool.detect_iqr_outliers(df, columns=[target_metric], dataset_name=target_ds_name)
        col_res = iqr_res.column_results.get(target_metric)
        if col_res and col_res.total_outliers > 0:
            outlier_df = df.loc[col_res.outlier_indices].copy()
            display_cols = ([group_col] if group_col and group_col in outlier_df.columns else []) + [target_metric]
            other_cols = [c for c in outlier_df.columns if c not in display_cols and not str(c).lower().startswith("unnamed")][:3]
            display_cols.extend(other_cols)
            res_df = outlier_df[display_cols].sort_values(by=target_metric, ascending=False)

            summary = (
                f"Identified **{col_res.total_outliers} outlier observations** for `{target_metric}` in `{target_ds_name}`:\n\n"
                f"- **IQR Bounds:** [{col_res.lower_bound:,.2f}, {col_res.upper_bound:,.2f}] (Multiplier: {col_res.multiplier}×)\n"
                f"- **Lower Outliers:** {col_res.lower_outliers_count}\n"
                f"- **Upper Outliers:** {col_res.upper_outliers_count}\n"
                f"- **Extreme Values:** Min {col_res.min_val:,.2f}, Max {col_res.max_val:,.2f}"
            )
            fig = ChartGeneratorService.create_box_plot(
                df, target_metric, f"Outlier Distribution for {target_metric} ({target_ds_name})"
            )
            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline=f"Unusual Records for '{target_metric}'",
                summary_markdown=summary,
                result_df=res_df.head(50),
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case E: Generic "How many anomalies were detected?" / "Any outliers?"
        total_iqr = AnomalyTool.detect_iqr_outliers(df, columns=suitable_cols, dataset_name=target_ds_name)
        summary = (
            f"Evaluated all **{len(suitable_cols)}** suitable numerical features in `{target_ds_name}`:\n\n"
            f"- **Rows Flagged with Outliers:** {total_iqr.total_outlier_rows:,} ({total_iqr.outlier_rate}%)\n"
            f"- **Evaluated Features:** {', '.join(suitable_cols)}\n"
            f"- **Status:** Controlled treatments can be configured in the **Anomalies** workspace."
        )
        col_summary = [
            {"Column": c, "Outliers": r.total_outliers, "Rate": f"{r.outlier_pct}%", "Bounds": f"[{r.lower_bound:,.1f}, {r.upper_bound:,.1f}]"}
            for c, r in total_iqr.column_results.items()
        ]
        res_df = pd.DataFrame(col_summary).sort_values(by="Outliers", ascending=False)
        fig = ChartGeneratorService.create_bar_chart(res_df.head(10), "Column", "Outliers", f"Outlier Counts by Column ({target_ds_name})")
        return AnalystResponse(
            question=q_clean,
            datasets_used=[target_ds_name],
            join_info=None,
            headline=f"Anomaly & Outlier Summary for {target_ds_name}",
            summary_markdown=summary,
            result_df=res_df,
            chart_figure=fig,
            confidence="HIGH",
            is_safe=True,
        )

    # =========================================================================
    # PHASE 5 INTELLIGENT ANALYSIS & INSIGHT QUERY DISPATCHER
    # =========================================================================

    @classmethod
    def _handle_phase5_query(
        cls,
        q_clean: str,
        q_lower: str,
        datasets: Dict[str, pd.DataFrame],
        relationships: Optional[List[Relationship]] = None,
    ) -> Optional[AnalystResponse]:
        """Detect and execute Phase 5 queries (insights, trends, correlations, top/bottom, compare)."""
        # Resolve target dataset
        target_ds_name = None
        for name in datasets.keys():
            if name.lower() in q_lower:
                target_ds_name = name
                break
        if not target_ds_name:
            active_name = SessionManager.get_active_dataset_name()
            if active_name and active_name in datasets:
                target_ds_name = active_name
            elif datasets:
                target_ds_name = next(iter(datasets.keys()))

        if not target_ds_name or target_ds_name not in datasets:
            return None

        df = datasets[target_ds_name]

        # Case 1: Dataset Comparison ("Compare the datasets" / "Compare datasets")
        if any(w in q_lower for w in ["compare the datasets", "compare datasets", "cross dataset", "cross-file"]):
            comp_rows = []
            for name, d in datasets.items():
                num_cols = len(d.select_dtypes(include=["number"]).columns)
                cat_cols = len(d.select_dtypes(include=["object", "category"]).columns)
                missing = int(d.isna().sum().sum())
                dups = int(d.duplicated().sum())
                comp_rows.append({
                    "Dataset": name,
                    "Records": len(d),
                    "Columns": len(d.columns),
                    "Numeric Cols": num_cols,
                    "Categorical Cols": cat_cols,
                    "Missing Cells": missing,
                    "Duplicates": dups,
                })
            comp_df = pd.DataFrame(comp_rows)
            summary = (
                f"### Cross-Dataset Multi-File Comparison\n\n"
                f"- **Total Datasets Ingested:** {len(datasets)}\n"
                f"- **Combined Records:** {sum(len(d) for d in datasets.values()):,}\n"
                f"- **Detected Relationships:** {len(relationships or [])}\n"
            )
            fig = ChartGeneratorService.create_bar_chart(
                comp_df, "Dataset", "Records", "Record Counts Across Uploaded Datasets"
            )
            return AnalystResponse(
                question=q_clean,
                datasets_used=list(datasets.keys()),
                join_info=None,
                headline="Cross-Dataset Inventory Comparison",
                summary_markdown=summary,
                result_df=comp_df,
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case 2: Key Insights ("What are the most important insights?" / "Takeaways" / "Findings")
        if any(w in q_lower for w in ["insight", "insights", "takeaway", "takeaways", "what is happening", "key findings"]):
            analysis_res = InsightService.analyze_dataset(df, dataset_name=target_ds_name)
            insights = analysis_res.insights

            if not insights:
                return AnalystResponse(
                    question=q_clean,
                    datasets_used=[target_ds_name],
                    join_info=None,
                    headline=f"Insights for {target_ds_name}",
                    summary_markdown=f"Analysis computed for `{target_ds_name}`, but no statistically severe flags were triggered.",
                    confidence="HIGH",
                    is_safe=True,
                )

            summary_lines = [
                f"### Key Synthesized Insights for `{target_ds_name}`\n",
                f"Generated **{len(insights)} deterministic insights** across data quality, trends, distributions, and anomalies:\n",
            ]
            rows = []
            for i, ins in enumerate(insights[:6], 1):
                summary_lines.append(f"**{i}. [{ins.severity.upper()}] {ins.title}**")
                summary_lines.append(f"- **Finding:** {ins.finding}")
                summary_lines.append(f"- **Evidence:** {ins.evidence}")
                summary_lines.append(f"- **Recommendation:** {ins.recommended_investigation}\n")
                rows.append({
                    "Severity": ins.severity,
                    "Category": ins.category,
                    "Title": ins.title,
                    "Finding": ins.finding,
                    "Evidence": ins.evidence,
                })

            res_df = pd.DataFrame(rows)
            # Generate chart from top trend or category if available
            fig = None
            if analysis_res.trends and analysis_res.trends[0].timeseries_df is not None:
                tr = analysis_res.trends[0]
                fig = ChartGeneratorService.create_trend_line_chart(
                    tr.timeseries_df, tr.date_column, tr.metric_column,
                    f"Primary Trend: {tr.metric_column} over {tr.date_column}",
                    peak_date=tr.peak_date, trough_date=tr.trough_date,
                )
            elif analysis_res.top_bottom_rankings and analysis_res.top_bottom_rankings[0].top_items:
                tb = analysis_res.top_bottom_rankings[0]
                fig = ChartGeneratorService.create_top_bottom_bar_chart(
                    tb.top_items, f"Top {tb.category_column} by {tb.metric_column}"
                )

            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline=f"Key Analytical Insights: {target_ds_name}",
                summary_markdown="\n".join(summary_lines),
                result_df=res_df,
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case 3: Trends ("What are the major trends?" / "What changed over time?" / "Trend")
        if any(w in q_lower for w in ["trend", "trends", "over time", "changed over time", "time series", "growth", "decline"]):
            trends = StatisticsTool.detect_trends(df, dataset_name=target_ds_name)
            if not trends:
                return AnalystResponse(
                    question=q_clean,
                    datasets_used=[target_ds_name],
                    join_info=None,
                    headline="No Time-Series Trend Detected",
                    summary_markdown=(
                        f"No valid date/time column was detected in `{target_ds_name}` to perform chronological trend detection.\n\n"
                        f"Available columns: `{', '.join(df.columns[:8])}`"
                    ),
                    confidence="HIGH",
                    is_safe=True,
                )

            tr = trends[0]
            summary = (
                f"### Time-Series Trend Analysis: `{tr.metric_column}`\n\n"
                f"- **Overall Trajectory:** **{tr.direction}** ({tr.change_pct:+.1f}% shift)\n"
                f"- **Analyzed Interval:** `{tr.start_date}` to `{tr.end_date}` ({tr.records_analyzed:,} temporal data points)\n"
                f"- **Initial -> Final:** {tr.start_value:,.2f} -> {tr.end_value:,.2f}\n"
                f"- **Peak:** **{tr.peak_value:,.2f}** on `{tr.peak_date}`\n"
                f"- **Trough / Minimum:** **{tr.trough_value:,.2f}** on `{tr.trough_date}`\n"
            )
            if tr.sudden_changes:
                sc = tr.sudden_changes[0]
                summary += f"- **Notable Step Change:** {sc['type']} on `{sc['date']}` ({sc['change_pct']:+.1f}% shift from {sc['previous_value']:,.2f} to {sc['current_value']:,.2f}).\n"

            fig = None
            if tr.timeseries_df is not None:
                fig = ChartGeneratorService.create_trend_line_chart(
                    tr.timeseries_df, tr.date_column, tr.metric_column,
                    f"Trend in {tr.metric_column} ({tr.start_date} to {tr.end_date})",
                    peak_date=tr.peak_date, trough_date=tr.trough_date,
                )

            trend_table = pd.DataFrame([{
                "Metric": t.metric_column,
                "Direction": t.direction,
                "Change %": f"{t.change_pct:+.1f}%",
                "Start Val": t.start_value,
                "End Val": t.end_value,
                "Peak Date": t.peak_date,
                "Peak Val": t.peak_value,
            } for t in trends])

            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline=f"Chronological Trend: {tr.metric_column} in {target_ds_name}",
                summary_markdown=summary,
                result_df=trend_table,
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case 4: Correlations ("What is the strongest correlation?" / "Correlations" / "Association")
        if any(w in q_lower for w in ["correlation", "correlations", "correlated", "relationship between", "association"]):
            corr_res = StatisticsTool.analyze_correlations(df, dataset_name=target_ds_name)
            if not corr_res or not corr_res.features_analyzed:
                return AnalystResponse(
                    question=q_clean,
                    datasets_used=[target_ds_name],
                    join_info=None,
                    headline="Insufficient Features for Correlation",
                    summary_markdown=f"Dataset `{target_ds_name}` does not have 2 or more suitable numerical features to compute statistical correlation.",
                    confidence="HIGH",
                    is_safe=True,
                )

            summary_lines = [
                f"### Correlation Analysis: `{target_ds_name}`\n",
                f"Evaluated pairwise statistical associations across **{len(corr_res.features_analyzed)} numerical features**:\n",
            ]

            all_pairs = corr_res.strong_positive_pairs + corr_res.strong_negative_pairs + corr_res.moderate_pairs
            if not all_pairs:
                summary_lines.append("*No statistically significant linear correlations (|r| >= 0.40) were observed.*")
            else:
                for p in all_pairs[:5]:
                    summary_lines.append(f"- **{p.strength}:** {p.non_causal_statement}")

            summary_lines.append("\n*Note: Correlation indicates statistical association, not causal direction.*")

            pair_rows = [{
                "Feature A": p.feature_x,
                "Feature B": p.feature_y,
                "Correlation (r)": p.correlation,
                "Strength": p.strength,
            } for p in all_pairs]
            pair_df = pd.DataFrame(pair_rows)

            fig = ChartGeneratorService.create_correlation_heatmap(
                corr_res.correlation_matrix, f"Feature Correlations ({target_ds_name})"
            )

            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline=f"Statistical Associations: {target_ds_name}",
                summary_markdown="\n".join(summary_lines),
                result_df=pair_df if not pair_df.empty else None,
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case 5: Top / Bottom Performers ("Which products perform best?" / "Top markets" / "Highest revenue")
        if any(w in q_lower for w in [
            "perform best", "best performing", "perform worst", "worst performing",
            "top product", "top market", "top categor", "highest revenue", "lowest revenue", "top 5"
        ]):
            top_bottoms = StatisticsTool.analyze_top_bottom(df, dataset_name=target_ds_name)
            if not top_bottoms:
                return AnalystResponse(
                    question=q_clean,
                    datasets_used=[target_ds_name],
                    join_info=None,
                    headline="No Category-Metric Pairings Found",
                    summary_markdown=f"No suitable combination of categorical dimensions and numerical metrics was identified in `{target_ds_name}`.",
                    confidence="HIGH",
                    is_safe=True,
                )

            tb = top_bottoms[0]
            summary = (
                f"### Performance Ranking: `{tb.category_column}` by `{tb.metric_column}`\n\n"
                f"- **Top Entity:** **{tb.top_items[0]['category']}** with {tb.top_items[0]['value']:,.2f} ({tb.top_items[0]['share_pct']}% of total volume)\n"
                f"- **Top 3 Concentration:** {tb.concentration_ratio_top3}% of total `{tb.metric_column}` held by top 3 entities.\n"
                f"- **Total Categories:** {tb.total_categories}\n"
            )
            top_df = pd.DataFrame(tb.top_items)
            fig = ChartGeneratorService.create_top_bottom_bar_chart(
                tb.top_items, f"Top {tb.category_column} by {tb.metric_column} ({target_ds_name})"
            )
            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline=f"Top Performing {tb.category_column}",
                summary_markdown=summary,
                result_df=top_df,
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        # Case 6: Missing Values & Data Quality ("Which columns have the most missing values?" / "Missing")
        if any(w in q_lower for w in ["most missing", "missing value", "missing values", "null values", "data quality"]):
            missing_series = df.isna().sum()
            missing_cols = missing_series[missing_series > 0].sort_values(ascending=False)

            if missing_cols.empty:
                return AnalystResponse(
                    question=q_clean,
                    datasets_used=[target_ds_name],
                    join_info=None,
                    headline="No Missing Values",
                    summary_markdown=f"Excellent data hygiene: Dataset `{target_ds_name}` contains **zero missing values** across all {len(df.columns)} columns ({len(df):,} records).",
                    confidence="HIGH",
                    is_safe=True,
                )

            rows = [{
                "Column": col,
                "Missing Cells": cnt,
                "Missing %": round((cnt / len(df)) * 100.0, 2),
            } for col, cnt in missing_cols.items()]
            missing_df = pd.DataFrame(rows)

            top_m_col = missing_df.iloc[0]["Column"]
            top_m_cnt = missing_df.iloc[0]["Missing Cells"]
            top_m_pct = missing_df.iloc[0]["Missing %"]

            summary = (
                f"### Missing Value Audit: `{target_ds_name}`\n\n"
                f"- **Highest Missing Column:** `{top_m_col}` with **{top_m_cnt:,} null values** ({top_m_pct}%)\n"
                f"- **Columns with Missing Data:** {len(missing_cols)} out of {len(df.columns)}\n"
                f"- **Total Missing Cells:** {int(missing_series.sum()):,}\n"
            )
            fig = ChartGeneratorService.create_bar_chart(
                missing_df.head(10), "Column", "Missing Cells", f"Missing Values by Column ({target_ds_name})"
            )
            return AnalystResponse(
                question=q_clean,
                datasets_used=[target_ds_name],
                join_info=None,
                headline=f"Missing Value Audit: {target_ds_name}",
                summary_markdown=summary,
                result_df=missing_df,
                chart_figure=fig,
                confidence="HIGH",
                is_safe=True,
            )

        return None

