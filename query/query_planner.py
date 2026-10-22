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
from query.intent_detector import detect_query_intent, normalize_question_for_intent
from query.column_resolver import (
    resolve_column,
    _extract_columns_from_metadata,
    is_metadata_column,
    filter_metadata_columns,
    RESOLVER_STOPWORDS,
    check_derivable_metric,
)


def _extract_datasets_from_question(
    question: str,
    metadata: Dict[str, Any],
) -> List[str]:
    """Find all dataset filenames or aliases mentioned in the question, ordered by appearance."""
    q_lower = question.lower()
    matches = []
    for ds_name in metadata.keys():
        ds_lower = ds_name.lower()
        base_name = ds_lower.split(".")[0]
        pos = q_lower.find(ds_lower)
        if pos == -1:
            m = re.search(r"\b" + re.escape(base_name) + r"\b", q_lower)
            if m:
                pos = m.start()
        if pos != -1:
            matches.append((pos, ds_name))
    matches.sort(key=lambda x: x[0])
    return [m[1] for m in matches]


def _extract_dataset_from_question(
    question: str,
    metadata: Dict[str, Any],
) -> Optional[str]:
    """Find if a specific dataset filename or alias is mentioned in the question."""
    found = _extract_datasets_from_question(question, metadata)
    return found[0] if found else None


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
) -> Tuple[List[Dict[str, Any]], str]:
    """Extract structured filters like 'price > 5000', 'where commodity is soybean', subqueries, etc.
    
    Returns:
        (filters_list, filter_logic) where filter_logic is 'OR' if conditions are joined by OR, else 'AND'.
    """
    filters: List[Dict[str, Any]] = []
    q_clean = question.strip()
    q_clean_nopunct = re.sub(r"[?!.,;]+$", "", q_clean).strip()
    q_lower = q_clean_nopunct.lower()

    # Determine logical operator: check if question joins filter conditions with " or "
    filter_logic = "AND"
    if " or " in q_lower:
        filter_logic = "OR"

    meta_cols = _extract_columns_from_metadata(dataset_metadata)

    # 1. Subquery numeric filters: e.g. "total_amount greater than the average total_amount", "amount is above average"
    subquery_patterns = [
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?(>=|>|greater than or equal to|greater than|more than|above)\s+(?:the\s+)?(average|mean)(?:\s+([a-zA-Z0-9_\s]+))?", ">"),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?(<=|<|less than or equal to|less than|below)\s+(?:the\s+)?(average|mean)(?:\s+([a-zA-Z0-9_\s]+))?", "<"),
        (r"([a-zA-Z0-9_\s]+?)\s*(?:is\s+)?(==|=|equal to)\s+(?:the\s+)?(average|mean)(?:\s+([a-zA-Z0-9_\s]+))?", "=="),
    ]
    for pattern, op in subquery_patterns:
        for m in re.finditer(pattern, q_lower):
            col_part = m.group(1).strip()
            sub_col_part = m.group(4).strip() if m.group(4) else None
            col_candidate = re.split(r"\b(?:where|having|with|for|that|which|records|rows|data|items|have|has|whose)\b", col_part)[-1].strip()
            col_clean = re.sub(r"^(where|and|with|having|for|have)\s+", "", col_candidate).strip()
            res = resolve_column(col_clean, dataset_metadata)
            if not res["resolved"] and col_clean != col_part:
                res = resolve_column(col_part, dataset_metadata)
            if not res["resolved"]:
                for c in sorted(meta_cols, key=len, reverse=True):
                    if re.search(r"\b" + re.escape(c.lower()) + r"\b", col_part) or re.search(r"\b" + re.escape(c.lower().replace("_", " ")) + r"\b", col_part):
                        res = resolve_column(c, dataset_metadata)
                        if res["resolved"]:
                            break
            if res["resolved"] and res["column"]:
                sub_col = res["column"]
                if sub_col_part:
                    res_sub = resolve_column(sub_col_part, dataset_metadata)
                    if not res_sub["resolved"]:
                        for c in sorted(meta_cols, key=len, reverse=True):
                            if re.search(r"\b" + re.escape(c.lower()) + r"\b", sub_col_part) or re.search(r"\b" + re.escape(c.lower().replace("_", " ")) + r"\b", sub_col_part):
                                res_sub = resolve_column(c, dataset_metadata)
                                if res_sub["resolved"]:
                                    break
                    if res_sub["resolved"] and res_sub["column"]:
                        sub_col = res_sub["column"]
                filters.append({
                    "column": res["column"],
                    "operator": op,
                    "value": "__subquery__",
                    "subquery": {
                        "intent": "AVERAGE",
                        "column": sub_col,
                    }
                })

    # 2. Numeric comparison patterns: e.g. "price > 5000", "modal_price >= 5000", "price greater than 5000"
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

            col_candidate = re.split(r"\b(?:where|having|with|for|that|which|records|rows|data|items|have|has|whose)\b", col_part)[-1].strip()
            col_clean = re.sub(r"^(where|and|with|having|for|have)\s+", "", col_candidate).strip()
            res = resolve_column(col_clean, dataset_metadata)
            if not res["resolved"] and col_clean != col_part:
                res = resolve_column(col_part, dataset_metadata)
            if not res["resolved"]:
                for c in sorted(meta_cols, key=len, reverse=True):
                    if re.search(r"\b" + re.escape(c.lower()) + r"\b", col_part) or re.search(r"\b" + re.escape(c.lower().replace("_", " ")) + r"\b", col_part):
                        res = resolve_column(c, dataset_metadata)
                        if res["resolved"]:
                            break
            if res["resolved"] and res["column"]:
                if not any(f.get("column") == res["column"] and f.get("operator") == op and f.get("value") == val_part for f in filters):
                    filters.append({
                        "column": res["column"],
                        "operator": op,
                        "value": val_part,
                    })

    # 3. Compound OR check: "order_status is Shipped or Delivered"
    compound_or_m = re.search(r"\b([a-zA-Z0-9_]+)\s*(?:is|==|=)\s*['\"]?([a-zA-Z0-9_]+)['\"]?\s+or\s+['\"]?([a-zA-Z0-9_]+)['\"]?", q_clean_nopunct, re.IGNORECASE)
    if compound_or_m:
        c_name = compound_or_m.group(1).strip()
        v1 = compound_or_m.group(2).strip().strip("'\"")
        v2 = compound_or_m.group(3).strip().strip("'\"")
        res_comp = resolve_column(c_name, dataset_metadata)
        if not res_comp["resolved"]:
            for c in sorted(meta_cols, key=len, reverse=True):
                if re.search(r"\b" + re.escape(c.lower()) + r"\b", c_name.lower()):
                    res_comp = resolve_column(c, dataset_metadata)
                    if res_comp["resolved"]:
                        break
        if res_comp["resolved"] and res_comp["column"]:
            filter_logic = "OR"
            for v in [v1, v2]:
                if not any(f.get("column") == res_comp["column"] and f.get("value") == v for f in filters):
                    filters.append({
                        "column": res_comp["column"],
                        "operator": "==",
                        "value": v,
                    })

    # 4. Equality / membership filter for categories:
    cat_patterns = [
        r"(?:where|for|with|having|have|whose)\s+([a-zA-Z0-9_]+)\s*(?:is|==|=)\s*['\"]?([a-zA-Z0-9_\s]+?)['\"]?(?:\s+(?:and|or|where|order|group)|$)",
        r"(?:and|or)\s+([a-zA-Z0-9_]+)\s*(?:is|==|=)\s*['\"]?([a-zA-Z0-9_\s]+?)['\"]?(?:\s+(?:and|or|where|order|group)|$)",
        r"\b([a-zA-Z0-9_]+)\s*(?:is|==|=)\s*['\"]?([a-zA-Z0-9_\s]+?)['\"]?(?:\s+(?:and|or|where|order|group)|$)",
        r"(?:for|in)\s+([a-zA-Z0-9_]+)\s+(['\"][a-zA-Z0-9_\s]+['\"])",
    ]
    for pattern in cat_patterns:
        for m in re.finditer(pattern, q_clean_nopunct, re.IGNORECASE):
            col_part = m.group(1).strip()
            val_part = m.group(2).strip().strip("'\"")
            val_part = re.sub(r"[?!.,;]+$", "", val_part).strip()
            res = resolve_column(col_part, dataset_metadata)
            if not res["resolved"]:
                for c in sorted(meta_cols, key=len, reverse=True):
                    if re.search(r"\b" + re.escape(c.lower()) + r"\b", col_part.lower()):
                        res = resolve_column(c, dataset_metadata)
                        if res["resolved"]:
                            break
            if res["resolved"] and res["column"]:
                if not any(f.get("column") == res["column"] and f.get("value") == val_part for f in filters):
                    filters.append({
                        "column": res["column"],
                        "operator": "==",
                        "value": val_part,
                    })

    # 5. Prepositional entity filter patterns
    NON_FILTER_FOR_WORDS = {
        "this", "that", "these", "those", "dataset", "data", "method", "methods",
        "analysis", "record", "records", "example", "each", "all", "the", "every",
        "a", "an", "any", "some", "our", "my", "your", "its", "their", "which",
        "what", "whom", "whose", "here", "there", "now", "then", "us", "me", "you",
        "it", "them", "him", "her", "both", "either", "neither", "iqr", "zscore",
        "z_score", "outlier", "outliers", "anomaly", "anomalies", "model", "models",
        "testing", "audit", "column", "columns", "table", "tables", "metric", "metrics",
        "currently", "current", "selected", "uploaded", "active", "given", "entire",
        "whole", "file", "filename", "clean", "cleaned", "raw", "original", "category",
        "categories", "product", "products", "status", "year", "years", "order", "orders",
    }

    # Pattern A: "for [the] <col> <val>" (e.g., "for the category NotPresentCategory", "for product NonExistentGadget", "for Year 2099", "for Age 99")
    for_col_val_m = re.search(r"\b(?:for|in)\s+(?:the\s+)?([a-zA-Z0-9_]+)\s+(['\"]?[a-zA-Z0-9_\-]+['\"]?)(?:\s+(?:and|or|where|order|group)|$|[?!.,;])", q_clean_nopunct, re.IGNORECASE)
    if for_col_val_m:
        w1, w2 = for_col_val_m.group(1).strip(), for_col_val_m.group(2).strip().strip("'\"")
        res1 = resolve_column(w1, dataset_metadata)
        if res1["resolved"] and res1["column"] and w2.lower() not in NON_FILTER_FOR_WORDS:
            val2 = float(w2) if "." in w2 and w2.replace(".", "", 1).isdigit() else (int(w2) if w2.isdigit() else w2)
            if not any(f.get("column") == res1["column"] for f in filters):
                filters.append({
                    "column": res1["column"],
                    "operator": "==",
                    "value": val2,
                })

    # Pattern B: "in [the] <val> <col>" (e.g., "orders in the Electronics category", "students in the 2021 Year")
    val_col_m = re.search(r"\b(?:in|of|from|for)\s+(?:the\s+)?(['\"]?[a-zA-Z0-9_\-]+['\"]?)\s+([a-zA-Z0-9_]+)\b", q_clean_nopunct, re.IGNORECASE)
    if val_col_m:
        w1, w2 = val_col_m.group(1).strip().strip("'\""), val_col_m.group(2).strip()
        res2 = resolve_column(w2, dataset_metadata)
        if res2["resolved"] and res2["column"] and w1.lower() not in NON_FILTER_FOR_WORDS:
            val1 = float(w1) if "." in w1 and w1.replace(".", "", 1).isdigit() else (int(w1) if w1.isdigit() else w1)
            if not any(f.get("column") == res2["column"] for f in filters):
                filters.append({
                    "column": res2["column"],
                    "operator": "==",
                    "value": val1,
                })

    # Pattern C: "<col> <val>" after verbs like have/with/where/has without is/==
    # e.g., "orders have order_status Delivered"
    have_col_val_m = re.search(r"\b(?:have|with|where|has)\s+([a-zA-Z0-9_]+)\s+(['\"]?[a-zA-Z0-9_\-]+['\"]?)\b", q_clean_nopunct, re.IGNORECASE)
    if have_col_val_m:
        w1, w2 = have_col_val_m.group(1).strip(), have_col_val_m.group(2).strip().strip("'\"")
        res_have = resolve_column(w1, dataset_metadata)
        if res_have["resolved"] and res_have["column"] and w2.lower() not in NON_FILTER_FOR_WORDS:
            val2 = float(w2) if "." in w2 and w2.replace(".", "", 1).isdigit() else (int(w2) if w2.isdigit() else w2)
            if not any(f.get("column") == res_have["column"] for f in filters):
                filters.append({
                    "column": res_have["column"],
                    "operator": "==",
                    "value": val2,
                })

    STATUS_VALUES = {"delivered", "shipped", "cancelled", "processing", "pending", "returned", "active", "inactive", "paid", "unpaid"}
    CATEGORY_VALUES = {"electronics", "books", "clothing", "fashion", "home", "beauty", "grocery"}

    # Pattern D: "<val> orders/records" e.g., "for Electronics orders", "for Delivered orders"
    val_orders_m = re.search(r"\bfor\s+([a-zA-Z0-9_]+)\s+(?:orders|records|rows|students|employees|items|cases)\b", q_clean_nopunct, re.IGNORECASE)
    if val_orders_m:
        entity_v = val_orders_m.group(1).strip()
        if entity_v.lower() not in NON_FILTER_FOR_WORDS:
            matched_c = None
            if entity_v.lower() in STATUS_VALUES:
                matched_c = next((c for c in meta_cols if "status" in c.lower()), None)
            elif entity_v.lower() in CATEGORY_VALUES:
                matched_c = next((c for c in meta_cols if "category" in c.lower()), None)
            if not matched_c:
                matched_c = next((c for c in meta_cols if any(t in c.lower() for t in ["category", "status", "product", "item", "department"])), None)
            if matched_c and not any(f.get("column") == matched_c for f in filters):
                filters.append({
                    "column": matched_c,
                    "operator": "==",
                    "value": entity_v.title() if entity_v.islower() else entity_v,
                })

    # Pattern E: Implicit OR: "belong to Electronics OR Books", "belong to Delivered OR Shipped", "belong to Year 2020 OR 2021"
    implicit_or_m = re.search(r"\b(?:belong\s+to|in|are|for|of)\s+(?:([a-zA-Z0-9_]+)\s+)?['\"]?([a-zA-Z0-9_\-]+)['\"]?\s+or\s+['\"]?([a-zA-Z0-9_\-]+)['\"]?\b", q_clean_nopunct, re.IGNORECASE)
    if implicit_or_m:
        prefix_col = implicit_or_m.group(1)
        v1 = implicit_or_m.group(2).strip()
        v2 = implicit_or_m.group(3).strip()
        target_col = None
        if prefix_col:
            res_p = resolve_column(prefix_col, dataset_metadata)
            if res_p["resolved"]:
                target_col = res_p["column"]
        if not target_col:
            v_low_set = {v1.lower(), v2.lower()}
            if v_low_set & STATUS_VALUES:
                target_col = next((c for c in meta_cols if "status" in c.lower()), None)
            elif v_low_set & CATEGORY_VALUES:
                target_col = next((c for c in meta_cols if "category" in c.lower()), None)
            elif v1.isdigit() and v2.isdigit():
                target_col = next((c for c in meta_cols if any(t in c.lower() for t in ["year", "age", "year_built"])), None)
            if not target_col:
                for c in meta_cols:
                    if any(t in c.lower() for t in ["category", "status", "product", "year", "department", "type"]):
                        target_col = c
                        break
        if target_col:
            filter_logic = "OR"
            val1 = float(v1) if "." in v1 and v1.replace(".", "", 1).isdigit() else (int(v1) if v1.isdigit() else (v1.title() if v1.islower() else v1))
            val2 = float(v2) if "." in v2 and v2.replace(".", "", 1).isdigit() else (int(v2) if v2.isdigit() else (v2.title() if v2.islower() else v2))
            if not any(f.get("column") == target_col and f.get("value") == val1 for f in filters):
                filters.append({"column": target_col, "operator": "==", "value": val1})
            if not any(f.get("column") == target_col and f.get("value") == val2 for f in filters):
                filters.append({"column": target_col, "operator": "==", "value": val2})

    # Fallback commodity/entity check if question says "for soybean" without column name
    if not filters and "for " in q_lower:
        match_for = re.search(r"\bfor\s+(?:the\s+|a\s+|an\s+)?([a-zA-Z0-9_]+)\b", q_lower)
        if match_for:
            entity_val = match_for.group(1).strip()
            res_is_col = resolve_column(entity_val, dataset_metadata)
            if not res_is_col["resolved"] and entity_val.lower() not in NON_FILTER_FOR_WORDS and len(entity_val) >= 2:
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

    return filters, filter_logic


