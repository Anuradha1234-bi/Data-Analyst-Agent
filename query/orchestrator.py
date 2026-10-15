"""Main Query Orchestrator for Phase 6 Natural Language Query Engine.

Coordinates the end-to-end analytical workflow:
Question -> Intent -> Query Plan -> Validation -> Safe Execution -> Evidence -> Answer -> Visualization.
"""

from typing import Dict, Any, List, Optional
import pandas as pd

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
) -> Dict[str, Any]:
    """Execute complete Phase 6 natural language query analysis pipeline.

    Contract:
    Returns:
    {
        "status": "success" | "needs_clarification" | "error",
        "question": str,
        "intent": dict,
        "query_plan": dict,
        "validation": dict,
        "result": dict,
        "evidence": dict,
        "answer": dict,
        "visualization": dict,
        "warnings": list,
        "errors": list
    }
    """
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
        query_plan, provider_name = LLMQueryPlanner.plan_query(q_clean, metadata, context=context)

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
        return {
            "status": "error",
            "question": q_clean,
            "intent": intent_res,
            "query_plan": query_plan,
            "validation": validation_res,
            "result": {},
            "evidence": {},
            "answer": {
                "answer": f"Unable to process query: {'; '.join(val_errors)}",
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
