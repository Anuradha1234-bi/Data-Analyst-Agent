"""Evidence Extractor Module for Phase 6 Natural Language Query Engine.

Extracts grounded, factual evidence items strictly from computed query results.
Ensures zero hallucination by anchoring downstream natural language answers in real values.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


def extract_query_evidence(
    query_plan: Dict[str, Any],
    query_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract structured evidence facts from query plan and execution result.

    Contract:
    Evidence should include:
    - actual computed values
    - relevant rows
    - relevant columns
    - aggregation values
    - comparison values
    - percentages
    - date ranges
    - filters applied
    - dataset used
    """
    raw_evidence = query_result.get("evidence", {})
    data = query_result.get("data")
    columns = query_result.get("columns", [])
    row_count = query_result.get("row_count", 0)

    # 1. Extract sample rows
    relevant_rows: List[Dict[str, Any]] = []
    if isinstance(data, pd.DataFrame) and not data.empty:
        # Convert top 5 rows to native python dicts
        for _, row in data.head(5).iterrows():
            clean_row = {}
            for col in data.columns:
                val = row[col]
                if pd.isna(val):
                    clean_row[col] = None
                elif isinstance(val, (np.integer, int)):
                    clean_row[col] = int(val)
                elif isinstance(val, (np.floating, float)):
                    clean_row[col] = round(float(val), 2)
                else:
                    clean_row[col] = str(val)
            relevant_rows.append(clean_row)

    # 2. Extract computed numerical values
    computed_values: Dict[str, Any] = {}
    if "value" in raw_evidence:
        computed_values["metric_value"] = raw_evidence["value"]
    if "count" in raw_evidence:
        computed_values["count"] = raw_evidence["count"]
    if "top_value" in raw_evidence:
        computed_values["top_value"] = raw_evidence["top_value"]
    if "percentage_change" in raw_evidence:
        computed_values["percentage_change"] = raw_evidence["percentage_change"]
    if "absolute_change" in raw_evidence:
        computed_values["absolute_change"] = raw_evidence["absolute_change"]

    # If first row has numeric metrics
    if relevant_rows and not computed_values:
        first_r = relevant_rows[0]
        from query.column_resolver import is_metadata_column
        for k, v in first_r.items():
            if isinstance(v, (int, float)) and not is_metadata_column(k):
                computed_values[k] = v
        if not computed_values:
            for k, v in first_r.items():
                if isinstance(v, (int, float)):
                    computed_values[k] = v

    # 3. Aggregations & Comparisons
    aggregation_values = {
        "aggregation": query_plan.get("aggregation") or raw_evidence.get("aggregation"),
        "measure_column": query_plan.get("column"),
        "group_by": query_plan.get("group_by", []),
    }

    comparison_values = {}
    if "date_a" in raw_evidence and "date_b" in raw_evidence:
        comparison_values = {
            "period_a": raw_evidence.get("date_a"),
            "value_a": raw_evidence.get("value_a"),
            "period_b": raw_evidence.get("date_b"),
            "value_b": raw_evidence.get("value_b"),
            "absolute_change": raw_evidence.get("absolute_change"),
            "percentage_change": raw_evidence.get("percentage_change"),
            "direction": raw_evidence.get("direction"),
        }
    elif "top_group" in raw_evidence and "second_group" in raw_evidence:
        comparison_values = {
            "top_group": raw_evidence.get("top_group"),
            "top_value": raw_evidence.get("top_value"),
            "second_group": raw_evidence.get("second_group"),
            "second_value": raw_evidence.get("second_value"),
            "difference": raw_evidence.get("absolute_difference"),
        }

    # 4. Percentages
    percentages: Dict[str, Any] = {}
    for k, v in raw_evidence.items():
        if "pct" in k or "percentage" in k or "rate" in k:
            percentages[k] = v

    # 5. Compile Master Evidence Container
    dataset_name = query_plan.get("dataset") or raw_evidence.get("dataset", "dataset")

    evidence: Dict[str, Any] = {
        "dataset_used": dataset_name,
        "dataset_source": raw_evidence.get("dataset_source", f"Analysis based on {dataset_name}."),
        "intent": query_plan.get("intent"),
        "filters_applied": query_plan.get("filters", []),
        "date_ranges": query_plan.get("date_range"),
        "relevant_columns": columns,
        "computed_values": computed_values,
        "aggregation_values": aggregation_values,
        "comparison_values": comparison_values,
        "percentages": percentages,
        "relevant_rows": relevant_rows,
        "total_result_rows": row_count,
        "raw_evidence": raw_evidence,
    }

    # Pass through advanced statistical and insight containers
    for k in (
        "regression_details", "test_details", "chi_details", "correlation_analysis",
        "automated_insights", "combination_analysis", "iqr_outliers", "zscore_outliers",
        "overlap_count", "iqr_only_count", "zscore_only_count", "skewness",
        "disagreement_explanation", "recommendation", "data_quality_audit",
        "peer_n", "pearson_r", "spearman_rho", "pearson_p_value", "spearman_p_value",
        "summary_table", "col_a", "col_b", "valid_pairs_n", "causation_warning",
        "missing_pairs", "significance_threshold_alpha", "pearson_significant", "spearman_significant",
        "evaluated_records", "total_rows", "total_dataset_rows", "total_columns", "numeric_columns", "dataset_id",
    ):
        if k in raw_evidence:
            evidence[k] = raw_evidence[k]

    metadata = query_plan.get("metadata") or {}
    if metadata.get("selection_explanation"):
        evidence["selection_explanation"] = metadata["selection_explanation"]

    return evidence
