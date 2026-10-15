"""Answer Generator Module for Phase 6 Natural Language Query Engine.

Generates concise, human-friendly, evidence-grounded natural language answers.
Never hallucinates, invents numbers, or creates unsupported causal assertions.
Strictly relies on deterministic execution results and evidence.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
from query.query_models import QueryIntent
from query.config import normalize_query_config


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

        return {
            "answer": f"No matching records were found in `{dataset_name}` matching your criteria.",
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
            top_row = data.iloc[0]
            top_entity = top_row[grp_col]
            metric_val = top_row.iloc[1]
            answer_text = f"**{top_entity}** has the highest {agg} `{col}` at **{metric_val:,.2f}**." if isinstance(metric_val, (int, float)) else f"**{top_entity}** leads with {agg} `{col}` of **{metric_val}**."
            key_points.append(f"Top {grp_col}: {top_entity}")
            key_points.append(f"Computed {agg}: {metric_val}")
            evidence_items.append(f"{grp_col}='{top_entity}', {agg}_{col}={metric_val}")
        else:
            val = evidence.get("computed_values", {}).get("metric_value")
            if val is None and isinstance(data, pd.DataFrame) and not data.empty:
                val = data.iloc[0, 0]
            elif val is None and isinstance(data, (int, float)):
                val = data

            if val is None:
                answer_text = f"No valid numerical values were found in `{col}` to calculate {agg}."
                limitations.append(f"Column '{col}' contains no valid numerical observations.")
                confidence_label = "Low"
                confidence_score = 0.20
            else:
                formatted_val = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)
                answer_text = f"The {agg} `{col}` is **{formatted_val}**."
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
                top_entity = data.iloc[0, 0]
                top_val = data.iloc[0, 1]
                val_str = f"{top_val:,.2f}" if isinstance(top_val, (int, float)) else str(top_val)
                if limit == 1:
                    answer_text = f"**{top_entity}** has the highest `{col}` at **{val_str}**."
                else:
                    direction = "top" if intent == QueryIntent.TOP_N.value else "bottom"
                    answer_text = f"Here are the {direction} {len(data)} `{group_by[0]}` items ranked by `{col}`. **{top_entity}** ranks first with **{val_str}**."
                for _, r in data.head(3).iterrows():
                    key_points.append(f"{r.iloc[0]}: {r.iloc[1]:,.2f}" if isinstance(r.iloc[1], (int, float)) else f"{r.iloc[0]}: {r.iloc[1]}")
                    evidence_items.append(f"{r.iloc[0]} -> {r.iloc[1]}")
            else:
                top_val = data.iloc[0][col] if col in data.columns else data.iloc[0, 0]
                val_str = f"{top_val:,.2f}" if isinstance(top_val, (int, float)) else str(top_val)
                answer_text = f"The highest `{col}` value is **{val_str}**."
                key_points.append(f"Peak value: {val_str}")
                evidence_items.append(f"Top record: {val_str}")

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
        raw_ev = evidence.get("raw_evidence", {})
        num_cols = raw_ev.get("numeric_columns", [])
        tot_cols = raw_ev.get("total_columns", len(query_result.get("columns", [])))
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
        raw_ev = evidence.get("raw_evidence", {})
        st_pair = raw_ev.get("strongest_pair", {})
        ev_msg = raw_ev.get("message") or evidence.get("message") or ""
        missing_cols = query_plan.get("metadata", {}).get("missing_columns", [])

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
        elif st_pair:
            c1 = st_pair.get("Feature A") or st_pair.get("column_a", "")
            c2 = st_pair.get("Feature B") or st_pair.get("column_b", "")
            r_val = st_pair.get("Correlation (r)") or st_pair.get("correlation", 0.0)
            strength = st_pair.get("Strength") or st_pair.get("strength", "Strong")
            answer_text = f"The strongest association is between `{c1}` and `{c2}` with a **{strength} correlation of {r_val:+.2f}**."
            key_points.append(f"Top Pair: `{c1}` & `{c2}` (r = {r_val:+.2f})")
            evidence_items.append(f"Pearson r = {r_val}")
        else:
            answer_text = f"No meaningful pairwise correlations could be computed for `{dataset_name}`."
            limitations.append("Requires at least two valid numerical columns.")

        limitations.append("Correlation does NOT imply causation. Associations reflect mathematical covariance rather than direct operational causality.")

    # 10. ANOMALY
    elif intent in (QueryIntent.ANOMALY_SUMMARY.value, QueryIntent.ANOMALY_RECORDS.value):
        raw_ev = evidence.get("raw_evidence", {})
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

    # 11. CROSS-DATASET / COMPARISON
    elif intent in (QueryIntent.CROSS_DATASET_ANALYSIS.value, QueryIntent.COMPARE_DATASETS.value):
        raw_ev = evidence.get("raw_evidence", {})
        l_ds = raw_ev.get("left_dataset", "")
        r_ds = raw_ev.get("right_dataset", "")
        rows_a = raw_ev.get("rows_after", row_count)
        answer_text = f"Successfully linked `{l_ds}` and `{r_ds}` via validated foreign key relationship. Resulted in **{rows_a:,} matching records**."
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

    # Fallback default
    else:
        answer_text = f"Query executed successfully on `{dataset_name}`. Displaying {row_count} computed records."
        key_points.append(f"Records returned: {row_count}")
        evidence_items.append(f"Row count: {row_count}")

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
