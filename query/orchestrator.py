"""Main Query Orchestrator for Phase 6 Natural Language Query Engine.

Coordinates the end-to-end analytical workflow:
Question -> Intent -> Query Plan -> Validation -> Safe Execution -> Evidence -> Answer -> Visualization.
"""

from typing import Dict, Any, List, Optional
import re
import pandas as pd
import numpy as np

from query.config import normalize_query_config
from query.intent_detector import detect_query_intent
from query.query_planner import build_query_plan
from query.query_validator import validate_query_plan
from query.query_executor import execute_query
from query.evidence_extractor import extract_query_evidence
from query.answer_generator import generate_query_answer
from query.chart_recommender import recommend_query_visualization
from query.llm_planner import LLMQueryPlanner
from query.context_manager import ConversationContextManager


def split_multi_part_question(question: str) -> List[str]:
    """Split a coordinated multi-part question into individual sub-questions.

    Handles questions like:
    - "Which product has the highest revenue, which region performs best, compare monthly sales, and identify unusual values?"
    - "What is the average price? Show top 5 products. Are there missing values?"
    """
    if not question:
        return []
    q = question.strip()

    # 1. Dataset preamble detection: "Using only clean_customer_orders (2).csv, ..." or "In dataset.csv, ..."
    preamble_pattern = (
        r"^(?:using\s+(?:only\s+)?|in\s+|for\s+|from\s+|with\s+)"
        r"(?:the\s+)?(?:currently\s+selected\s+|uploaded\s+)?"
        r"([^,;]+?(?:\.(?:csv|xlsx?|tsv|parquet|json)\b|\bdataset\b|\bfile\b))"
        r"[\s,;]+"
    )
    preamble_match = re.match(preamble_pattern, q, flags=re.IGNORECASE)
    preamble = ""
    body = q
    if preamble_match:
        preamble = preamble_match.group(0)
        body = q[len(preamble):].strip()

    # Helper: Check if body is a single grouping/aggregation request
    # e.g., "group rows by Category and calculate total Order_Amount_INR"
    # "calculate total Order_Amount_INR for each Category and return only the table"
    # "group rows by Category by summing Order_Amount_INR for each group"
    # "For orders where Category is Electronics and Quantity is greater than 1, show the total Order_Amount_INR grouped by Payment_Method"
    is_grouping_req = (
        bool(re.search(r"\bgroup(?:ing)?(?:\s+rows)?\s+by\b.*?\b(?:and\s+|,\s*|\s+by\s+)(?:calculate|compute|sum|count|average|mean|total|aggregat)\b", body, re.IGNORECASE))
        or bool(re.search(r"\b(?:calculate|compute|sum|count|average|mean|total|aggregat)\b.*?\b(?:and\s+|,\s*)group\s+(?:rows\s+)?by\b", body, re.IGNORECASE))
        or bool(re.search(r"\bgroup(?:ing)?(?:\s+rows)?\s+by\b", body, re.IGNORECASE) and re.search(r"\bfor\s+each\s+group\b|\bby\s+summing\b|\bby\s+totaling\b|\bby\s+aggregating\b", body, re.IGNORECASE))
        or bool(re.search(r"\bfor\s+each\s+[a-zA-Z0-9_]+\b", body, re.IGNORECASE) and not re.search(r"[?;]", body) and not re.search(r"\b(?:and\s+also|and\s+what|and\s+which|and\s+how|and\s+compare|and\s+identify)\b", body, re.IGNORECASE))
        or bool(re.search(r"^(?:for\s+.*?\bwhere\b|where\b).*?,\s*(?:show|find|list|calculate|compute|give|tell|get)\b", body, re.IGNORECASE))
        or bool(re.search(r"\b(?:group(?:ed)?\s+by|grouped\s+by)\b", body, re.IGNORECASE) and not re.search(r"[?;]", body) and not re.search(r"\b(?:and\s+also|and\s+what|and\s+which|and\s+how|and\s+compare|and\s+identify)\b", body, re.IGNORECASE))
    )

    if is_grouping_req:
        # Check if there is an explicit second independent question separated by ?, ;, or coordinated interrogatives
        has_distinct_second_q = bool(re.search(r"[?;]|\b(?:,\s*and\s+|\s+and\s+)(?=(?:which|what|who|where|how many|how|compare|identify|are there|is there|any outliers)\b)", body, re.IGNORECASE))
        if not has_distinct_second_q:
            return [q]

    # 2. Check for multiple question marks
    if body.count("?") > 1:
        raw_parts = [p.strip() for p in re.split(r"\?+", body) if p.strip()]
        parts = [p + "?" if not p.endswith("?") else p for p in raw_parts]
        if preamble:
            parts[0] = preamble + parts[0]
        return parts

    # 3. Coordinate split pattern
    split_pattern = (
        r"(?:,\s*and\s+|;\s*and\s+|;\s*|,\s*|\s+and\s+)"
        r"(?=(?:which|what|who|where|how many|how|compare|identify|show|find|list|check|calculate|count|sum|total|average|mean|tell me|is there|are there|any outliers|unusual values)\b)"
    )
    raw_parts = re.split(split_pattern, body, flags=re.IGNORECASE)
    parts = [p.strip().rstrip("?,.") for p in raw_parts if p.strip()]

    # Filter out or merge invalid parts (pure grouping clause without aggregation, pure formatting instructions, subordinate clauses, etc.)
    merged_parts: List[str] = []
    for p in parts:
        is_pure_group = bool(re.match(r"^group(?:ing)?(?:\s+rows)?\s+by\s+[a-zA-Z0-9_]+$", p, re.IGNORECASE))
        is_pure_format = bool(re.match(r"^(?:return\s+)?(?:only\s+)?(?:a\s+|the\s+)?(?:\w+[- ]\w+\s+)?table$|^do\s+not\s+include\s+.*$", p, re.IGNORECASE))
        is_subordinate = bool(re.match(r"^(?:for\s+.*?\bwhere\b|where\b)\s+.*$", p, re.IGNORECASE)) and not bool(re.search(r"\b(?:show|find|list|check|calculate|count|sum|total|average|mean|which|what|who|how)\b", p, re.IGNORECASE))
        if is_pure_group or is_pure_format:
            if merged_parts:
                merged_parts[-1] = merged_parts[-1] + " and " + p
            else:
                merged_parts.append(p)
        elif is_subordinate:
            merged_parts.append(p)
        else:
            if merged_parts and (re.match(r"^group(?:ing)?(?:\s+rows)?\s+by\s+[a-zA-Z0-9_]+$", merged_parts[-1], re.IGNORECASE) or bool(re.match(r"^(?:for\s+.*?\bwhere\b|where\b)\s+.*$", merged_parts[-1], re.IGNORECASE))):
                merged_parts[-1] = merged_parts[-1] + ", " + p
            else:
                merged_parts.append(p)

    if len(merged_parts) > 1:
        if preamble:
            merged_parts[0] = preamble + merged_parts[0]
        return merged_parts

    return [q]


