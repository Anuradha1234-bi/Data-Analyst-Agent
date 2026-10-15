"""Query Planner Module for Phase 6 Natural Language Query Engine.

Transforms natural language questions into deterministic, structured query plans.
Supports ambiguity identification, follow-up context resolution, and filter extraction.
Does not generate or embed arbitrary code.
"""

from typing import Dict, Any, List, Optional, Tuple
import re
from query.query_models import (
    QueryIntent,
    StructuredQueryPlan,
    QueryFilter,
)
from query.intent_detector import detect_query_intent
from query.column_resolver import (
    resolve_column,
    _extract_columns_from_metadata,
    is_metadata_column,
    filter_metadata_columns,
    RESOLVER_STOPWORDS,
)


def _extract_dataset_from_question(
    question: str,
    metadata: Dict[str, Any],
) -> Optional[str]:
    """Find if a specific dataset filename or alias is mentioned in the question."""
    q_lower = question.lower()
    for ds_name in metadata.keys():
        ds_lower = ds_name.lower()
        base_name = ds_lower.split(".")[0]
        if ds_lower in q_lower or base_name in q_lower:
            return ds_name
    return None


def _find_best_dataset_for_columns(
    target_columns: List[str],
    metadata: Dict[str, Any],
) -> Optional[str]:
    """Find which dataset contains the largest number of target columns."""
    best_ds = None
    best_count = 0

    for ds_name, meta in metadata.items():
        cols = [c.lower() for c in _extract_columns_from_metadata(meta)]
        match_count = sum(1 for col in target_columns if any(col.lower() in c for c in cols))
        if match_count > best_count:
            best_count = match_count
            best_ds = ds_name

    return best_ds if best_count > 0 else (list(metadata.keys())[0] if metadata else None)


def _extract_filters_from_question(
    question: str,
    columns: List[str],
    dataset_metadata: Any,
) -> List[Dict[str, Any]]:
    """Extract structured filters like 'price > 5000', 'where commodity is soybean', etc."""
    filters: List[Dict[str, Any]] = []
    q_lower = question.lower()

    # Numeric comparison patterns: e.g. "price > 5000", "modal_price >= 5000", "price greater than 5000"
    num_patterns = [
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?(>=|>|<=|<|==|=|!=)\s*(\d+(?:\.\d+)?)", None),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?greater than or equal to\s*(\d+(?:\.\d+)?)", ">="),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?greater than\s*(\d+(?:\.\d+)?)", ">"),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?more than\s*(\d+(?:\.\d+)?)", ">"),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?above\s*(\d+(?:\.\d+)?)", ">"),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?less than or equal to\s*(\d+(?:\.\d+)?)", "<="),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?less than\s*(\d+(?:\.\d+)?)", "<"),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?below\s*(\d+(?:\.\d+)?)", "<"),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?equal to\s*(\d+(?:\.\d+)?)", "=="),
    ]

    for pattern, override_op in num_patterns:
        matches = re.finditer(pattern, q_lower)
        for m in matches:
            col_part = m.group(1).strip()
            if override_op:
                op = override_op
                val_part = float(m.group(2)) if "." in m.group(2) else int(m.group(2))
            else:
                raw_op = m.group(2).strip()
                op = "==" if raw_op == "=" else raw_op
                val_part = float(m.group(3)) if "." in m.group(3) else int(m.group(3))

            # Clean leading conversational text like "show me records where", "where", "with"
            col_candidate = re.split(r"\b(?:where|having|with|for|that|which|records|rows|data|items)\b", col_part)[-1].strip()
            col_clean = re.sub(r"^(where|and|with|having|for)\s+", "", col_candidate).strip()
            res = resolve_column(col_clean, dataset_metadata)
            if not res["resolved"] and col_clean != col_part:
                res = resolve_column(col_part, dataset_metadata)
            if res["resolved"] and res["column"]:
                filters.append({
                    "column": res["column"],
                    "operator": op,
                    "value": val_part,
                })

    # Equality / membership filter for categories:
    # e.g., "for soybean", "where commodity is soybean", "commodity == 'Soybean'"
    cat_patterns = [
        r"(?:where|for|with)\s+([a-zA-Z0-9_]+)\s*(?:is|==|=)\s*['\"]?([a-zA-Z0-9_\s]+?)['\"]?(?:\s+(?:and|where|order|group)|$)",
        r"(?:for|in)\s+([a-zA-Z0-9_]+)\s+(['\"][a-zA-Z0-9_\s]+['\"])",
    ]
    for pattern in cat_patterns:
        for m in re.finditer(pattern, question, re.IGNORECASE):
            col_part = m.group(1).strip()
            val_part = m.group(2).strip().strip("'\"")
            res = resolve_column(col_part, dataset_metadata)
            if res["resolved"] and res["column"]:
                # Avoid duplicate filter on same column
                if not any(f["column"] == res["column"] for f in filters):
                    filters.append({
                        "column": res["column"],
                        "operator": "==",
                        "value": val_part,
                    })

    # Specific commodity/entity check if question says "for soybean" without column name
    # Check if a known categorical column has a potential value match in question
    if not filters and "for " in q_lower:
        match_for = re.search(r"\bfor\s+([a-zA-Z0-9_]+)\b", q_lower)
        if match_for:
            entity_val = match_for.group(1).strip()
            if entity_val not in ["each", "all", "the", "every"]:
                # Check categorical columns in metadata
                meta_cols = _extract_columns_from_metadata(dataset_metadata)
                for c in meta_cols:
                    c_norm = c.lower()
                    if any(term in c_norm for term in ["commodity", "product", "item", "category", "market", "region"]):
                        filters.append({
                            "column": c,
                            "operator": "==",
                            "value": entity_val.title(),
                        })
                        break

    return filters


