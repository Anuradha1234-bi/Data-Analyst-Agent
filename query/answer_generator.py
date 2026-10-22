"""Answer Generator Module for Phase 6 Natural Language Query Engine.

Generates concise, human-friendly, evidence-grounded natural language answers.
Never hallucinates, invents numbers, or creates unsupported causal assertions.
Strictly relies on deterministic execution results and evidence.
"""

import re
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from query.query_models import QueryIntent
from query.config import normalize_query_config


def _is_table_only_request(question: str) -> bool:
    if not question:
        return False
    ql = question.lower()
    return any(
        term in ql for term in [
            "return only a table", "return only the table", "return only the resulting table",
            "only the resulting table", "only the table", "table only", "only a table", "only table",
            "resulting table only", "return the resulting table only",
            "2-row table", "two-row table", "2-column table", "two-column table"
        ]
    ) or bool(
        re.search(
            r"\b(?:return\s+)?only\s+(?:a\s+|the\s+)?(?:resulting\s+)?(?:\w+[- ]\w+\s+)?table\b|"
            r"\b(?:resulting\s+)?table\s+only\b|"
            r"\b(?:return\s+)?(?:only\s+)?(?:a\s+|the\s+)?(?:two|2)[ -](?:row|column)\s+table\b",
            ql,
        )
    )


def _dataframe_to_markdown_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    lines = ["| " + " | ".join(str(c) for c in df.columns) + " |"]
    lines.append("| " + " | ".join([":---" for _ in df.columns]) + " |")
    for _, r in df.iterrows():
        row_vals = []
        for v in r:
            if isinstance(v, (float, np.floating)):
                row_vals.append(f"{v:,.2f}")
            elif isinstance(v, (int, np.integer)):
                row_vals.append(f"{v:,}")
            else:
                row_vals.append(str(v))
        lines.append("| " + " | ".join(row_vals) + " |")
    return "\n".join(lines)