def _is_numeric_column(col_name: str, ds_meta: Dict[str, Any]) -> bool:
    """Helper to determine whether a column is numeric based on schema data_types or semantic heuristics."""
    if not col_name:
        return False
    if isinstance(ds_meta, dict) and "data_types" in ds_meta and ds_meta["data_types"]:
        dtype_s = str(ds_meta["data_types"].get(col_name, "")).lower()
        return any(t in dtype_s for t in ["int", "float", "double", "num"])
    c_name_l = col_name.lower().strip()
    tokens = set(re.split(r"[_\s\W]+", c_name_l))
    numeric_terms = {
        "price", "amount", "qty", "quantity", "sales", "revenue", "profit",
        "cost", "total", "score", "rate", "salary", "marks", "mark",
        "pct", "percentage", "sgpa", "cgpa", "gpa", "grade", "points",
        "package", "ctc", "age", "weight", "height", "balance", "count", "num"
    }
    if tokens & numeric_terms:
        return True
    for t in tokens:
        for term in numeric_terms:
            if len(term) >= 3 and (t.startswith(term) or t.endswith(term)):
                if term == "mark" and t in ("market", "marketing", "marketplace", "bookmark"):
                    continue
                if term == "count" and t in ("country", "county", "account"):
                    continue
                if term == "age" and t in ("stage", "image", "message", "page", "usage", "storage", "coverage", "average", "lineage"):
                    continue
                if term == "rate" and t in ("corporate", "accurate", "generate", "strategy", "crate", "pirate", "migrate"):
                    continue
                return True
    return False


