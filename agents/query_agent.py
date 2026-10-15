"""Query Agent - Translates natural language questions into safe, deterministic Pandas operations.

Phase 6 Implementation: End-to-end intelligent query execution adhering to structured
query plans, strict validation, zero arbitrary code execution, and evidence-grounded answers.
"""

from typing import Dict, Any, Optional, List
import pandas as pd
from core.config import config
from query.orchestrator import run_ask_analyst_query
from query.query_planner import build_query_plan
from query.query_validator import validate_query_plan
from query.query_models import StructuredQueryPlan


class QueryAgent:
    """Agent responsible for semantic query understanding, planning, and safe execution."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.version = "Phase 6 - Intelligent Ask Analyst & Natural-Language Data Query"

    def plan_query(
        self,
        question: str,
        metadata: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convert natural language question into a validated structured query plan."""
        return build_query_plan(question, metadata, context)

    def validate_plan(
        self,
        query_plan: Dict[str, Any],
        datasets: Dict[str, pd.DataFrame],
        metadata: Dict[str, Any],
        relationships: Optional[List[Any]] = None,
        query_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate structured query plan prior to execution."""
        return validate_query_plan(query_plan, datasets, metadata, relationships, query_config)

    def execute(
        self,
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
        """Run the complete end-to-end Phase 6 analytical pipeline."""
        return run_ask_analyst_query(
            question=question,
            datasets=datasets,
            metadata=metadata,
            cleaned_datasets=cleaned_datasets,
            phase4_results=phase4_results,
            phase5_results=phase5_results,
            relationships=relationships,
            join_audit=join_audit,
            context=context,
            config=config,
        )