def _run_single_query(
    question: str,
    datasets: Dict[str, pd.DataFrame],
    metadata: Dict[str, Any],
    cleaned_datasets: Optional[Dict[str, pd.DataFrame]] = None,
    phase4_results: Optional[Dict[str, Any]] = None,
    phase5_results: Optional[Dict[str, Any]] = None,
    relationships: Optional[List[Any]] = None,
    join_audit: Optional[List[Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    default_dataset: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute complete Phase 6 natural language query analysis pipeline for a single analytical question."""
    cfg = normalize_query_config(config)
    q_clean = question.strip() if question else ""
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Basic validation of inputs
    if not q_clean:
        return {
            "status": "error",
            "question": "",
            "intent": {},
            "query_plan": {},
            "validation": {"valid": False, "errors": ["No question provided."]},
            "result": {},
            "evidence": {},
            "answer": {"answer": "Please provide a question to analyze.", "key_points": [], "evidence": [], "limitations": [], "confidence": "Low"},
            "visualization": {"recommended": False},
            "warnings": [],
            "errors": ["Question cannot be empty."],
        }

    if not datasets:
        return {
            "status": "error",
            "question": q_clean,
            "intent": {},
            "query_plan": {},
            "validation": {"valid": False, "errors": ["No datasets available."]},
            "result": {},
            "evidence": {},
            "answer": {"answer": "No dataset loaded. Please upload a CSV or Excel file to begin.", "key_points": [], "evidence": [], "limitations": [], "confidence": "Low"},
            "visualization": {"recommended": False},
            "warnings": [],
            "errors": ["No datasets available."],
        }

    # 2. Contextual follow-up resolution & Intent Detection
    resolved_q, modified_plan = ConversationContextManager.resolve_follow_up(q_clean, context or {})
    provider_name = "Deterministic Semantic Engine"

    if modified_plan:
        query_plan = modified_plan
        intent_res = {"intent": query_plan.get("intent", "TOP_N"), "confidence": 0.95, "reason": "Follow-up contextual resolution."}
        provider_name = "Conversational Memory Resolver"
    else:
        intent_res = detect_query_intent(q_clean, metadata, context)
        # 3. Query Planning (LLM with strict fallback to semantic engine)
        query_plan, provider_name = LLMQueryPlanner.plan_query(q_clean, metadata, context=context, default_dataset=default_dataset)

    # Check if planner identified ambiguity (e.g. "What is the average price?" with modal/min/max)
    if query_plan.get("needs_clarification"):
        q_text = query_plan.get("clarification_question", "Please clarify which column or dataset you wish to analyze.")
        options = query_plan.get("clarification_options", [])
        plan_meta = query_plan.get("metadata", {}) or {}
        candidates = plan_meta.get("clarification_candidates", [])
        labels = plan_meta.get("clarification_labels", [])
        return {
            "status": "needs_clarification",
            "question": q_clean,
            "intent": intent_res,
            "query_plan": query_plan,
            "clarification_candidates": candidates,
            "clarification_labels": labels,
            "validation": {
                "valid": False,
                "requires_clarification": True,
                "clarification_question": q_text,
                "clarification_options": options,
                "clarification_candidates": candidates,
                "clarification_labels": labels,
            },
            "result": {},
            "evidence": {},
            "answer": {
                "answer": q_text,
                "key_points": [f"Candidate options: {', '.join(labels or options)}"],
                "evidence": [],
                "limitations": ["Ambiguous query requires user disambiguation."],
                "confidence": "Medium",
            },
            "visualization": {"recommended": False},
            "warnings": [],
            "errors": [],
        }

    # 4. Query Validation
    validation_res = validate_query_plan(query_plan, datasets, metadata, relationships, cfg)
    warnings.extend(validation_res.get("warnings", []))

    if validation_res.get("requires_clarification"):
        return {
            "status": "needs_clarification",
            "question": q_clean,
            "intent": intent_res,
            "query_plan": query_plan,
            "validation": validation_res,
            "result": {},
            "evidence": {},
            "answer": {
                "answer": validation_res.get("clarification_question", "Please clarify your query."),
                "key_points": [],
                "evidence": [],
                "limitations": [],
                "confidence": "Medium",
            },
            "visualization": {"recommended": False},
            "warnings": warnings,
            "errors": [],
        }

    if not validation_res.get("valid"):
        val_errors = validation_res.get("errors", ["Query plan failed validation."])
        errors.extend(val_errors)
        missing_csv_msg = next((m for m in val_errors if m.startswith("This information is not available in the uploaded CSV")), None)
        ans_text = missing_csv_msg if missing_csv_msg else f"Unable to process query: {'; '.join(val_errors)}"
        return {
            "status": "error",
            "question": q_clean,
            "intent": intent_res,
            "query_plan": query_plan,
            "validation": validation_res,
            "result": {},
            "evidence": {},
            "answer": {
                "answer": ans_text,
                "key_points": val_errors,
                "evidence": [],
                "limitations": ["Query rejected by validation safety layer."],
                "confidence": "Low",
            },
            "visualization": {"recommended": False},
            "warnings": warnings,
            "errors": errors,
        }

    # 5. Deterministic Safe Execution
    exec_res = execute_query(
        query_plan=query_plan,
        datasets=datasets,
        cleaned_datasets=cleaned_datasets,
        phase5_results=phase5_results,
        phase4_results=phase4_results,
        relationships=relationships,
        join_audit=join_audit,
        config=cfg,
    )
    warnings.extend(exec_res.get("warnings", []))
    errors.extend(exec_res.get("errors", []))

    if exec_res.get("status") == "error":
        return {
            "status": "error",
            "question": q_clean,
            "intent": intent_res,
            "query_plan": query_plan,
            "validation": validation_res,
            "result": exec_res,
            "evidence": {},
            "answer": {
                "answer": f"Query execution failed: {'; '.join(exec_res.get('errors', []))}",
                "key_points": exec_res.get("errors", []),
                "evidence": [],
                "limitations": [],
                "confidence": "Low",
            },
            "visualization": {"recommended": False},
            "warnings": warnings,
            "errors": errors,
        }

    # 6. Evidence Extraction
    evidence = extract_query_evidence(query_plan, exec_res)

    # 7. Answer Generation
    answer = generate_query_answer(q_clean, query_plan, exec_res, evidence, cfg)

    # 8. Visualization Recommendation & Generation
    visualization = recommend_query_visualization(q_clean, query_plan, exec_res)

    return {
        "status": "success",
        "question": q_clean,
        "provider": provider_name,
        "intent": intent_res,
        "query_plan": query_plan,
        "validation": validation_res,
        "result": exec_res,
        "evidence": evidence,
        "answer": answer,
        "visualization": visualization,
        "warnings": warnings,
        "errors": errors,
    }


def run_ask_analyst_query(
    question: str,
    datasets: Dict[str, pd.DataFrame],
    metadata: Dict[str, Any],
    cleaned_datasets: Optional[Dict[str, pd.DataFrame]] = None,
    phase4_results: Optional[Dict[str, Any]] = None,
    phase5_results: Optional[Dict[str, Any]] = None,
    relationships: Optional[List[Any]] = None,
    join_audit: Optional[List[Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    default_dataset: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute complete Phase 6 natural language query analysis pipeline.

    Supports single analytical questions as well as coordinated multi-part / mixed questions.
    """
    cfg = normalize_query_config(config)
    q_clean = question.strip() if question else ""

    # Basic validations
    if not q_clean:
        return {
            "status": "error",
            "question": "",
            "intent": {},
            "query_plan": {},
            "validation": {"valid": False, "errors": ["No question provided."]},
            "result": {},
            "evidence": {},
            "answer": {"answer": "Please provide a question to analyze.", "key_points": [], "evidence": [], "limitations": [], "confidence": "Low"},
            "visualization": {"recommended": False},
            "warnings": [],
            "errors": ["Question cannot be empty."],
        }

    if not datasets:
        return {
            "status": "error",
            "question": q_clean,
            "intent": {},
            "query_plan": {},
            "validation": {"valid": False, "errors": ["No datasets available."]},
            "result": {},
            "evidence": {},
            "answer": {"answer": "No dataset loaded. Please upload a CSV or Excel file to begin.", "key_points": [], "evidence": [], "limitations": [], "confidence": "Low"},
            "visualization": {"recommended": False},
            "warnings": [],
            "errors": ["No datasets available."],
        }

    # 1. Multi-part question splitting
    sub_questions = split_multi_part_question(q_clean)
    if len(sub_questions) > 1:
        sub_results = []
        for sq in sub_questions:
            res = _run_single_query(
                question=sq,
                datasets=datasets,
                metadata=metadata,
                cleaned_datasets=cleaned_datasets,
                phase4_results=phase4_results,
                phase5_results=phase5_results,
                relationships=relationships,
                join_audit=join_audit,
                context=context,
                config=cfg,
                default_dataset=default_dataset,
            )
            sub_results.append((sq, res))

        # Format into clean, numbered sections
        answer_sections = []
        all_key_points = []
        all_evidence = []
        all_limitations = []
        all_warnings = []
        all_errors = []
        primary_viz = {"recommended": False}
        primary_result = {}
        primary_plan = {}

        def _clean_instruction_tail(text: str) -> str:
            cleaned = re.sub(
                r"(?:[\.;]\s*|\s+)(?:return\s+(?:only\s+)?(?:a\s+)?(?:\w+[- ]\w+\s+)?table|do\s+not\s+include|without\s+outlier|without\s+correlation|without\s+suggestion|exclude\s+outlier|exclude\s+correlation|exclude\s+suggestion|table\s+only|only\s+a\s+table)\b.*$",
                "",
                text.strip(),
                flags=re.IGNORECASE,
            )
            return cleaned.strip()

        for idx, (sq, res) in enumerate(sub_results, 1):
            sq_title = _clean_instruction_tail(sq)
            title_text = sq_title.rstrip("?.,")
            title_clean = title_text.capitalize()

            res_ans = res.get("answer", {})
            ans_text = res_ans.get("answer", "")

            if res.get("status") == "success":
                answer_sections.append(f"### {idx}. {title_clean}\n{ans_text}")
                if not primary_result:
                    primary_result = res.get("result", {})
                    primary_plan = res.get("query_plan", {})
                elif isinstance(res.get("result", {}).get("data"), pd.DataFrame) and len(res.get("result", {}).get("data")) > 1:
                    prev_data = primary_result.get("data")
                    if prev_data is None or not isinstance(prev_data, pd.DataFrame) or len(prev_data) <= 1:
                        primary_result = res.get("result", {})
                        primary_plan = res.get("query_plan", {})
                if not primary_viz.get("recommended") and res.get("visualization", {}).get("recommended"):
                    primary_viz = res.get("visualization")
            elif res.get("status") == "needs_clarification":
                clarif_q = res.get("validation", {}).get("clarification_question") or ans_text
                answer_sections.append(f"### {idx}. {title_clean}\n*Clarification required*: {clarif_q}")
            else:
                clean_err = ans_text
                if not clean_err.startswith("This information is not available") and not clean_err.startswith("Cannot determine"):
                    clean_err = f"This information is not available in the uploaded CSV: {clean_err}"
                answer_sections.append(f"### {idx}. {title_clean}\n{clean_err}")

            all_key_points.extend(res_ans.get("key_points", []))
            all_evidence.extend(res_ans.get("evidence", []))
            all_limitations.extend(res_ans.get("limitations", []))
            all_warnings.extend(res.get("warnings", []))
            all_errors.extend(res.get("errors", []))

        combined_answer_md = "\n\n".join(answer_sections)
        any_success = any(r.get("status") == "success" for _, r in sub_results)

        # Check if scalar sub-results can be merged into a coordinated multi-row Metric & Value table
        scalar_rows = []
        for sq, res in sub_results:
            if res.get("status") == "success":
                r_payload = res.get("result", {})
                r_data = r_payload.get("data")
                if isinstance(r_data, pd.DataFrame) and len(r_data) == 1:
                    row_0 = r_data.iloc[0]
                    for col_name, val in row_0.items():
                        m_name = str(col_name).replace("_", " ").title()
                        if "Sum " in m_name and not m_name.startswith("Sum Of"):
                            m_name = m_name.replace("Sum ", "Sum of ")
                        if isinstance(val, (float, np.floating)):
                            v_str = f"{val:,.2f}"
                        elif isinstance(val, (int, np.integer)):
                            v_str = f"{val:,}"
                        else:
                            v_str = str(val)
                        scalar_rows.append({"Metric": m_name, "Value": v_str})

        target_ds_name = default_dataset or (list(datasets.keys())[0] if datasets else "")
        evaluated_cnt = len(datasets[target_ds_name]) if target_ds_name in datasets else (len(list(datasets.values())[0]) if datasets else 0)

        has_multi_row_grouped_result = any(
            isinstance(r.get("result", {}).get("data"), pd.DataFrame) and len(r.get("result", {}).get("data")) > 1
            for _, r in sub_results
        )
        if len(scalar_rows) >= 2 and not has_multi_row_grouped_result and (
            "table with metric and value" in q_clean.lower()
            or "two-row table" in q_clean.lower()
            or "2-row table" in q_clean.lower()
            or "metric and value" in q_clean.lower()
            or len(scalar_rows) == len(sub_results)
        ):
            comb_df = pd.DataFrame(scalar_rows)
            primary_result = {
                "result_type": "table",
                "data": comb_df,
                "columns": ["Metric", "Value"],
                "row_count": len(comb_df),
                "evidence": {
                    "dataset_source": target_ds_name,
                    "evaluated_records": evaluated_cnt,
                    "total_dataset_rows": evaluated_cnt,
                },
                "warnings": all_warnings,
            }

            is_table_requested = (
                bool(re.search(r"\b(?:return\s+)?(?:only\s+)?(?:a\s+|the\s+)?(?:two|2)[ -]row\s+table\b", q_clean, re.IGNORECASE))
                or bool(re.search(r"\b(?:return\s+)?(?:only\s+)?(?:a\s+|the\s+)?(?:two|2)[ -]column\s+table\b", q_clean, re.IGNORECASE))
                or bool(re.search(r"\b(?:return\s+)?only\s+(?:a\s+|the\s+)?(?:resulting\s+)?table\b|\b(?:resulting\s+)?table\s+only\b", q_clean, re.IGNORECASE))
                or "two-row table with metric and value" in q_clean.lower()
            )

            if is_table_requested:
                table_md_lines = ["| Metric | Value |", "| :--- | :--- |"]
                for s_row in scalar_rows:
                    table_md_lines.append(f"| {s_row['Metric']} | {s_row['Value']} |")
                table_md = "\n".join(table_md_lines)
                combined_answer_md = table_md

        return {
            "status": "success" if any_success else "error",
            "question": q_clean,
            "provider": "Multi-Part Analytical Orchestrator",
            "intent": {
                "intent": "MULTI_PART",
                "confidence": 0.95,
                "reason": f"Executed {len(sub_questions)} coordinated sub-questions across uploaded CSV data.",
                "sub_questions": sub_questions,
            },
            "query_plan": primary_plan or {"intent": "MULTI_PART", "sub_questions": sub_questions},
            "validation": {"valid": True, "errors": [], "warnings": all_warnings},
            "result": primary_result or {"data": None, "row_count": 0, "status": "success"},
            "evidence": {
                "dataset_used": target_ds_name,
                "dataset_source": target_ds_name,
                "evaluated_records": evaluated_cnt,
                "total_rows": evaluated_cnt,
                "total_dataset_rows": evaluated_cnt,
                "sub_results_count": len(sub_results),
            },
            "answer": {
                "answer": combined_answer_md,
                "key_points": all_key_points[:8],
                "evidence": all_evidence[:8],
                "limitations": all_limitations,
                "confidence": "High" if any_success else "Low",
            },
            "visualization": primary_viz,
            "sub_results": [r for _, r in sub_results],
            "warnings": all_warnings,
            "errors": all_errors,
        }

    # Single analytical question
    return _run_single_query(
        question=q_clean,
        datasets=datasets,
        metadata=metadata,
        cleaned_datasets=cleaned_datasets,
        phase4_results=phase4_results,
        phase5_results=phase5_results,
        relationships=relationships,
        join_audit=join_audit,
        context=context,
        config=cfg,
        default_dataset=default_dataset,
    )
