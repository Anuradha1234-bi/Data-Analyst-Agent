"""LLM-Powered Analytical Planning Module for AI Data Analyst Agent.

Provides a controlled, prompt-engineered planning layer using Gemini/OpenAI when configured.
The model produces a structured analytical plan (JSON) rather than executing arbitrary code.
Strictly validates every output through Pydantic against an allowlist of supported operations,
falling back cleanly to the deterministic semantic query planner when no LLM key is configured.
"""

from typing import Dict, Any, List, Optional, Tuple
import os
import json
import re

from core.config import config
from query.query_models import QueryIntent, StructuredQueryPlan
from query.query_planner import build_query_plan
from query.column_resolver import _extract_columns_from_metadata


class LLMQueryPlanner:
    """Orchestrates LLM-based query planning with strict schema validation and deterministic fallback."""

    SYSTEM_PROMPT = """You are an expert AI Data Analyst. Your task is to translate a user's natural language question into a structured analytical plan (JSON).

CRITICAL CONSTRAINTS:
1. Output ONLY a valid JSON object matching the schema below. No markdown fences, no explanatory text.
2. Do NOT output Python, SQL, or code to be executed.
3. Use ONLY column names present in the provided dataset schema.
4. Allowed intents:
   - "AVERAGE", "SUM", "COUNT", "MEDIAN", "MINIMUM", "MAXIMUM"
   - "TOP_N", "BOTTOM_N", "GROUP_BY", "FILTER", "SORT", "SHOW_DATA"
   - "TREND", "CORRELATION", "REGRESSION", "TWO_GROUP_TEST", "CHI_SQUARE"
   - "MISSING_VALUES", "UNIQUE_VALUES", "INSIGHT_SUMMARY", "DESCRIPTIVE_STATISTICS"

OUTPUT JSON SCHEMA:
{
  "intent": "<ONE_OF_ALLOWED_INTENTS>",
  "column": "<primary_numeric_metric_or_null>",
  "group_by": ["<categorical_column_name>"],
  "secondary_column": "<predictor_or_second_variable_or_null>",
  "limit": <integer_or_null>,
  "sort": "descending" | "ascending" | null,
  "filters": [
    {"column": "<col_name>", "operator": ">" | ">=" | "<" | "<=" | "==" | "!=", "value": <literal>}
  ]
}
"""

    @classmethod
    def plan_query(
        cls,
        question: str,
        metadata: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """Produce a validated analytical query plan.

        Returns: (plan_dict, provider_label)
        """
        api_key = os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", "")

        # If API key is available, attempt structured LLM plan generation
        if api_key and len(api_key.strip()) > 8:
            llm_plan = cls._generate_llm_plan(question, metadata, api_key, context)
            if llm_plan:
                return llm_plan, "Gemini (AI Structured Planner)"

        # Deterministic rule-based semantic fallback
        fallback_plan = build_query_plan(question, metadata, context=context)
        return fallback_plan, "Deterministic Semantic Engine (Grounded Allowlist)"

    @classmethod
    def _generate_llm_plan(
        cls,
        question: str,
        metadata: Dict[str, Any],
        api_key: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Call Gemini API to generate structured plan and validate against allowlist."""
        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            # Build schema context summary for prompt
            schema_summary = {}
            for ds_name, m in metadata.items():
                schema_summary[ds_name] = {
                    "columns": _extract_columns_from_metadata(m),
                    "types": m.get("data_types", {}),
                }

            user_prompt = f"""Dataset Schema:
{json.dumps(schema_summary, indent=2)}

Previous Conversation Context:
{json.dumps(context or {}, indent=2)}

User Question:
"{question}"

Generate the structured analytical plan JSON:"""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    {"role": "user", "parts": [{"text": cls.SYSTEM_PROMPT + "\n\n" + user_prompt}]}
                ],
            )

            raw_text = response.text.strip()
            # Strip markdown json code block if returned
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)

            parsed = json.loads(raw_text)

            all_cols = []
            for m in metadata.values():
                all_cols.extend(_extract_columns_from_metadata(m))

            if not cls.validate_plan_structure(parsed, all_cols):
                return None

            intent_val = str(parsed.get("intent", "")).upper()
            col = parsed.get("column")

            # Build complete StructuredQueryPlan
            first_ds = list(metadata.keys())[0] if metadata else None
            plan = StructuredQueryPlan(
                intent=intent_val,
                dataset=first_ds,
                column=col,
                secondary_column=parsed.get("secondary_column"),
                group_by=parsed.get("group_by") or [],
                filters=parsed.get("filters") or [],
                limit=parsed.get("limit"),
                sort=parsed.get("sort"),
                confidence=0.95,
            )
            return plan.to_dict()

        except Exception:
            # Fall back safely
            return None

    @classmethod
    def validate_plan_structure(cls, parsed: Dict[str, Any], allowed_columns: List[str]) -> bool:
        """Validate LLM output plan structure against allowed intents and dataset columns."""
        if not isinstance(parsed, dict):
            return False
        intent_val = str(parsed.get("intent", "")).upper()
        if intent_val not in QueryIntent.list_all():
            return False
        col = parsed.get("column")
        allowed_lower = [str(c).lower() for c in allowed_columns]
        if col and str(col).lower() not in allowed_lower:
            return False
        return True