def build_query_plan(
    question: str,
    metadata: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Transform natural language question and context into a structured query plan.

    Contract:
    Returns a structured query plan dictionary conforming to StructuredQueryPlan.
    """
    if not question or not question.strip():
        plan = StructuredQueryPlan(
            intent=QueryIntent.UNKNOWN.value,
            confidence=0.0,
            needs_clarification=False,
            metadata={"error": "Empty question provided."},
        )
        return plan.to_dict()

    q_clean = question.strip()
    q_lower = q_clean.lower()

    # 1. Handle Context & Follow-Up Modifications
    prev_plan_dict = context.get("previous_query_plan") if context else None
    if prev_plan_dict and isinstance(prev_plan_dict, dict):
        prev_plan = StructuredQueryPlan.from_dict(prev_plan_dict)

        # Case A: "What about the second highest?" / "What about the 3rd highest?"
        match_rank = re.search(r"\b(second|2nd|third|3rd|fourth|4th|fifth|5th)\s+(highest|lowest|best|worst|top|bottom)\b", q_lower)
        if match_rank:
            rank_word = match_rank.group(1).lower()
            rank_map = {
                "second": 1, "2nd": 1,
                "third": 2, "3rd": 2,
                "fourth": 3, "4th": 3,
                "fifth": 4, "5th": 4,
            }
            offset = rank_map.get(rank_word, 1)
            is_desc = any(w in match_rank.group(2).lower() for w in ["highest", "best", "top"])

            new_plan = prev_plan
            new_plan.intent = QueryIntent.TOP_N.value if is_desc else QueryIntent.BOTTOM_N.value
            new_plan.sort = "descending" if is_desc else "ascending"
            new_plan.limit = 1
            new_plan.offset = offset
            new_plan.confidence = 0.95
            new_plan.metadata["follow_up"] = True
            new_plan.metadata["offset"] = offset
            return new_plan.to_dict()

        # Case B: "Make it top 5." / "Make it 10." / "Show top 5."
        match_limit = re.search(r"\b(?:make\s+it|change\s+to|show)\s+(?:top|bottom)?\s*(\d+)\b", q_lower)
        if match_limit:
            new_limit = min(int(match_limit.group(1)), 100)
            new_plan = prev_plan
            new_plan.limit = new_limit
            new_plan.offset = None
            new_plan.confidence = 0.95
            new_plan.metadata["follow_up"] = True
            return new_plan.to_dict()

    # 2. Detect Intent
    intent_res = detect_query_intent(q_clean, metadata, context)
    intent = intent_res["intent"]
    intent_confidence = intent_res["confidence"]

    # 3. Resolve Target Dataset
    explicit_ds = _extract_dataset_from_question(q_clean, metadata)
    if explicit_ds:
        target_ds = explicit_ds
    elif prev_plan_dict and prev_plan_dict.get("dataset") in metadata:
        target_ds = prev_plan_dict["dataset"]
    elif len(metadata) == 1:
        target_ds = list(metadata.keys())[0]
    else:
        # Infer dataset from keywords in question
        words = re.findall(r"[a-zA-Z_]+", q_lower)
        target_ds = _find_best_dataset_for_columns(words, metadata)

    ds_meta = metadata.get(target_ds, {}) if target_ds else {}
    available_cols = _extract_columns_from_metadata(ds_meta)

    # 4. Check Dataset Ambiguity (e.g. "Compare sales" when multiple datasets contain sales)
    if len(metadata) > 1 and not explicit_ds:
        if intent in (QueryIntent.COMPARE_DATASETS.value, QueryIntent.CROSS_DATASET_ANALYSIS.value):
            target_ds = list(metadata.keys())[0]
            secondary_ds = list(metadata.keys())[1] if len(metadata) > 1 else None
        elif any(k in q_lower for k in ["compare sales", "show sales"]) and sum(1 for m in metadata.values() if any("sales" in c.lower() for c in _extract_columns_from_metadata(m))) > 1:
            matching_ds = [d for d, m in metadata.items() if any("sales" in c.lower() for c in _extract_columns_from_metadata(m))]
            plan = StructuredQueryPlan(
                intent=intent,
                dataset=None,
                needs_clarification=True,
                clarification_question=f"Multiple datasets contain sales data ({', '.join(matching_ds)}). Which dataset would you like to analyze?",
                clarification_options=matching_ds,
                confidence=0.50,
            )
            return plan.to_dict()
    secondary_ds = None
    if intent in (QueryIntent.COMPARE_DATASETS.value, QueryIntent.CROSS_DATASET_ANALYSIS.value) and len(metadata) > 1:
        datasets_list = list(metadata.keys())
        if target_ds in datasets_list:
            other_datasets = [d for d in datasets_list if d != target_ds]
            secondary_ds = other_datasets[0] if other_datasets else None

    # 5. Column Resolution
    measure_col = None
    secondary_col = None
    group_by_cols: List[str] = []
    date_col = None
    ambiguous_column_result = None
    selection_explanation = None
    missing_requested_columns: List[str] = []

    # Special Handling for CORRELATION Intent: Extract both variables (e.g. between CGPA and Package)
    if intent == QueryIntent.CORRELATION.value:
        corr_patterns = [
            r"(?:correlation|association|relationship)\s+between\s+([a-zA-Z0-9_\s]+?)\s+and\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+)",
            r"between\s+([a-zA-Z0-9_\s]+?)\s+and\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+)",
            r"(?:correlate|compare)\s+([a-zA-Z0-9_\s]+?)\s+(?:with|and)\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+)",
        ]
        found_corr_pair = None
        for cp in corr_patterns:
            m_cp = re.search(cp, q_lower)
            if m_cp:
                cand_a = m_cp.group(1).strip()
                cand_b = m_cp.group(2).strip()
                cand_a = re.sub(r"^(the|an|a)\s+", "", cand_a).strip()
                cand_b = re.sub(r"^(the|an|a)\s+", "", cand_b).strip()
                if cand_a and cand_b and cand_a not in RESOLVER_STOPWORDS and cand_b not in RESOLVER_STOPWORDS:
                    found_corr_pair = (cand_a, cand_b)
                    break

        if found_corr_pair:
            raw_a, raw_b = found_corr_pair
            res_a = resolve_column(raw_a, ds_meta)
            res_b = resolve_column(raw_b, ds_meta)
            if res_a["resolved"] and res_a["column"]:
                measure_col = res_a["column"]
            else:
                missing_requested_columns.append(raw_a)

            if res_b["resolved"] and res_b["column"]:
                secondary_col = res_b["column"]
            else:
                missing_requested_columns.append(raw_b)

    # A. Check if question explicitly specifies a column (e.g. from clarification: "using unit_price", "use Modal_Price")
    explicit_using = re.search(r"\b(?:using|use|with column|column)\s+([a-zA-Z0-9_]+)\b", q_lower)
    if explicit_using:
        cand_name = explicit_using.group(1).strip()
        res_cand = resolve_column(cand_name, ds_meta)
        if res_cand["resolved"] and res_cand["column"]:
            measure_col = res_cand["column"]
            selection_explanation = f"Using user-specified column '{measure_col}'."

    # B. Check if question directly mentions an actual column name from dataset schema
    # Sort by length descending to match longer specific names first (e.g. 'unit_price' before 'price')
    sorted_avail = sorted(available_cols, key=len, reverse=True)
    for col in sorted_avail:
        c_low = col.lower()
        c_spaced = c_low.replace("_", " ")
        if re.search(r"\b" + re.escape(c_low) + r"\b", q_lower) or re.search(r"\b" + re.escape(c_spaced) + r"\b", q_lower):
            res_direct = resolve_column(col, ds_meta)
            if res_direct["resolved"] and res_direct["column"]:
                cand_col = res_direct["column"]
                is_num = False
                if isinstance(ds_meta, dict) and "data_types" in ds_meta and ds_meta["data_types"]:
                    dtype_s = str(ds_meta["data_types"].get(cand_col, "")).lower()
                    is_num = any(t in dtype_s for t in ["int", "float", "double", "num"])
                else:
                    # Heuristic based on typical numeric names/metrics
                    c_name_l = cand_col.lower()
                    is_num = any(t in c_name_l for t in ["price", "amount", "qty", "quantity", "sales", "revenue", "profit", "cost", "total", "score", "rate", "count", "num", "value", "salary"])

                if not measure_col and (is_num or intent in (QueryIntent.AVERAGE.value, QueryIntent.SUM.value, QueryIntent.MEDIAN.value, QueryIntent.MINIMUM.value, QueryIntent.MAXIMUM.value)):
                    measure_col = cand_col
                    if res_direct.get("selection_explanation"):
                        selection_explanation = res_direct["selection_explanation"]
                elif not is_num and cand_col != measure_col and cand_col not in group_by_cols:
                    if any(t in q_lower for t in ["by ", "per ", "for each ", "which ", "top ", "highest", "lowest", "rank", "breakdown"]):
                        group_by_cols.append(cand_col)

    # C. Check for group_by indicators: "by market", "per commodity", "by region"
    group_matches = re.findall(r"\b(?:by|per|across|for each)\s+([a-zA-Z0-9_]+)\b", q_lower)
    for gm in group_matches:
        if gm in [
            "average", "mean", "sum", "total", "max", "min", "highest", "lowest",
            "month", "year", "date", "two", "flagged", "failed", "case", "cases",
            "record", "records", "row", "rows", "each", "all", "other"
        ] or gm in RESOLVER_STOPWORDS:
            continue
        res = resolve_column(gm, ds_meta)
        if not res["resolved"] and secondary_ds and secondary_ds in metadata:
            res = resolve_column(gm, metadata[secondary_ds])
        if res["is_ambiguous"]:
            ambiguous_column_result = res
        elif res["resolved"] and res["column"]:
            if res["column"] not in group_by_cols:
                group_by_cols.append(res["column"])
            if res.get("selection_explanation") and not selection_explanation:
                selection_explanation = res["selection_explanation"]
        elif not res["resolved"] and intent in (QueryIntent.AVERAGE.value, QueryIntent.SUM.value, QueryIntent.GROUP_BY.value, QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value):
            missing_requested_columns.append(gm)

    # D. If no explicit "by ...", check if question asks "Which <category> has the highest <measure>?"
    which_match = re.search(r"\b(?:which|what)\s+([a-zA-Z0-9_]+)\s+has\b", q_lower)
    if which_match:
        cat_candidate = which_match.group(1).strip()
        res = resolve_column(cat_candidate, ds_meta)
        if not res["resolved"] and secondary_ds and secondary_ds in metadata:
            res = resolve_column(cat_candidate, metadata[secondary_ds])
        if res["resolved"] and res["column"] and res["column"] not in group_by_cols:
            group_by_cols.append(res["column"])

    # E. If question mentions Top N commodities/markets: "top 10 commodities by modal price"
    top_entity_match = re.search(r"\b(?:top|bottom)\s*(?:\d+)?\s*([a-zA-Z0-9_]+)\b", q_lower)
    if top_entity_match:
        entity_name = top_entity_match.group(1).strip()
        if entity_name not in ["records", "rows", "values", "numbers"]:
            res = resolve_column(entity_name, ds_meta)
            if not res["resolved"] and secondary_ds and secondary_ds in metadata:
                res = resolve_column(entity_name, metadata[secondary_ds])
            if res["resolved"] and res["column"] and res["column"] not in group_by_cols:
                group_by_cols.append(res["column"])

    # F. Identify measure column from semantic candidates if not yet matched directly
    if not measure_col and not ambiguous_column_result:
        measure_candidates = [
            "modal_price", "unit_price", "price", "arrival_quantity", "quantity", "sales", "revenue",
            "amount", "profit", "cost", "total", "units_sold", "salary", "score", "value"
        ]
        found_measure_words = []
        for mc in measure_candidates:
            if mc.replace("_", " ") in q_lower or mc in q_lower:
                found_measure_words.append(mc)

        if found_measure_words:
            found_measure_words.sort(key=len, reverse=True)
            for mw in found_measure_words:
                res = resolve_column(mw, ds_meta)
                if not res["resolved"] and secondary_ds and secondary_ds in metadata:
                    res = resolve_column(mw, metadata[secondary_ds])
                if res["is_ambiguous"]:
                    ambiguous_column_result = res
                    break
                elif res["resolved"] and res["column"]:
                    measure_col = res["column"]
                    if res.get("selection_explanation"):
                        selection_explanation = res["selection_explanation"]
                    break

    # G. Check for requested metric that could not be resolved (e.g. "average attendance", "sum of marks")
    if not measure_col and intent in (
        QueryIntent.AVERAGE.value,
        QueryIntent.SUM.value,
        QueryIntent.MEDIAN.value,
        QueryIntent.MINIMUM.value,
        QueryIntent.MAXIMUM.value,
    ):
        agg_metric_m = re.search(r"\b(?:average|mean|avg|median|sum|total of|minimum|lowest|min|maximum|highest|max)\s+(?:of\s+)?([a-zA-Z0-9_]+)\b", q_lower)
        if agg_metric_m:
            raw_metric = agg_metric_m.group(1).strip()
            if raw_metric not in [
                "of", "the", "a", "an", "all", "each", "records", "rows", "values",
                "numbers", "dataset", "data", "columns", "features", "value", "table"
            ] and raw_metric not in RESOLVER_STOPWORDS:
                res_m = resolve_column(raw_metric, ds_meta)
                if res_m["resolved"] and res_m["column"]:
                    measure_col = res_m["column"]
                else:
                    missing_requested_columns.append(raw_metric)

    # H. If still no measure found and no explicit missing metric identified, scan non-metadata numeric columns
    if not measure_col and not ambiguous_column_result and not missing_requested_columns:
        domain_available_cols = filter_metadata_columns(available_cols)
        for col in domain_available_cols:
            col_lower = col.lower()
            if col in group_by_cols:
                continue
            if col_lower in q_lower or _normalize_name(col) in _normalize_name(q_lower):
                res = resolve_column(col, ds_meta)
                if res["resolved"] and res["column"]:
                    measure_col = res["column"]
                    if res.get("selection_explanation"):
                        selection_explanation = res["selection_explanation"]
                    break

    # Check for Ambiguity Stop Condition:
    if ambiguous_column_result and ambiguous_column_result.get("is_ambiguous"):
        opts = ambiguous_column_result.get("clarification_options", [])
        candidates = ambiguous_column_result.get("clarification_candidates", [])
        labels = ambiguous_column_result.get("clarification_labels", [])

        if labels:
            labels_formatted = ", ".join(f"'{l}'" for l in labels)
            q_text = f"Which column should I use: {labels_formatted}?"
        else:
            opts_formatted = ", ".join(f"'{o}'" for o in opts)
            q_text = f"Which column should I use: {opts_formatted}?"

        plan = StructuredQueryPlan(
            intent=intent,
            dataset=target_ds,
            needs_clarification=True,
            clarification_question=q_text,
            clarification_options=opts,
            confidence=0.50,
            metadata={
                "clarification_candidates": candidates,
                "clarification_labels": labels,
            },
        )
        return plan.to_dict()

    # Identify Date Column
    for col in available_cols:
        col_l = col.lower()
        if any(term in col_l for term in ["date", "time", "timestamp", "month", "year", "created_at"]):
            date_col = col
            break

    # 6. Aggregation, Sort, Limit, Offset
    aggregation = None
    if intent == QueryIntent.AVERAGE.value or any(w in q_lower for w in ["average", "mean", "avg"]):
        aggregation = "mean"
    elif intent == QueryIntent.MEDIAN.value or "median" in q_lower:
        aggregation = "median"
    elif intent == QueryIntent.SUM.value or any(w in q_lower for w in ["sum", "total of", "total"]):
        aggregation = "sum"
    elif intent == QueryIntent.MINIMUM.value or any(w in q_lower for w in ["minimum", "lowest", "min"]):
        aggregation = "min"
    elif intent == QueryIntent.MAXIMUM.value or any(w in q_lower for w in ["maximum", "highest", "max"]):
        aggregation = "max"
    elif intent == QueryIntent.COUNT.value or any(w in q_lower for w in ["count", "how many"]):
        aggregation = "count"
    elif intent in (QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value):
        # Default aggregation for top_n grouping if measure present
        aggregation = "mean" if "average" in q_lower else "sum"

    # Limit and Sort
    limit = None
    sort = None
    sort_column = measure_col

    if intent == QueryIntent.TOP_N.value:
        sort = "descending"
        match_n = re.search(r"\btop\s*(\d+)\b", q_lower)
        if match_n:
            limit = min(int(match_n.group(1)), 100)
        elif any(w in q_lower for w in ["which", "what"]) and any(w in q_lower for w in ["highest", "largest", "peak", "maximum"]):
            limit = 1
        else:
            limit = 10
    elif intent == QueryIntent.BOTTOM_N.value:
        sort = "ascending"
        match_n = re.search(r"\bbottom\s*(\d+)\b", q_lower)
        if match_n:
            limit = min(int(match_n.group(1)), 100)
        elif any(w in q_lower for w in ["which", "what"]) and any(w in q_lower for w in ["lowest", "smallest", "minimum"]):
            limit = 1
        else:
            limit = 10
    elif intent == QueryIntent.SORT.value:
        sort = "ascending" if "asc" in q_lower else "descending"

    # Filters
    filters = _extract_filters_from_question(q_clean, available_cols, ds_meta)

    # Date Range Extraction
    date_range = None
    match_dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", q_clean)
    if len(match_dates) >= 2:
        date_range = {"start": match_dates[0], "end": match_dates[1]}
    elif len(match_dates) == 1:
        date_range = {"start": match_dates[0], "end": match_dates[0]}

    # Check textual date patterns like "between 1 September and 9 September"
    match_text_dates = re.search(r"between\s+([0-9]{1,2}\s+[a-zA-Z]+|\w+\s+[0-9]{1,2})\s+and\s+([0-9]{1,2}\s+[a-zA-Z]+|\w+\s+[0-9]{1,2})", q_lower)
    if match_text_dates:
        date_range = {"start": match_text_dates.group(1).strip(), "end": match_text_dates.group(2).strip()}

    # Output flags
    output_table = True
    output_chart = False
    if intent in (QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value, QueryIntent.GROUP_BY.value, QueryIntent.TREND.value, QueryIntent.CORRELATION.value):
        output_chart = True

    # Build plan
    plan = StructuredQueryPlan(
        intent=intent,
        dataset=target_ds,
        column=measure_col,
        secondary_dataset=secondary_ds,
        secondary_column=secondary_col,
        filters=filters,
        group_by=group_by_cols,
        aggregation=aggregation,
        sort=sort,
        sort_column=sort_column,
        limit=limit,
        offset=None,
        date_range=date_range,
        date_column=date_col,
        comparison=None,
        output={"table": output_table, "chart": output_chart},
        needs_clarification=False,
        metadata={
            "reason": intent_res.get("reason", ""),
            "error": intent_res.get("reason", "") if intent == QueryIntent.UNKNOWN.value else "",
            "selection_explanation": selection_explanation,
            "missing_columns": list(dict.fromkeys(missing_requested_columns)) if missing_requested_columns else [],
        },
    )

    return plan.to_dict()


def _normalize_name(name: str) -> str:
    """Helper normalization."""
    return re.sub(r"[^a-zA-Z0-9]", "", str(name).lower())