def build_query_plan(
    question: str,
    metadata: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    default_dataset: Optional[str] = None,
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
    q_norm = normalize_question_for_intent(q_clean)
    q_norm_l = q_norm.lower()

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

        # Case B: "Make it top 5." / "Make it 10." / "Show top 5." / "Now show only the top 3"
        has_explicit_by = " by " in q_lower
        prev_intent_str = str(prev_plan.intent).upper() if prev_plan.intent else ""
        if not has_explicit_by and prev_intent_str in ("TOP_N", "BOTTOM_N", "GROUP_BY", "FILTER", "SORT", "SHOW_DATA"):
            match_limit = (
                re.search(r"^(?:now\s+)?(?:show\s+)?(?:only\s+)?(?:the\s+)?(?:top|bottom|first|last)\s+(\d+)\b", q_lower) or
                re.search(r"\b(?:make\s+it|change\s+to|limit\s+to)\s+(?:top|bottom)?\s*(\d+)\b", q_lower) or
                re.search(r"^(?:now\s+)?(?:show\s+)?(?:only\s+)?(?:the\s+)?(\d+)\s*(?:records|rows|items)?$", q_lower)
            )
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

    # 3. Resolve Target Dataset & Secondary Dataset
    active_dataset = default_dataset or (context.get("selected_dataset") if context else None)
    mentioned_datasets = _extract_datasets_from_question(q_clean, metadata)

    if len(mentioned_datasets) >= 2:
        target_ds = mentioned_datasets[0]
        secondary_ds = mentioned_datasets[1]
    elif len(mentioned_datasets) == 1:
        target_ds = mentioned_datasets[0]
        if intent in (QueryIntent.COMPARE_DATASETS.value, QueryIntent.CROSS_DATASET_ANALYSIS.value) and len(metadata) > 1:
            other_ds = [d for d in metadata.keys() if d != target_ds]
            secondary_ds = other_ds[0] if other_ds else None
        else:
            secondary_ds = None
    elif active_dataset and active_dataset in metadata:
        target_ds = active_dataset
        if intent in (QueryIntent.COMPARE_DATASETS.value, QueryIntent.CROSS_DATASET_ANALYSIS.value) and len(metadata) > 1:
            other_ds = [d for d in metadata.keys() if d != target_ds]
            secondary_ds = other_ds[0] if other_ds else None
        else:
            secondary_ds = None
    elif prev_plan_dict and prev_plan_dict.get("dataset") in metadata:
        target_ds = prev_plan_dict["dataset"]
        secondary_ds = None
    elif len(metadata) == 1:
        target_ds = list(metadata.keys())[0]
        secondary_ds = None
    else:
        # Infer dataset from keywords in question
        words = re.findall(r"[a-zA-Z_]+", q_lower)
        target_ds = _find_best_dataset_for_columns(words, metadata)
        if intent in (QueryIntent.COMPARE_DATASETS.value, QueryIntent.CROSS_DATASET_ANALYSIS.value) and len(metadata) > 1:
            other_ds = [d for d in metadata.keys() if d != target_ds]
            secondary_ds = other_ds[0] if other_ds else None
        else:
            secondary_ds = None

    ds_meta = metadata.get(target_ds, {}) if target_ds else {}
    available_cols = _extract_columns_from_metadata(ds_meta)

    # 4. Pre-extract filters so columns in filters are not mistakenly assigned as group_by keys!
    parsed_filters, parsed_filter_logic = _extract_filters_from_question(q_clean, available_cols, ds_meta)
    filtered_cols_set = {f.get("column") for f in parsed_filters if f.get("column")}

    # Check Dataset Ambiguity (e.g. "Compare sales" when multiple datasets contain sales)
    if len(metadata) > 1 and len(mentioned_datasets) < 2 and not active_dataset:
        if any(k in q_lower for k in ["compare sales", "show sales"]) and sum(1 for m in metadata.values() if any("sales" in c.lower() for c in _extract_columns_from_metadata(m))) > 1:
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
            r"(?:correlation|association|relationship)\s+between\s+([a-zA-Z0-9_\s]+?)\s+and\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+|\s+calculate\b)",
            r"between\s+([a-zA-Z0-9_\s]+?)\s+and\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+|\s+calculate\b)",
            r"(?:correlate|compare)\s+([a-zA-Z0-9_\s]+?)\s+(?:with|and)\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+|\s+calculate\b)",
            r"(?:whether|if)\s+([a-zA-Z0-9_\s]+?)\s+(?:is\s+)?(?:associated\s+with|correlated\s+with|related\s+to)\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+|\s+calculate\b)",
            r"([a-zA-Z0-9_\s]+?)\s+(?:is\s+)?(?:associated\s+with|correlated\s+with)\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+|\s+calculate\b)",
        ]
        found_corr_pair = None
        for cp in corr_patterns:
            m_cp = re.search(cp, q_lower)
            if m_cp:
                cand_a = m_cp.group(1).strip()
                cand_b = m_cp.group(2).strip()
                cand_a = re.sub(r"^(?:the|an|a)\s+", "", cand_a).strip()
                cand_b = re.sub(r"^(?:the|an|a)\s+", "", cand_b).strip()
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

        # Fallback if both not found: scan available numeric columns mentioned in question
        if not (measure_col and secondary_col):
            num_cols_in_q = []
            for c in available_cols:
                if not _is_numeric_column(c, ds_meta):
                    continue
                c_low = c.lower()
                c_spaced = c_low.replace("_", " ")
                c_words = [w for w in re.split(r"[_\s]+", c_low) if w not in ("inr", "usd", "id", "num", "val")]
                if (
                    re.search(r"\b" + re.escape(c_low) + r"\b", q_lower)
                    or re.search(r"\b" + re.escape(c_spaced) + r"\b", q_lower)
                    or (len(c_words) >= 2 and all(w in q_lower for w in c_words))
                    or (len(c_low) >= 3 and c_low in ("age", "price", "sales", "revenue", "quantity", "cost", "marks", "salary", "score") and re.search(r"\b" + c_low + r"\b", q_lower))
                ):
                    if c not in num_cols_in_q:
                        num_cols_in_q.append(c)

            if len(num_cols_in_q) >= 2:
                if not measure_col:
                    measure_col = num_cols_in_q[0]
                if not secondary_col:
                    rem = [c for c in num_cols_in_q if c != measure_col]
                    if rem:
                        secondary_col = rem[0]

    # A. Check if question explicitly specifies a column (e.g. from clarification: "using unit_price", "use Modal_Price")
    explicit_using = re.search(r"\b(?:using|use|with column|column)\s+([a-zA-Z0-9_]+)\b", q_lower)
    if explicit_using:
        cand_name = explicit_using.group(1).strip()
        res_cand = resolve_column(cand_name, ds_meta)
        if res_cand["resolved"] and res_cand["column"]:
            measure_col = res_cand["column"]
            selection_explanation = f"Using user-specified column '{measure_col}'."

    # A2. Check if a metric column is explicitly mentioned after total/sum/average/mean/max/min
    if not measure_col:
        explicit_metric_m = re.search(r"\b(?:total|sum\s+of|sum|average|mean|max|maximum|min|minimum)\s+(?:the\s+)?([a-zA-Z0-9_]+)\b", q_lower)
        if explicit_metric_m:
            cand_m_name = explicit_metric_m.group(1).strip()
            res_m = resolve_column(cand_m_name, ds_meta, column_type_filter="numeric")
            if res_m["resolved"] and res_m["column"] and _is_numeric_column(res_m["column"], ds_meta):
                measure_col = res_m["column"]
                selection_explanation = f"Using metric column '{measure_col}' specified after aggregation keyword."

    # B. Check if question directly mentions an actual column name from dataset schema
    def _to_sing(w: str) -> str:
        s = w.lower()
        if s.endswith("ies") and len(s) > 4:
            return s[:-3] + "y"
        if s.endswith("es") and len(s) > 3:
            return s[:-2]
        if s.endswith("s") and not s.endswith("ss") and len(s) > 3:
            return s[:-1]
        return s

    sorted_avail = sorted(available_cols, key=len, reverse=True)
    for col in sorted_avail:
        c_low = col.lower()
        c_spaced = c_low.replace("_", " ")
        c_sing = _to_sing(c_low)
        c_sing_spaced = c_sing.replace("_", " ")
        if (
            re.search(r"\b" + re.escape(c_low) + r"\b", q_lower)
            or re.search(r"\b" + re.escape(c_spaced) + r"\b", q_lower)
            or re.search(r"\b" + re.escape(c_sing) + r"\b", q_lower)
            or re.search(r"\b" + re.escape(c_sing_spaced) + r"\b", q_lower)
        ):
            res_direct = resolve_column(col, ds_meta)
            if res_direct["resolved"] and res_direct["column"]:
                cand_col = res_direct["column"]
                is_num = _is_numeric_column(cand_col, ds_meta)

                if is_num:
                    if not measure_col:
                        is_shadowed_filter_col = cand_col in filtered_cols_set and any(
                            c != cand_col and _is_numeric_column(c, ds_meta) and (re.search(r"\b" + re.escape(c.lower()) + r"\b", q_lower) or re.search(r"\b" + re.escape(c.lower().replace("_", " ")) + r"\b", q_lower))
                            for c in available_cols
                        )
                        if not is_shadowed_filter_col:
                            measure_col = cand_col
                            if res_direct.get("selection_explanation"):
                                selection_explanation = res_direct["selection_explanation"]
                else:
                    if cand_col in filtered_cols_set:
                        pass
                    else:
                        has_explicit_group = any(t in q_lower for t in ["by ", "per ", "for each ", "across ", "breakdown", "group by ", "grouped by ", "group rows by "])
                        has_rank_group = intent in (QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value, QueryIntent.GROUP_BY.value) and any(w in q_lower for w in ["which", "who", "top", "bottom", "highest", "lowest", "most", "least"])
                        if has_explicit_group or has_rank_group:
                            if cand_col not in group_by_cols:
                                group_by_cols.append(cand_col)
                    if not measure_col and intent in (
                        QueryIntent.COUNT.value,
                        QueryIntent.UNIQUE_VALUES.value,
                        QueryIntent.SHOW_DATA.value,
                    ) and cand_col not in filtered_cols_set:
                        measure_col = cand_col
                        if res_direct.get("selection_explanation"):
                            selection_explanation = res_direct["selection_explanation"]

    # C. Check for group_by indicators: "by market", "per commodity", "by region"
    # Exclude passive / causal indicators like "driven by", "caused by", "accompanied by", "ranked by", "sorted by"
    group_matches = re.findall(
        r"(?<!\bdriven\s)(?<!\bcaused\s)(?<!\baffected\s)(?<!\bdetermined\s)(?<!\bexplained\s)(?<!\baccompanied\s)(?<!\branked\s)(?<!\bsorted\s)\b(?:by|per|across|for each)\s+([a-zA-Z0-9_]+)\b",
        q_lower,
    )
    for gm in group_matches:
        if gm in [
            "average", "mean", "sum", "total", "max", "min", "highest", "lowest",
            "month", "year", "date", "two", "flagged", "failed", "case", "cases",
            "record", "records", "row", "rows", "each", "all", "other",
            "order", "orders", "volume", "value", "values",
            "summing", "group", "groups", "grouping", "calculating", "aggregating", "totaling"
        ] or gm in RESOLVER_STOPWORDS:
            continue
        res = resolve_column(gm, ds_meta)
        if not res["resolved"] and secondary_ds and secondary_ds in metadata:
            res = resolve_column(gm, metadata[secondary_ds])
        if res["is_ambiguous"]:
            if not group_by_cols:
                ambiguous_column_result = res
        elif res["resolved"] and res["column"]:
            cand = res["column"]
            if _is_numeric_column(cand, ds_meta) and intent in (
                QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value, QueryIntent.MAXIMUM.value, QueryIntent.MINIMUM.value
            ):
                if not measure_col:
                    measure_col = cand
                continue
            if cand not in group_by_cols:
                group_by_cols.append(cand)
            if res.get("selection_explanation") and not selection_explanation:
                selection_explanation = res["selection_explanation"]
        elif not res["resolved"] and intent in (QueryIntent.AVERAGE.value, QueryIntent.SUM.value, QueryIntent.GROUP_BY.value, QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value):
            missing_requested_columns.append(gm)

    which_match = re.search(r"\b(?:which|what|who)\s+([a-zA-Z0-9_]+)\s+(?:has|had|scored|got|achieved|received|is|was|generates|leads|produced|spent|spend|purchased|ordered|bought|made|paid|sold|placed)\b", q_lower)
    if which_match:
        cat_candidate = which_match.group(1).strip()
        if (
            cat_candidate not in RESOLVER_STOPWORDS
            and cat_candidate not in [
                "method", "methods", "approach", "technique", "algorithm",
                "dataset", "data", "metric", "measure", "one", "record",
                "records", "result", "results", "way", "model", "case", "cases"
            ]
        ):
            res = resolve_column(cat_candidate, ds_meta)
            if not res["resolved"] and secondary_ds and secondary_ds in metadata:
                res = resolve_column(cat_candidate, metadata[secondary_ds])
            if res["resolved"] and res["column"]:
                cand = res["column"]
                if _is_numeric_column(cand, ds_meta):
                    if not measure_col:
                        measure_col = cand
                else:
                    if cand not in group_by_cols:
                        group_by_cols.append(cand)
                    if measure_col == cand:
                        measure_col = None
    elif re.search(r"\bwho\s+(?:has|had|scored|got|achieved|received|is|was)\b", q_lower):
        # Look for entity/person/name column in domain columns
        entity_candidates = [
            c for c in filter_metadata_columns(available_cols)
            if any(t in c.lower() for t in ["name", "student", "candidate", "customer", "user", "person", "employee", "roll"])
        ]
        if entity_candidates and entity_candidates[0] not in group_by_cols:
            group_by_cols.append(entity_candidates[0])

    # If still no group_by found for ranking / grouping questions, check for any domain categorical column in question
    if not group_by_cols and intent in (
        QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value, QueryIntent.GROUP_BY.value
    ):
        domain_cats = [c for c in filter_metadata_columns(available_cols) if not _is_numeric_column(c, ds_meta)]
        for c in domain_cats:
            c_l = c.lower()
            c_sing = _to_sing(c_l)
            if (
                re.search(r"\b" + re.escape(c_l) + r"\b", q_lower)
                or re.search(r"\b" + re.escape(c_sing) + r"\b", q_lower)
                or re.search(r"\b" + re.escape(c_l) + r"\b", q_norm_l)
                or re.search(r"\b" + re.escape(c_sing) + r"\b", q_norm_l)
            ):
                group_by_cols.append(c)
                break

    # E. If question mentions Top N commodities/markets: "top 10 commodities by modal price"
    top_entity_match = re.search(r"\b(?:top|bottom)\s*(?:\d+)?\s*([a-zA-Z0-9_]+)\b", q_lower)
    if top_entity_match:
        entity_name = top_entity_match.group(1).strip()
        if entity_name not in ["records", "rows", "values", "numbers"]:
            res = resolve_column(entity_name, ds_meta)
            if not res["resolved"] and secondary_ds and secondary_ds in metadata:
                res = resolve_column(entity_name, metadata[secondary_ds])
            if res["resolved"] and res["column"]:
                if res["column"] not in group_by_cols:
                    group_by_cols.append(res["column"])
                if measure_col == res["column"]:
                    measure_col = None

    # F. Identify measure column from semantic candidates if not yet matched directly
    if not measure_col and not ambiguous_column_result:
        from query.column_resolver import SEMANTIC_SYNONYMS
        metric_concepts = [
            "price", "sales", "profit", "cost", "discount", "quantity", "marks",
            "score", "percentage", "sgpa", "cgpa", "attendance", "salary", "rating", "performance"
        ]
        measure_candidates = []
        for k in metric_concepts:
            measure_candidates.append(k)
            measure_candidates.extend(SEMANTIC_SYNONYMS.get(k, []))
        measure_candidates.extend([
            "revenue", "modal_price", "unit_price", "arrival_quantity", "units_sold",
            "total_marks", "subject_marks", "obtained_marks", "annual_ctc", "amount", "total_amount", "spending", "spent", "spend", "money"
        ])
        measure_candidates = list(dict.fromkeys(measure_candidates))

        found_measure_words = []
        for mc in measure_candidates:
            if re.search(r"\b" + re.escape(mc.replace("_", " ")) + r"\b", q_lower) or re.search(r"\b" + re.escape(mc) + r"\b", q_lower):
                found_measure_words.append(mc)

        if found_measure_words:
            found_measure_words.sort(key=len, reverse=True)
            for mw in found_measure_words:
                res = resolve_column(mw, ds_meta, column_type_filter="numeric")
                if not res["resolved"] and secondary_ds and secondary_ds in metadata:
                    res = resolve_column(mw, metadata[secondary_ds], column_type_filter="numeric")
                if res["is_ambiguous"]:
                    ambiguous_column_result = res
                    break
                elif res["resolved"] and res["column"]:
                    cand_col = res["column"]
                    if cand_col in group_by_cols:
                        continue
                    if not _is_numeric_column(cand_col, ds_meta):
                        continue
                    measure_col = cand_col
                    if res.get("selection_explanation"):
                        selection_explanation = res["selection_explanation"]
                    break

    # G. Check for requested metric that could not be resolved (e.g. "average attendance", "highest marks", "lowest score")
    if not measure_col and intent in (
        QueryIntent.AVERAGE.value,
        QueryIntent.SUM.value,
        QueryIntent.MEDIAN.value,
        QueryIntent.MINIMUM.value,
        QueryIntent.MAXIMUM.value,
        QueryIntent.TOP_N.value,
        QueryIntent.BOTTOM_N.value,
        QueryIntent.GROUP_BY.value,
        QueryIntent.SORT.value,
        QueryIntent.DESCRIPTIVE_STATISTICS.value,
    ):
        agg_metric_m = re.search(
            r"\b(?:average|mean|avg|median|sum|summing|total|total of|minimum|lowest|min|maximum|highest|max|distribution of|spread of|summary of)\s+(?:of\s+)?([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+|\s+by\s+|\s+where\s+)",
            q_lower
        )
        if not agg_metric_m:
            agg_metric_m = re.search(
                r"\b(?:highest|lowest|max|maximum|min|minimum|peak|top|bottom)\s+([a-zA-Z0-9_\s]+?)(?:\?|$|\.|\s+in\s+|\s+for\s+|\s+by\s+|\s+where\s+)",
                q_lower
            )

        if agg_metric_m:
            raw_metric_orig = agg_metric_m.group(1).strip()
            raw_metric = re.sub(r"^(?:the|an|a|all|each|student|students|customer|customers|order|orders|user|users)\s+", "", raw_metric_orig).strip()
            metric_candidates = [raw_metric, raw_metric_orig]
            words = raw_metric.split()
            if len(words) > 1:
                metric_candidates.extend(words)
                metric_candidates.append(words[-1])

            matched_metric = False
            for cand in metric_candidates:
                cand_clean = cand.strip()
                if cand_clean and cand_clean not in [
                    "of", "the", "a", "an", "all", "each", "records", "rows", "values",
                    "numbers", "dataset", "data", "columns", "features", "value", "table", "student", "students"
                ] and cand_clean not in RESOLVER_STOPWORDS:
                    res_m = resolve_column(cand_clean, ds_meta)
                    if res_m["is_ambiguous"]:
                        ambiguous_column_result = res_m
                        matched_metric = True
                        break
                    elif res_m["resolved"] and res_m["column"]:
                        cand_col = res_m["column"]
                        if cand_col in group_by_cols:
                            continue
                        if not _is_numeric_column(cand_col, ds_meta):
                            continue
                        measure_col = cand_col
                        matched_metric = True
                        break

            if not matched_metric and raw_metric and raw_metric not in [
                "of", "the", "a", "an", "all", "each", "records", "rows", "values",
                "numbers", "dataset", "data", "columns", "features", "value", "table"
            ] and not raw_metric.isdigit() and raw_metric not in RESOLVER_STOPWORDS:
                missing_col_name = raw_metric_orig if raw_metric_orig else raw_metric
                missing_requested_columns.append(missing_col_name)

    # H. If still no measure found and no explicit missing metric identified, scan non-metadata numeric columns
    if not measure_col and not ambiguous_column_result and not missing_requested_columns:
        domain_available_cols = filter_metadata_columns(available_cols)
        for col in domain_available_cols:
            col_lower = col.lower()
            if col in group_by_cols:
                continue
            if not _is_numeric_column(col, ds_meta):
                continue
            if col_lower in q_lower or _to_sing(col_lower) in q_lower or _normalize_name(col) in _normalize_name(q_lower):
                res = resolve_column(col, ds_meta)
                if res["resolved"] and res["column"]:
                    cand_col = res["column"]
                    if cand_col in group_by_cols or not _is_numeric_column(cand_col, ds_meta):
                        continue
                    measure_col = cand_col
                    if res.get("selection_explanation"):
                        selection_explanation = res["selection_explanation"]
                    break

        # Fallback to single domain numeric column or performance measure if general question
        if not measure_col and intent in (QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value, QueryIntent.MAXIMUM.value, QueryIntent.MINIMUM.value):
            if any(term in q_lower or term in q_norm_l for term in ["perform", "best", "worst", "revenue", "sales", "selling", "profit", "amount"]):
                for col in filter_metadata_columns(available_cols):
                    if _is_numeric_column(col, ds_meta) and any(term in col.lower() for term in ["revenue", "sales", "profit", "amount", "total", "score", "price"]):
                        measure_col = col
                        selection_explanation = f"Selected performance measure '{measure_col}'."
                        break

        if not measure_col:
            domain_numeric = []
            for c in domain_available_cols:
                if isinstance(ds_meta, dict) and "data_types" in ds_meta and ds_meta["data_types"]:
                    dt = str(ds_meta["data_types"].get(c, "")).lower()
                    if any(t in dt for t in ["int", "float", "double", "num"]):
                        domain_numeric.append(c)
                elif any(t in c.lower() for t in ["marks", "price", "sales", "amount", "salary", "score", "total", "qty", "quantity", "sgpa", "cgpa", "pct", "percentage"]):
                    domain_numeric.append(c)

            if len(domain_numeric) == 1 and intent in (
                QueryIntent.AVERAGE.value, QueryIntent.SUM.value, QueryIntent.MEDIAN.value,
                QueryIntent.MINIMUM.value, QueryIntent.MAXIMUM.value, QueryIntent.TOP_N.value,
                QueryIntent.BOTTOM_N.value, QueryIntent.DESCRIPTIVE_STATISTICS.value
            ):
                measure_col = domain_numeric[0]
                selection_explanation = f"Selected single available domain numeric metric '{measure_col}'."
            elif len(domain_numeric) > 1 and intent in (
                QueryIntent.AVERAGE.value, QueryIntent.SUM.value, QueryIntent.MEDIAN.value,
                QueryIntent.MINIMUM.value, QueryIntent.MAXIMUM.value
            ) and any(w in q_lower for w in ["average", "mean", "sum", "total", "median", "minimum", "maximum"]):
                ambiguous_column_result = {
                    "is_ambiguous": True,
                    "clarification_options": domain_numeric,
                    "clarification_candidates": [{"column": c} for c in domain_numeric],
                    "clarification_labels": domain_numeric,
                }

    # Check if question asked for a mathematically derivable metric before stopping for ambiguity
    derived_column_spec = None
    if not measure_col or (ambiguous_column_result and ambiguous_column_result.get("is_ambiguous")):
        for cand_word in re.findall(r"[a-zA-Z_]+", q_lower):
            derivable = check_derivable_metric(cand_word, available_cols)
            if derivable:
                measure_col = derivable["output_name"]
                derived_column_spec = derivable
                ambiguous_column_result = None
                selection_explanation = derivable["explanation"]
                if cand_word in missing_requested_columns:
                    missing_requested_columns.remove(cand_word)
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

    # 6. Aggregation, Sort, Limit, Offset
    date_col = None
    aggregation = None
    if group_by_cols and intent in (QueryIntent.FILTER.value, QueryIntent.SHOW_DATA.value):
        intent = QueryIntent.GROUP_BY.value
    if intent in (QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value):
        if any(w in q_lower for w in ["total revenue", "total sales", "total amount", "contribution to total", "contribution to revenue"]):
            aggregation = "sum"
        elif any(w in q_lower for w in ["average price", "mean price", "average sales", "mean sales", "average revenue", "average marks", "average score"]):
            aggregation = "mean"
        elif any(w in q_lower for w in ["average", "mean", "avg"]) and "average order value" not in q_lower and "average order size" not in q_lower:
            aggregation = "mean"
        elif "median" in q_lower:
            aggregation = "median"
        elif any(w in q_lower for w in ["minimum", "min"]):
            aggregation = "min"
        elif any(w in q_lower for w in ["maximum", "max", "peak"]):
            aggregation = "max"
        else:
            aggregation = "sum"
    elif intent == QueryIntent.AVERAGE.value or any(w in q_lower for w in ["average", "mean", "avg"]):
        aggregation = "mean"
    elif intent == QueryIntent.MEDIAN.value or "median" in q_lower:
        aggregation = "median"
    elif intent == QueryIntent.SUM.value or any(w in q_lower for w in ["sum", "total of", "total", "summing", "totaling"]):
        aggregation = "sum"
    elif intent == QueryIntent.MINIMUM.value or any(w in q_lower for w in ["minimum", "lowest", "min"]):
        aggregation = "min"
    elif intent == QueryIntent.MAXIMUM.value or any(w in q_lower for w in ["maximum", "highest", "max", "peak"]):
        aggregation = "max"
    elif intent == QueryIntent.COUNT.value or any(w in q_lower for w in ["count", "how many"]):
        aggregation = "count"

    # Limit and Sort
    limit = None
    sort = None
    sort_column = measure_col

    if intent == QueryIntent.TOP_N.value:
        sort = "descending"
        match_n = re.search(r"\btop\s*(\d+)\b", q_lower) or re.search(r"\btop\s*(\d+)\b", q_norm_l)
        if match_n:
            limit = min(int(match_n.group(1)), 100)
        elif re.search(r"\btop\s*(?:\d+)?\s*(?:performing\s+)?combination\b", q_lower):
            limit = 1
        elif any(w in q_lower or w in q_norm_l for w in ["which", "what", "who"]) and any(w in q_lower or w in q_norm_l for w in ["highest", "largest", "peak", "maximum", "best", "greatest", "most", "better", "leading"]):
            limit = 1
        elif any(w in q_lower or w in q_norm_l for w in ["highest", "maximum", "peak", "most", "better"]):
            limit = 1
        else:
            limit = 10
    elif intent == QueryIntent.BOTTOM_N.value:
        sort = "ascending"
        match_n = re.search(r"\bbottom\s*(\d+)\b", q_lower) or re.search(r"\bbottom\s*(\d+)\b", q_norm_l)
        if match_n:
            limit = min(int(match_n.group(1)), 100)
        elif any(w in q_lower or w in q_norm_l for w in ["which", "what", "who"]) and any(w in q_lower or w in q_norm_l for w in ["lowest", "smallest", "minimum", "worst", "least", "fewest"]):
            limit = 1
        elif any(w in q_lower or w in q_norm_l for w in ["lowest", "minimum", "least", "fewest", "worst"]):
            limit = 1
        else:
            limit = 10
    elif intent == QueryIntent.SORT.value:
        sort = "ascending" if "asc" in q_lower else "descending"

    # Filters
    filters = parsed_filters
    filter_logic = parsed_filter_logic
    if intent in (QueryIntent.DATA_TYPES.value, QueryIntent.DATA_QUALITY_AUDIT.value):
        filters = [f for f in filters if f.get("operator") in (">", ">=", "<", "<=", "!=")]

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

    # Identify Date Column (only if trend, date range, or date-related question)
    if (
        intent == QueryIntent.TREND.value
        or date_range is not None
        or any(term in q_lower for term in ["date", "time", "trend", "monthly", "yearly", "daily", "timeline", "temporal", "over time"])
    ):
        for col in available_cols:
            col_l = col.lower()
            if any(term in col_l for term in ["date", "time", "timestamp", "month", "year", "created_at"]):
                date_col = col
                break

    # Output flags
    output_table = True
    output_chart = False
    if intent in (QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value, QueryIntent.GROUP_BY.value, QueryIntent.TREND.value, QueryIntent.CORRELATION.value):
        output_chart = True

    # Derivable metric calculation if requested measure is missing
    if not derived_column_spec and missing_requested_columns:
        still_missing = []
        for mr in missing_requested_columns:
            derivable = check_derivable_metric(mr, available_cols)
            if derivable:
                derived_column_spec = derivable
                if not measure_col:
                    measure_col = derivable["output_name"]
                    selection_explanation = derivable["explanation"]
            else:
                still_missing.append(mr)
        missing_requested_columns = still_missing

    # Purge any columns from missing_requested_columns that exist in available_cols, measure_col, or group_by_cols
    avail_lower = {c.lower(): c for c in available_cols}
    missing_requested_columns = [
        m for m in missing_requested_columns
        if m.lower() not in avail_lower
        and (not measure_col or m.lower() != measure_col.lower())
        and not any(m.lower() == g.lower() for g in group_by_cols)
    ]

    if not sort_column and measure_col:
        sort_column = measure_col

    compare_methods = False
    if intent in (QueryIntent.ANOMALY_SUMMARY.value, QueryIntent.ANOMALY_RECORDS.value):
        if any(k in q_lower for k in ["z-score", "zscore", "z score", "both methods", "compare", "disagree", "recommend", "methods", "iqr and z"]):
            compare_methods = True

    subquery_obj = next((f.get("subquery") for f in filters if f.get("subquery")), None)
    is_rows_and_cols = ("row" in q_lower or "record" in q_lower) and "column" in q_lower

    # Build plan
    plan = StructuredQueryPlan(
        intent=intent,
        dataset=target_ds,
        column=measure_col,
        secondary_dataset=secondary_ds,
        secondary_column=secondary_col,
        filters=filters,
        filter_logic=filter_logic,
        subquery=subquery_obj,
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
        derived_column=derived_column_spec,
        needs_clarification=False,
        metadata={
            "reason": intent_res.get("reason", ""),
            "error": intent_res.get("reason", "") if intent == QueryIntent.UNKNOWN.value else "",
            "selection_explanation": selection_explanation,
            "missing_columns": list(dict.fromkeys(missing_requested_columns)) if missing_requested_columns else [],
            "derived_column": derived_column_spec,
            "compare_methods": compare_methods,
            "show_records": any(k in q_lower for k in ["record", "records", "detected records", "flagged records", "row", "rows", "show"]),
            "question": question,
            "dataset_id": ds_meta.get("dataset_id") if isinstance(ds_meta, dict) else None,
            "dataset_filename": target_ds,
            "include_columns": is_rows_and_cols,
            "include_rows": is_rows_and_cols,
            "filter_logic": filter_logic,
        },
    )

    return plan.to_dict()


def _normalize_name(name: str) -> str:
    """Helper normalization."""
    return re.sub(r"[^a-zA-Z0-9]", "", str(name).lower())