def generate_query_answer(
    question: str,
    query_plan: Dict[str, Any],
    query_result: Dict[str, Any],
    evidence: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate evidence-grounded natural language answer for query results.

    Contract:
    Returns:
    {
        "answer": "...",
        "key_points": [],
        "evidence": [],
        "limitations": [],
        "confidence": 0.91
    }
    """
    cfg = normalize_query_config(config)
    intent = query_plan.get("intent", QueryIntent.UNKNOWN.value)
    data = query_result.get("data")
    row_count = query_result.get("row_count", 0)
    dataset_name = evidence.get("dataset_used", "the dataset")
    source_label = evidence.get("dataset_source", "")

    # Check for empty result or error
    if query_result.get("status") == "error":
        err_msg = query_result.get("errors", ["An error occurred during query execution."])[0]
        missing_cols = query_plan.get("metadata", {}).get("missing_columns", [])
        if missing_cols or "do not exist in dataset" in err_msg or "cannot be calculated" in err_msg or "This information is not available" in err_msg:
            full_msg = err_msg if err_msg.startswith("This information is not available") else f"This information is not available in the uploaded CSV. {err_msg}"
            return {
                "answer": full_msg,
                "key_points": [err_msg],
                "evidence": [],
                "limitations": ["Required column or information is not available in the uploaded dataset schema."],
                "confidence": "Low",
            }
        return {
            "answer": f"Unable to complete query: {err_msg}",
            "key_points": [err_msg],
            "evidence": [],
            "limitations": ["Query execution encountered an error."],
            "confidence": "Low",
        }

    if row_count == 0 or data is None or (isinstance(data, pd.DataFrame) and data.empty):
        if intent in (QueryIntent.FORECAST.value, QueryIntent.PREDICTION.value, "forecast", "prediction") or str(intent).upper() in ("FORECAST", "PREDICTION"):
            raw_ev = evidence.get("raw_evidence", {}) or evidence
            notice = raw_ev.get("notice") or evidence.get("notice") or "No prediction results are available yet. Run a prediction or forecasting analysis first."
            sugg = raw_ev.get("suggestion") or evidence.get("suggestion") or "Run a prediction or forecasting analysis first."
            full_msg = f"{notice} {sugg}".strip() if sugg not in notice else notice
            return {
                "answer": full_msg,
                "key_points": ["No active prediction or forecast model results available yet."],
                "evidence": [notice],
                "limitations": ["A prediction model must be trained in the Prediction page before querying future projections."],
                "confidence": "Medium",
            }

        applied_filters = query_plan.get("filters", [])
        if applied_filters:
            f_desc = ", ".join(f"{f.get('column')} {f.get('operator')} '{f.get('value')}'" for f in applied_filters)
            return {
                "answer": f"Cannot determine from the uploaded CSV: no records match the criteria ({f_desc}). The value does not exist in the dataset.",
                "key_points": ["0 matching rows returned."],
                "evidence": ["Result set is empty after applying filters."],
                "limitations": [f"No observations satisfied filter: {f_desc}"],
                "confidence": "Medium",
            }

        return {
            "answer": f"Cannot determine from the uploaded CSV: no matching records were found in `{dataset_name}`.",
            "key_points": ["0 matching rows returned."],
            "evidence": ["Result set is empty."],
            "limitations": ["No observations satisfied the applied filters or queries."],
            "confidence": "Medium",
        }

    key_points: List[str] = []
    evidence_items: List[str] = []
    limitations: List[str] = []

    # Calculate overall confidence
    plan_conf = query_plan.get("confidence", 1.0)
    if plan_conf >= 0.85:
        confidence_label = "High"
        confidence_score = 0.95
    elif plan_conf >= 0.60:
        confidence_label = "Medium"
        confidence_score = 0.75
    else:
        confidence_label = "Low"
        confidence_score = 0.50

    answer_text = ""

    # 1. COUNT
    if intent == QueryIntent.COUNT.value:
        cnt = evidence.get("computed_values", {}).get("count")
        if cnt is None and isinstance(data, pd.DataFrame) and not data.empty:
            cnt = int(data.iloc[0, 0])
        cnt_val = cnt if cnt is not None else row_count
        col_cnt = (
            evidence.get("column_count")
            or evidence.get("raw_evidence", {}).get("column_count")
            or query_result.get("evidence", {}).get("column_count")
        )
        include_cols = query_plan.get("metadata", {}).get("include_columns", False) or col_cnt is not None
        if include_cols and col_cnt is not None:
            answer_text = f"There are **{cnt_val:,}** rows and **{col_cnt}** columns in `{dataset_name}`."
            key_points.append(f"Total Rows: {cnt_val:,}")
            key_points.append(f"Total Columns: {col_cnt}")
        else:
            answer_text = f"There are **{cnt_val:,}** records in `{dataset_name}`."
            if evidence.get("filters_applied"):
                answer_text += " matching the specified criteria."
            key_points.append(f"Total Count: {cnt_val:,}")
        evidence_items.append(f"Row count: {cnt_val:,}")

    # 2. AGGREGATIONS (AVERAGE, MEDIAN, SUM, MINIMUM, MAXIMUM)
    elif intent in (QueryIntent.AVERAGE.value, QueryIntent.MEDIAN.value, QueryIntent.SUM.value, QueryIntent.MINIMUM.value, QueryIntent.MAXIMUM.value):
        col = query_plan.get("column")
        agg = query_plan.get("aggregation") or (intent.lower() if intent else "average")
        group_by = query_plan.get("group_by", [])

        if not col or str(col).lower() == "none":
            missing_cols = query_plan.get("metadata", {}).get("missing_columns", [])
            if missing_cols:
                answer_text = f"Unable to compute {agg}: requested column(s) {', '.join(f'`{c}`' for c in missing_cols)} were not found in dataset `{dataset_name}`."
            else:
                answer_text = f"Unable to compute {agg}: no valid numerical column was specified or found in dataset `{dataset_name}`."
            limitations.append(f"Requested measure not found in schema of dataset '{dataset_name}'.")
            confidence_label = "Low"
            confidence_score = 0.20
        elif group_by and isinstance(data, pd.DataFrame) and not data.empty:
            grp_col = group_by[0]
            tbl_md = _dataframe_to_markdown_table(data)
            num_series = pd.to_numeric(data.iloc[:, 1], errors="coerce") if len(data.columns) > 1 else None
            tot_sum = float(num_series.sum()) if num_series is not None and not num_series.dropna().empty else None
            tot_str = f" (total: **{tot_sum:,.2f}**)" if tot_sum is not None and agg == "sum" else ""

            lead_entity = ""
            if num_series is not None and not num_series.dropna().empty:
                max_idx = num_series.idxmax()
                max_row = data.loc[max_idx]
                lead_entity = f" Highest: **{max_row.iloc[0]}** ({max_row.iloc[1]:,.2f})."

            answer_text = (
                f"Computed {agg} `{col}` grouped across {len(data)} `{grp_col}` categories in `{dataset_name}`{tot_str}.{lead_entity}\n\n{tbl_md}"
            )
            for _, r in data.iterrows():
                val_c = f"{r.iloc[-1]:,.2f}" if isinstance(r.iloc[-1], (float, int, np.floating, np.integer)) else str(r.iloc[-1])
                key_points.append(f"{r.iloc[0]}: {val_c}")
            if tot_sum is not None and agg == "sum":
                key_points.append(f"Total: {tot_sum:,.2f}")
            evidence_items.append(f"Grouped {len(data)} categories by '{grp_col}'")
        else:
            val = evidence.get("computed_values", {}).get("metric_value")
            if val is None and isinstance(data, pd.DataFrame) and not data.empty:
                val = data.iloc[0, 0]
            elif val is None and isinstance(data, (int, float)):
                val = data

            if val is None or (isinstance(data, pd.DataFrame) and data.empty):
                if query_plan.get("filters"):
                    filter_str = ", ".join(f"{f.get('column')} == '{f.get('value')}'" for f in query_plan.get("filters", []))
                    answer_text = f"Cannot determine from the uploaded CSV: 0 records matched the filter criteria ({filter_str}) in `{dataset_name}`."
                    key_points.append("0 matching rows in dataset.")
                else:
                    answer_text = f"No valid numerical values were found in `{col}` to calculate {agg}."
                limitations.append("Query returned 0 valid observations.")
                confidence_label = "Low"
                confidence_score = 0.20
            else:
                formatted_val = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)
                filt_note = ""
                if query_plan.get("filters"):
                    filt_note = f" for {', '.join(str(f.get('value')) for f in query_plan.get('filters', []))}"
                answer_text = f"The {agg} `{col}`{filt_note} is **{formatted_val}** in `{dataset_name}`."
                key_points.append(f"{agg.title()} {col}: {formatted_val}")
                evidence_items.append(f"Computed value: {formatted_val}")

    # 3. TOP_N & BOTTOM_N
    elif intent in (QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value):
        offset = query_plan.get("offset")
        limit = query_plan.get("limit", 10)
        group_by = query_plan.get("group_by", [])
        col = query_plan.get("column", "value")

        if isinstance(data, pd.DataFrame) and not data.empty:
            if offset and offset > 0:
                # Rank offset (e.g. "second highest")
                top_row = data.iloc[0]
                entity_label = top_row.iloc[0]
                metric_val = top_row.iloc[1] if len(top_row) > 1 else top_row.iloc[0]
                rank_str = "second highest" if offset == 1 else ("third highest" if offset == 2 else f"rank {offset + 1}")
                val_str = f"{metric_val:,.2f}" if isinstance(metric_val, (int, float)) else str(metric_val)
                answer_text = f"The {rank_str} is **{entity_label}** with `{col}` of **{val_str}**."
                key_points.append(f"Rank {offset + 1}: {entity_label} ({val_str})")
                evidence_items.append(f"Offset={offset}: {entity_label} = {val_str}")
            elif group_by:
                comb_analysis = evidence.get("combination_analysis") or evidence.get("raw_evidence", {}).get("combination_analysis")
                if len(group_by) > 1 and comb_analysis:
                    top_comb_dict = comb_analysis.get("top_combination", {})
                    comb_labels = [f"{top_comb_dict.get(g)} ({g})" for g in group_by if g in top_comb_dict]
                    top_comb_str = ", ".join(comb_labels) if comb_labels else str(data.iloc[0, 0])

                    comb_rev = comb_analysis.get("combination_revenue", 0.0)
                    total_rev = comb_analysis.get("total_valid_revenue", 0.0)
                    contrib_pct = comb_analysis.get("contribution_pct", 0.0)
                    curr_sym = comb_analysis.get("currency_symbol", "")

                    rev_str = f"{curr_sym}{comb_rev:,.2f}"
                    tot_rev_str = f"{curr_sym}{total_rev:,.2f}"

                    orders = comb_analysis.get("order_volume", 1)
                    comb_aov = comb_analysis.get("combination_aov", 0.0)
                    overall_aov = comb_analysis.get("overall_aov", 0.0)
                    aov_str = f"{curr_sym}{comb_aov:,.2f}"
                    overall_aov_str = f"{curr_sym}{overall_aov:,.2f}"

                    driver_stmt = comb_analysis.get("driver_statement", "")
                    order_def = comb_analysis.get("order_counting_definition", "")

                    answer_text = (
                        f"The top-performing combination is **{top_comb_str}**, generating the highest total `{col}` of **{rev_str}** in `{dataset_name}`. "
                        f"This combination contributes **{contrib_pct}%** of the total valid revenue ({tot_rev_str}) across the dataset. "
                        f"{driver_stmt}"
                    )

                    key_points.append(f"Top Combination: {top_comb_str}")
                    key_points.append(f"Revenue: {rev_str} ({contrib_pct}% of total {tot_rev_str})")
                    key_points.append(f"Order Volume: {orders} order(s) (determined via {order_def})")
                    key_points.append(f"Average Order Value: {aov_str} (vs dataset overall average of {overall_aov_str})")
                    key_points.append(f"Driver Analysis: {comb_analysis.get('primary_driver', 'N/A').replace('_', ' ').title()} - {driver_stmt}")

                    evidence_items.append(f"Top Combination = {top_comb_str}")
                    evidence_items.append(f"Revenue = {rev_str} ({contrib_pct}%)")
                    evidence_items.append(f"Order Volume = {orders}, AOV = {aov_str}")

                    limitations.append(comb_analysis.get("causation_disclaimer", "Empirical association only; does not establish operational causation."))

                    missing_cols = query_plan.get("metadata", {}).get("missing_columns", [])
                    if missing_cols:
                        limitations.append(f"Unavailable requested columns: {', '.join(missing_cols)}")
                    if comb_analysis.get("missing_or_invalid_revenue_count", 0) > 0:
                        limitations.append(f"Excluded {comb_analysis['missing_or_invalid_revenue_count']} missing or non-numeric entries from revenue calculation.")
                else:
                    top_entity = data.iloc[0, 0]
                    top_val = data.iloc[0, -1] if len(data.columns) > 1 else data.iloc[0, 0]
                    val_str = f"{top_val:,.2f}" if isinstance(top_val, (int, float)) else str(top_val)
                    adj = "lowest" if intent == QueryIntent.BOTTOM_N.value else "highest"
                    agg = query_plan.get("aggregation")
                    agg_label = f"{agg} " if agg and agg not in ("sum", "None") else ("total " if agg == "sum" else "")
                    calc_note = ""
                    derived_info = query_plan.get("derived_column") or query_plan.get("metadata", {}).get("derived_column")
                    if derived_info and isinstance(derived_info, dict):
                        calc_note = f" (calculated as `{derived_info.get('formula')}`)"

                    if limit == 1:
                        verb = "generated" if any(k in str(col).lower() for k in ["sales", "revenue", "profit", "amount"]) else ("scored" if "score" in str(col).lower() or "mark" in str(col).lower() else "had")
                        answer_text = f"**{top_entity}** {verb} the {adj} {agg_label}`{col}`, amounting to **{val_str}** in `{dataset_name}`{calc_note}."
                    else:
                        direction = "top" if intent == QueryIntent.TOP_N.value else "bottom"
                        answer_text = f"Here are the {direction} {len(data)} `{group_by[0]}` items ranked by {agg_label}`{col}`{calc_note}. **{top_entity}** ranks first with **{val_str}**."
                    for _, r in data.head(3).iterrows():
                        key_points.append(f"{r.iloc[0]}: {r.iloc[-1]:,.2f}" if isinstance(r.iloc[-1], (int, float)) else f"{r.iloc[0]}: {r.iloc[-1]}")
                        evidence_items.append(f"{r.iloc[0]} -> {r.iloc[-1]}")
            else:
                top_val = data.iloc[0][col] if (col and col in data.columns) else (evidence.get("top_value") if evidence.get("top_value") is not None else data.iloc[0, 0])
                val_str = f"{top_val:,.2f}" if isinstance(top_val, (int, float)) else str(top_val)
                adj = "lowest" if intent == QueryIntent.BOTTOM_N.value else "highest"
                if col and str(col) != "None" and col != "value":
                    answer_text = f"The {adj} `{col}` value is **{val_str}**."
                else:
                    answer_text = f"The {adj} value is **{val_str}**."
                key_points.append(f"{adj.title()} value: {val_str}")
                evidence_items.append(f"{adj.title()} record: {val_str}")
        else:
            filt_info = ""
            if query_plan.get("filters"):
                filt_parts = [f"{f.get('column')} == {f.get('value')}" for f in query_plan.get("filters", [])]
                filt_info = f" with filter ({', '.join(filt_parts)})"
            answer_text = f"Cannot determine from the uploaded CSV: 0 matching records found in `{dataset_name}`{filt_info}."
            key_points.append("0 matching rows in dataset.")
            limitations.append("Query returned 0 rows.")

    # 4. MISSING VALUES
    elif intent == QueryIntent.MISSING_VALUES.value:
        raw_ev = evidence.get("raw_evidence", {})
        tot_missing = raw_ev.get("total_missing_values", 0)
        overall_pct = raw_ev.get("overall_missing_pct", 0.0)
        cols_with_missing = raw_ev.get("columns_with_missing", [])

        if tot_missing == 0:
            answer_text = f"There are **no missing values** in `{dataset_name}` (100% complete data)."
            key_points.append("Dataset is 100% complete.")
        else:
            answer_text = f"Found **{tot_missing:,} missing values** ({overall_pct}% of total cells) across {len(cols_with_missing)} columns."
            key_points.append(f"Total null cells: {tot_missing:,} ({overall_pct}%)")
            key_points.append(f"Columns affected: {', '.join(cols_with_missing[:5])}")
            for c in cols_with_missing[:3]:
                evidence_items.append(f"Column '{c}' has missing values")

    # 5. DUPLICATES
    elif intent == QueryIntent.DUPLICATES.value:
        raw_ev = evidence.get("raw_evidence", {})
        dup_count = raw_ev.get("duplicate_count", 0)
        dup_pct = raw_ev.get("duplicate_rate_pct", 0.0)
        if dup_count == 0:
            answer_text = f"There are **0 duplicate rows** in `{dataset_name}`. Every record is unique."
            key_points.append("0 duplicate rows identified.")
        else:
            answer_text = f"Identified **{dup_count:,} duplicate rows** representing **{dup_pct}%** of the dataset."
            key_points.append(f"Duplicates: {dup_count:,} ({dup_pct}%)")
            evidence_items.append(f"Duplicate count: {dup_count:,}")

    # 6. DATA TYPES
    elif intent == QueryIntent.DATA_TYPES.value:
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        num_cols = raw_ev.get("numeric_columns", [])
        tot_cols = raw_ev.get("total_columns", len(query_result.get("columns", [])))
        tot_rows = raw_ev.get("total_rows") or evidence.get("total_rows") or evidence.get("evaluated_records") or row_count
        ds_id = raw_ev.get("dataset_id") or evidence.get("dataset_id") or query_plan.get("metadata", {}).get("dataset_id")

        q_lower_ans = question.lower()
        is_table_only_ans = bool(re.search(r"\b(?:return\s+)?only\s+(?:a\s+)?(?:\w+[- ]\w+\s+)?table\b|\btable\s+only\b", q_lower_ans))
        if is_table_only_ans:
            answer_text = f"Dataset schema table for `{dataset_name}` ({tot_cols} columns)."
        elif any(term in q_lower_ans for term in ["filename", "dataset id", "row count", "column count", "metadata"]):
            id_str = f" (Dataset ID: {ds_id})" if ds_id else ""
            answer_text = (
                f"### Dataset Schema & Metadata for `{dataset_name}`{id_str}\n\n"
                f"- **Exact Filename**: `{dataset_name}`\n"
                f"- **Dataset ID**: `{ds_id if ds_id else 'Not specified'}`\n"
                f"- **Total Rows**: **{tot_rows:,}**\n"
                f"- **Total Columns**: **{tot_cols}**\n\n"
                f"The table below details all **{tot_cols} column names and data types**."
            )
            key_points.append(f"Exact Filename: `{dataset_name}`")
            if ds_id:
                key_points.append(f"Dataset ID: {ds_id}")
            key_points.append(f"Total Rows: {tot_rows:,}")
            key_points.append(f"Total Columns: {tot_cols}")
        elif isinstance(data, pd.DataFrame) and "Column Name" in data.columns:
            all_cols = data["Column Name"].tolist()
            answer_text = f"`{dataset_name}` has **{len(all_cols)} columns**: {', '.join(all_cols)}."
            key_points.append(f"Columns ({len(all_cols)}): {', '.join(all_cols)}")
            evidence_items.append(f"{len(all_cols)} columns confirmed")
        else:
            answer_text = f"`{dataset_name}` has **{tot_cols} columns**, including **{len(num_cols)} numeric columns**: {', '.join(num_cols[:5])}."
            key_points.append(f"Numeric features ({len(num_cols)}): {', '.join(num_cols[:5])}")
            evidence_items.append(f"{len(num_cols)} numeric columns confirmed")

    # 7. TREND & PERCENTAGE CHANGE
    elif intent in (QueryIntent.TREND.value, QueryIntent.PERCENTAGE_CHANGE.value):
        raw_ev = evidence.get("raw_evidence", {})
        dir_str = raw_ev.get("direction", "stable")
        pct_chg = raw_ev.get("percentage_change", 0.0)
        col = raw_ev.get("metric_column", "value")
        s_date = raw_ev.get("start_period", "")
        e_date = raw_ev.get("end_period", "")
        s_val = raw_ev.get("start_value", 0.0)
        e_val = raw_ev.get("end_value", 0.0)

        answer_text = f"`{col}` exhibited an **{dir_str} trend** ({pct_chg:+.1f}%) from **{s_date}** ({s_val:,.2f}) to **{e_date}** ({e_val:,.2f})."
        key_points.append(f"Trajectory: {dir_str.title()} ({pct_chg:+.1f}%)")
        key_points.append(f"Starting value: {s_val:,.2f} ({s_date})")
        key_points.append(f"Ending value: {e_val:,.2f} ({e_date})")
        evidence_items.append(f"Change: {s_val} -> {e_val} ({pct_chg:+.1f}%)")
        limitations.append("Trend calculation reflects empirical historical trajectory. The dataset does not establish causal operational drivers.")

    # 8. DATE COMPARISON
    elif intent == QueryIntent.DATE_COMPARISON.value:
        cmp = evidence.get("comparison_values", {})
        dt_a = cmp.get("period_a", "Period A")
        val_a = cmp.get("value_a", 0.0)
        dt_b = cmp.get("period_b", "Period B")
        val_b = cmp.get("value_b", 0.0)
        chg = cmp.get("absolute_change", 0.0)
        pct = cmp.get("percentage_change", 0.0)
        dir_w = cmp.get("direction", "changed")

        answer_text = f"Between **{dt_a}** and **{dt_b}**, the value {dir_w} by **{chg:+,.2f}** ({pct:+.1f}%), moving from **{val_a:,.2f}** to **{val_b:,.2f}**."
        key_points.append(f"Baseline ({dt_a}): {val_a:,.2f}")
        key_points.append(f"Comparison ({dt_b}): {val_b:,.2f}")
        key_points.append(f"Shift: {chg:+,.2f} ({pct:+.1f}%)")
        evidence_items.append(f"{dt_a}={val_a} -> {dt_b}={val_b}")
        limitations.append("The dataset records the numerical shift during this interval but does not record external causal factors.")

    # 9. CORRELATION
    elif intent == QueryIntent.CORRELATION.value:
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        st_pair = raw_ev.get("strongest_pair", {})
        ev_msg = raw_ev.get("message") or evidence.get("message") or ""
        missing_cols = query_plan.get("metadata", {}).get("missing_columns", [])
        col_a_ev = raw_ev.get("col_a")
        col_b_ev = raw_ev.get("col_b")
        p_r = raw_ev.get("pearson_r")
        s_rho = raw_ev.get("spearman_rho")

        if missing_cols:
            answer_text = f"Unable to compute correlation: requested column(s) {', '.join(f'`{c}`' for c in missing_cols)} do not exist in dataset `{dataset_name}`."
            limitations.append(f"Requested features {missing_cols} not present in dataset schema.")
            confidence_label = "Low"
            confidence_score = 0.20
        elif ev_msg and ("extraction metadata" in ev_msg.lower() or "insufficient" in ev_msg.lower()):
            answer_text = f"Dataset `{dataset_name}` contains extraction metadata columns but lacks domain numerical features for statistical correlation analysis."
            limitations.append("Metadata-only columns (e.g. PDF pagination, line offsets) do not represent domain metrics.")
            confidence_label = "Low"
            confidence_score = 0.20
        elif col_a_ev and col_b_ev and p_r is not None and s_rho is not None:
            n_pairs = raw_ev.get("valid_pairs_n", row_count)
            p_pval = raw_ev.get("pearson_p_value", 1.0)
            s_pval = raw_ev.get("spearman_p_value", 1.0)
            sig_p_str = "statistically significant" if raw_ev.get("pearson_significant") else "not statistically significant"
            p_pval_str = f"{p_pval:.4f}" if p_pval >= 0.0001 else "< 0.0001"
            s_pval_str = f"{s_pval:.4f}" if s_pval >= 0.0001 else "< 0.0001"

            abs_r = abs(p_r)
            if abs_r >= 0.7:
                strength_word = "Strong"
            elif abs_r >= 0.4:
                strength_word = "Moderate"
            elif abs_r >= 0.2:
                strength_word = "Weak"
            else:
                strength_word = "Negligible"

            answer_text = (
                f"Correlation analysis between `{col_a_ev}` and `{col_b_ev}` (N = {n_pairs:,} valid paired observations):\n\n"
                f"- **Pearson Correlation (r)**: `{p_r:+.4f}` (`{p_r:+.2f}`, {strength_word}) (two-sided p-value: `{p_pval_str}`, {sig_p_str} at alpha = 0.05)\n"
                f"- **Spearman Rank Correlation (rho)**: `{s_rho:+.4f}` (two-sided p-value: `{s_pval_str}`)\n\n"
                f"**Causation Caveat**: Correlation does NOT establish causation. While `{col_a_ev}` and `{col_b_ev}` exhibit "
                f"a {strength_word.lower()} statistical relationship (r = {p_r:+.4f} / {p_r:+.2f}), mathematical covariance does not prove that changes in one variable cause changes in the other. "
                f"Confounding variables (e.g., customer income, order frequency, tenure), reverse causality, or coincidence may drive this association. "
                f"Additionally, statistical significance (p < 0.05) indicates that the relationship is unlikely to be a sampling fluke, but does not prove practical or business importance."
            )
            key_points.append(f"Pair: `{col_a_ev}` & `{col_b_ev}` (N = {n_pairs:,})")
            key_points.append(f"Pearson r = {p_r:+.4f} (p = {p_pval_str})")
            key_points.append(f"Spearman rho = {s_rho:+.4f} (p = {s_pval_str})")
            key_points.append(f"Significance at alpha=0.05: {'Yes' if raw_ev.get('pearson_significant') else 'No'}")
            evidence_items.append(f"Pearson r={p_r:.4f}, p={p_pval_str}; Spearman rho={s_rho:.4f}, p={s_pval_str}; N={n_pairs}")
            limitations.append("Correlation does NOT establish causation. Statistical significance does not prove practical importance.")
        elif st_pair:
            c1 = st_pair.get("Feature A") or st_pair.get("column_a", "")
            c2 = st_pair.get("Feature B") or st_pair.get("column_b", "")
            r_val = st_pair.get("Correlation (r)") or st_pair.get("correlation", 0.0)
            strength = st_pair.get("Strength") or st_pair.get("strength", "Strong")
            answer_text = f"The strongest association is between `{c1}` and `{c2}` with a **{strength} correlation of {r_val:+.2f}**."
            key_points.append(f"Top Pair: `{c1}` & `{c2}` (r = {r_val:+.2f})")
            evidence_items.append(f"Pearson r = {r_val}")
            limitations.append("Correlation does NOT imply causation.")
        else:
            answer_text = f"No meaningful pairwise correlations could be computed for `{dataset_name}`."
            limitations.append("Requires at least two valid numerical columns.")

    # 10. ANOMALY
    elif intent in (QueryIntent.ANOMALY_SUMMARY.value, QueryIntent.ANOMALY_RECORDS.value):
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        if raw_ev.get("disagreement_explanation"):
            tgt_col = raw_ev.get("target_column", "the column")
            n_obs = raw_ev.get("valid_observations", row_count)
            iqr_cnt = raw_ev.get("iqr_outliers", 0)
            z_cnt = raw_ev.get("zscore_outliers", 0)
            overlap_cnt = raw_ev.get("overlap_count", 0)
            iqr_only_cnt = raw_ev.get("iqr_only_count", 0)
            z_only_cnt = raw_ev.get("zscore_only_count", 0)
            skew_val = raw_ev.get("skewness", 0.0)
            dis_expl = raw_ev.get("disagreement_explanation", "")
            recom = raw_ev.get("recommendation", "")

            answer_text = (
                f"Outlier detection and method comparison for `{tgt_col}` (N = {n_obs:,} observations):\n\n"
                f"- **IQR Method (Q1 - 1.5*IQR to Q3 + 1.5*IQR)**: Flagged **{iqr_cnt:,} records** [{raw_ev.get('iqr_lower_bound', 0):.2f}, {raw_ev.get('iqr_upper_bound', 0):.2f}]\n"
                f"- **Z-Score Method (|Z| > {raw_ev.get('z_threshold', 3.0):.1f})**: Flagged **{z_cnt:,} records** (mean = {raw_ev.get('mean', 0):.2f}, std = {raw_ev.get('std', 0):.2f})\n\n"
                f"### Comparison of Flagged Records\n"
                f"- **Overlapping (Both Methods)**: {overlap_cnt:,} records\n"
                f"- **IQR-Only**: {iqr_only_cnt:,} records\n"
                f"- **Z-Score-Only**: {z_only_cnt:,} records\n\n"
                f"### Method Disagreement Analysis\n"
                f"{dis_expl}\n\n"
                f"### Method Recommendation\n"
                f"{recom}"
            )
            key_points.append(f"Target Column: `{tgt_col}`")
            key_points.append(f"IQR Outliers: {iqr_cnt:,} | Z-Score Outliers: {z_cnt:,}")
            key_points.append(f"Overlap: {overlap_cnt:,} records flagged by both")
            key_points.append(f"Distribution Skewness: {skew_val:.2f}")
            evidence_items.append(f"IQR bounds: [{raw_ev.get('iqr_lower_bound', 0):.2f}, {raw_ev.get('iqr_upper_bound', 0):.2f}]")
            evidence_items.append(f"Z-Score mean={raw_ev.get('mean', 0):.2f}, std={raw_ev.get('std', 0):.2f}")
            limitations.append("Outliers reflect statistical departures from expected bounds, not necessarily corrupted records.")
        else:
            tot_anom = raw_ev.get("total_iqr_outliers", raw_ev.get("total_anomalies", 0))
            cols_anom = raw_ev.get("columns_with_anomalies", [])
            if tot_anom > 0:
                answer_text = f"Identified **{tot_anom:,} anomalous data points** across {len(cols_anom)} columns ({', '.join(cols_anom[:4])})."
                key_points.append(f"Total flagged anomalies: {tot_anom:,}")
                key_points.append(f"Columns with outliers: {', '.join(cols_anom[:4])}")
                evidence_items.append(f"{tot_anom} anomalies detected via statistical bounds")
            else:
                answer_text = f"No statistical anomalies or extreme outliers were flagged in `{dataset_name}`."
                key_points.append("0 anomalies detected within standard statistical bounds.")
            limitations.append("Outliers reflect statistical departures from expected bounds, not necessarily data errors.")

    # DATA QUALITY AUDIT
    elif intent == QueryIntent.DATA_QUALITY_AUDIT.value:
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        tot_rows = raw_ev.get("total_rows", row_count)
        tot_cols = raw_ev.get("total_columns", 0)
        n_issues = raw_ev.get("audit_issues_count", row_count)
        acc_caveat = raw_ev.get("accuracy_caveat", "Factual accuracy cannot be mathematically established without trusted ground truth.")

        answer_text = (
            f"### Comprehensive Data Quality Audit Report for `{dataset_name}`\n"
            f"Evaluated **{tot_rows:,} rows** and **{tot_cols} columns** across all 6 core data quality dimensions:\n\n"
            f"1. **Completeness**: Missing, null, and empty cell audit across all columns.\n"
            f"2. **Uniqueness**: Full-record duplicate analysis and candidate primary key collision evaluation.\n"
            f"3. **Validity**: Strict range bounds (e.g. non-negative numeric constraints) and standard ISO datetime format validation.\n"
            f"4. **Consistency**: Cross-attribute relational rule verification and categorical text casing consistency.\n"
            f"5. **Statistical Anomalies**: Numerical outlier screening using IQR (1.5×IQR) and Z-score (|Z| > 3.0) boundaries.\n"
            f"6. **Accuracy Limitations**: {acc_caveat}\n\n"
            f"Below is the itemized findings table specifying affected row counts, severity classifications, detection rules with denominators, and recommended actions."
        )
        key_points.append(f"Audit Scope: {tot_rows:,} rows across {tot_cols} columns")
        key_points.append(f"Total Quality Findings: {n_issues} itemized rows")
        key_points.append("Dimensions: Completeness, Uniqueness, Validity, Consistency, Anomalies, Accuracy")
        evidence_items.append(f"Quality audit performed across {tot_rows} observations.")
        limitations.append("Factual accuracy cannot be mathematically proven without an authoritative external ground truth or reference system.")

    # 11. CROSS-DATASET / COMPARISON
    elif intent in (QueryIntent.CROSS_DATASET_ANALYSIS.value, QueryIntent.COMPARE_DATASETS.value):
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        q_type = raw_ev.get("query_type")
        res_type = query_result.get("result_type")
        l_ds = raw_ev.get("left_dataset", "")
        r_ds = raw_ev.get("right_dataset", "")

        if res_type == "comparison" or intent == QueryIntent.COMPARE_DATASETS.value or q_type == "dataset_comparison":
            l_rows = raw_ev.get("left_rows", 0)
            r_rows = raw_ev.get("right_rows", 0)
            diff = raw_ev.get("row_count_difference", abs(l_rows - r_rows))
            common_cols = raw_ev.get("common_columns", [])
            answer_text = (
                f"Comparison between `{l_ds}` ({l_rows:,} rows) and `{r_ds}` ({r_rows:,} rows): "
                f"difference of **{diff:,}** rows. "
                f"Shared candidate join keys/columns: {', '.join(f'`{c}`' for c in common_cols) if common_cols else 'None'}."
            )
            key_points.append(f"`{l_ds}`: {l_rows:,} rows")
            key_points.append(f"`{r_ds}`: {r_rows:,} rows")
            key_points.append(f"Row Count Difference: {diff:,}")
            if common_cols:
                key_points.append(f"Common Columns: {', '.join(common_cols)}")
            evidence_items.append(f"{l_ds} ({l_rows}) vs {r_ds} ({r_rows})")
        elif q_type == "unmatched_records":
            unmatched_cnt = raw_ev.get("unmatched_count", row_count)
            key_col = raw_ev.get("key_column", "join key")
            answer_text = f"Found **{unmatched_cnt:,}** records in `{l_ds}` whose `{key_col}` has no matching entry in `{r_ds}`."
            key_points.append(f"Unmatched records: {unmatched_cnt:,}")
            key_points.append(f"Join key: `{key_col}`")
            evidence_items.append(f"Unmatched ({l_ds} not in {r_ds}): {unmatched_cnt}")
        else:
            rows_a = raw_ev.get("rows_after", row_count)
            key_col = raw_ev.get("relationship", {}).get("left_key", "key")
            answer_text = f"Successfully linked `{l_ds}` and `{r_ds}` on `{key_col}`. Resulted in **{rows_a:,} matching records**."
            key_points.append(f"Linked Datasets: `{l_ds}` ↔ `{r_ds}`")
            key_points.append(f"Matched records: {rows_a:,}")
            evidence_items.append(f"Join: {l_ds} ↔ {r_ds} (rows={rows_a})")

    # 12. FORECAST & PREDICTION
    elif intent in (QueryIntent.FORECAST.value, QueryIntent.PREDICTION.value, "forecast", "prediction") or str(intent).upper() in ("FORECAST", "PREDICTION"):
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        sel_model = raw_ev.get("selected_model")
        if sel_model:
            tgt = raw_ev.get("target_column", "the target")
            m_name = raw_ev.get("metric_name", "MAE")
            m_val = raw_ev.get("metric_value", 0.0)
            first_v = raw_ev.get("first_predicted", 0.0)
            last_v = raw_ev.get("last_predicted", 0.0)
            horizon = raw_ev.get("horizon", row_count)
            conf_stmt = raw_ev.get("confidence_statement", "")
            narrative = raw_ev.get("explanation", "")
            prob_type = raw_ev.get("problem_type", "")

            first_v_str = f"{first_v:,.2f}" if isinstance(first_v, (int, float)) else str(first_v)
            last_v_str = f"{last_v:,.2f}" if isinstance(last_v, (int, float)) else str(last_v)
            m_val_str = f"{m_val:.4f}" if isinstance(m_val, (int, float)) else str(m_val)

            if prob_type == "classification":
                answer_text = f"Based on the trained **{sel_model}** model for `{tgt}` (Classification), predictions project {horizon} records (Validation {m_name}: {m_val_str})."
            elif prob_type == "time_series":
                answer_text = f"Based on the trained **{sel_model}** model for `{tgt}`, forecast projections across a **{horizon}-step horizon** project values from **{first_v_str}** to **{last_v_str}** (Validation {m_name}: {m_val_str})."
            else:
                answer_text = f"Based on the trained **{sel_model}** model for `{tgt}` (Regression), predictions across {horizon} validation points project values from **{first_v_str}** to **{last_v_str}** (Validation {m_name}: {m_val_str})."

            if narrative:
                answer_text += f"\n\n{narrative}"
            key_points.append(f"Selected Model: {sel_model} (validation {m_name} = {m_val_str})")
            key_points.append(f"Prediction Horizon: {horizon} steps")
            key_points.append(f"Range: {first_v_str} -> {last_v_str}")
            top_feats = raw_ev.get("top_features", [])
            if top_feats:
                key_points.append(f"Top influential features: {', '.join(top_feats)}")
            if conf_stmt:
                key_points.append(conf_stmt)
            evidence_items.append(f"Model: {sel_model}, {m_name}={m_val_str}")
            for lim in raw_ev.get("limitations", []):
                limitations.append(lim)
            if not limitations:
                limitations.append("Predictions reflect historical statistical patterns; unseen external shocks cannot be anticipated.")
        else:
            notice = raw_ev.get("notice") or "No prediction results are available yet. Run a prediction or forecasting analysis first."
            answer_text = notice
            key_points.append("No active prediction result available.")
    elif intent in (QueryIntent.REGRESSION.value, "REGRESSION"):
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        reg_details = raw_ev.get("regression_details") or {}
        interp = reg_details.get("interpretation") or f"Linear regression model fitted: {reg_details.get('equation', '')}"
        answer_text = interp
        key_points.append(f"Equation: {reg_details.get('equation', 'N/A')}")
        r2 = reg_details.get('r_squared', 0)
        key_points.append(f"R²: {r2} (explains {float(r2) * 100:.1f}% variance)")
        key_points.append(f"P-value: {reg_details.get('p_value', 'N/A')}")
        for lim in reg_details.get("limitations", []):
            limitations.append(lim)

    elif intent in (QueryIntent.TWO_GROUP_TEST.value, "TWO_GROUP_TEST"):
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        test_details = raw_ev.get("test_details") or {}
        interp = test_details.get("interpretation") or "Two-group hypothesis test evaluated."
        answer_text = interp
        key_points.append(f"T-statistic: {test_details.get('t_statistic')}, P-value: {test_details.get('p_value')}")
        key_points.append(f"Effect Size (Cohen's d): {test_details.get('cohens_d')}")
        key_points.append(f"Statistically Significant: {'Yes (p < 0.05)' if test_details.get('is_significant') else 'No (p >= 0.05)'}")
        for lim in test_details.get("limitations", []):
            limitations.append(lim)

    elif intent in (QueryIntent.CHI_SQUARE.value, "CHI_SQUARE"):
        raw_ev = evidence.get("raw_evidence", {}) or evidence
        chi_details = raw_ev.get("chi_details") or {}
        interp = chi_details.get("interpretation") or "Chi-square test of independence evaluated."
        answer_text = interp
        key_points.append(f"Chi² Statistic: {chi_details.get('chi2_statistic')}, dof: {chi_details.get('degrees_of_freedom')}")
        key_points.append(f"P-value: {chi_details.get('p_value')}, Cramér's V: {chi_details.get('cramers_v')}")
        limitations.append("Chi-square evaluates non-parametric categorical association, not causality.")

    elif intent in (QueryIntent.DESCRIPTIVE_STATISTICS.value, "DESCRIPTIVE_STATISTICS"):
        col = query_plan.get("column")
        if isinstance(data, pd.DataFrame) and not data.empty and "Feature" in data.columns:
            row_f = data.iloc[0]
            feat = row_f.get("Feature", col or "Feature")
            mean_v = row_f.get("mean")
            std_v = row_f.get("std")
            min_v = row_f.get("min")
            max_v = row_f.get("max")
            med_v = row_f.get("50%")
            answer_text = (
                f"Statistical distribution for `{feat}` in `{dataset_name}`: "
                f"Mean is **{mean_v}**, Median is **{med_v}**, Min is **{min_v}**, Max is **{max_v}** (Std Dev: **{std_v}**)."
            )
            key_points.append(f"Mean: {mean_v}, Median: {med_v}")
            key_points.append(f"Range: [{min_v} to {max_v}]")
            evidence_items.append(f"Feature '{feat}': mean={mean_v}, std={std_v}, min={min_v}, max={max_v}")
        else:
            answer_text = f"Computed statistical distribution for `{dataset_name}` across {row_count} metrics."
            key_points.append(f"Metrics evaluated: {row_count}")

    elif intent in (QueryIntent.GROUP_BY.value, "GROUP_BY"):
        col = query_plan.get("column")
        group_by = query_plan.get("group_by", [])
        agg = query_plan.get("aggregation") or "sum"
        grp_col = group_by[0] if group_by else "Category"
        if isinstance(data, pd.DataFrame) and not data.empty:
            top_row = data.iloc[0]
            top_entity = top_row.iloc[0]
            top_val = top_row.iloc[1] if len(top_row) > 1 else top_row.iloc[0]
            top_str = f"{top_val:,.2f}" if isinstance(top_val, (float, int, np.floating, np.integer)) else str(top_val)
            answer_text = (
                f"Computed {agg} `{col}` grouped across {len(data)} `{grp_col}` categories in `{dataset_name}`. "
                f"**{top_entity}** ranks first with **{top_str}**."
            )
            for _, r in data.head(5).iterrows():
                val_c = f"{r.iloc[-1]:,.2f}" if isinstance(r.iloc[-1], (float, int, np.floating, np.integer)) else str(r.iloc[-1])
                key_points.append(f"{r.iloc[0]}: {val_c}")
            evidence_items.append(f"Grouped {len(data)} categories by '{grp_col}'")
        else:
            answer_text = f"Query executed successfully on `{dataset_name}`. Displaying {row_count} computed records."
            key_points.append(f"Records returned: {row_count}")
            evidence_items.append(f"Row count: {row_count}")

    elif intent in (QueryIntent.SHOW_DATA.value, QueryIntent.FILTER.value):
        filt_note = ""
        if query_plan.get("filters"):
            filt_parts = [f"`{f.get('column')}` {f.get('operator')} '{f.get('value')}'" for f in query_plan.get("filters", [])]
            filt_note = f" where {' and '.join(filt_parts)}"
        answer_text = f"Displaying **{row_count}** matching records from `{dataset_name}`{filt_note}."
        key_points.append(f"Matching Records: {row_count}")
        evidence_items.append(f"Filtered rows: {row_count}")

    # Fallback default
    else:
        if isinstance(data, pd.DataFrame) and data.empty:
            filt_info = ""
            if query_plan.get("filters"):
                filt_parts = [f"{f.get('column')} == {f.get('value')}" for f in query_plan.get("filters", [])]
                filt_info = f" with filter ({', '.join(filt_parts)})"
            answer_text = f"Cannot determine from the uploaded CSV: 0 matching records found in `{dataset_name}`{filt_info}."
            key_points.append("0 matching rows in dataset.")
            limitations.append("Query returned 0 rows.")
        else:
            answer_text = f"Query executed successfully on `{dataset_name}`. Displaying {row_count} computed records."
            key_points.append(f"Records returned: {row_count}")
            evidence_items.append(f"Row count: {row_count}")

    # Check if table-only format was requested
    is_table_only_req = _is_table_only_request(question)

    if is_table_only_req:
        key_points = []
        evidence_items = []
        limitations = []
        if isinstance(data, pd.DataFrame) and not data.empty:
            answer_text = _dataframe_to_markdown_table(data)
    else:
        # Append column selection explanation if lineage established preference
        selection_expl = query_plan.get("metadata", {}).get("selection_explanation") or evidence.get("selection_explanation")
        if selection_expl and selection_expl not in key_points:
            key_points.append(selection_expl)

        # Append data source notice
        if source_label:
            evidence_items.append(source_label)

    return {
        "answer": answer_text,
        "key_points": key_points,
        "evidence": evidence_items,
        "limitations": limitations,
        "confidence": confidence_label,
        "confidence_score": confidence_score,
    }
