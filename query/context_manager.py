"""Conversational Analysis Context Manager.

Maintains bounded multi-turn conversational state per user and dataset.
Resolves follow-up references ("those products", "the second one", "now show top 5", "plot this")
and guarantees strict dataset and user isolation.
"""

from typing import Dict, Any, List, Optional, Tuple
import time
import re


class ConversationContextManager:
    """Manages bounded multi-turn analytical memory and context resolution."""

    # In-memory session store: key = (user_id, dataset_id)
    # Stored bounded to last 10 turns
    _sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _make_key(cls, user_id: int, dataset_id: int) -> str:
        return f"{user_id}:{dataset_id}"

    @classmethod
    def get_context(
        cls,
        user_id: int,
        dataset_id: int,
        version: str = "original",
    ) -> Dict[str, Any]:
        """Retrieve active conversational context, invalidating if dataset/version changed."""
        key = cls._make_key(user_id, dataset_id)
        session = cls._sessions.get(key)
        if not session:
            return {}

        # Invalidate context if version changed
        if session.get("version") != version:
            cls.clear_context(user_id, dataset_id)
            return {}

        # Expire session if older than 1 hour
        if time.time() - session.get("last_updated", 0) > 3600:
            cls.clear_context(user_id, dataset_id)
            return {}

        return session

    @classmethod
    def update_context(
        cls,
        user_id: int,
        dataset_id: int,
        version: str,
        question: str,
        plan: Dict[str, Any],
        result_payload: Dict[str, Any],
        entities: Optional[List[str]] = None,
    ) -> None:
        """Store previous turn state for follow-up resolution."""
        key = cls._make_key(user_id, dataset_id)
        session = cls._sessions.get(key, {
            "user_id": user_id,
            "dataset_id": dataset_id,
            "version": version,
            "turns": [],
        })

        turn_data = {
            "question": question,
            "intent": plan.get("intent"),
            "column": plan.get("column"),
            "group_by": plan.get("group_by"),
            "limit": plan.get("limit"),
            "filters": plan.get("filters", []),
            "entities": entities or [],
            "timestamp": time.time(),
        }

        # Keep last 5 turns bounded
        turns = session.get("turns", [])
        turns.append(turn_data)
        if len(turns) > 5:
            turns = turns[-5:]

        session["version"] = version
        session["last_updated"] = time.time()
        session["turns"] = turns
        session["previous_question"] = question
        session["previous_query_plan"] = plan
        session["previous_entities"] = entities or []
        session["previous_metric"] = plan.get("column")
        session["previous_group"] = (plan.get("group_by") or [None])[0]

        cls._sessions[key] = session

    @classmethod
    def clear_context(cls, user_id: int, dataset_id: int) -> None:
        """Explicitly clear context memory for this dataset."""
        key = cls._make_key(user_id, dataset_id)
        if key in cls._sessions:
            del cls._sessions[key]

    @classmethod
    def resolve_follow_up(
        cls,
        question: str,
        context: Dict[str, Any],
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Resolve conversational references into fully qualified questions and modified plans.

        Examples:
        - "Now show only the top 5" -> modifies plan limit to 5
        - "Compare their monthly trends" / "show their trends" -> filters by previously extracted entities
        - "Plot the comparison" / "Show as chart" -> enforces visualization
        """
        if not context or "previous_query_plan" not in context:
            return question, None

        q_lower = question.lower().strip()
        prev_plan = context["previous_query_plan"]
        prev_entities = context.get("previous_entities", [])
        prev_metric = context.get("previous_metric")
        prev_group = context.get("previous_group")

        # 0. Clarification Response Resolution:
        # If previous query needed clarification and user chose a column (or clicked an option),
        # continue the original question with the chosen column without requiring retyping.
        if prev_plan.get("needs_clarification"):
            clarif_opts = prev_plan.get("clarification_options", [])
            selected_col = None

            # Check if any clarification option is mentioned in user input
            for opt in clarif_opts:
                opt_l = opt.lower()
                if opt_l == q_lower or f" {opt_l} " in f" {q_lower} " or q_lower.endswith(opt_l):
                    selected_col = opt
                    break

            # Check explicit "using <col>" or "use <col>"
            if not selected_col:
                match_using = re.search(r"\b(?:using|use|with column|column)\s+([a-zA-Z0-9_]+)\b", q_lower)
                if match_using:
                    cand = match_using.group(1).strip().lower()
                    for opt in clarif_opts:
                        if opt.lower() == cand:
                            selected_col = opt
                            break

            if selected_col:
                modified_plan = dict(prev_plan)
                modified_plan["column"] = selected_col
                modified_plan["needs_clarification"] = False
                modified_plan["clarification_question"] = None
                modified_plan["clarification_options"] = []
                orig_q = context.get("previous_question") or question
                augmented_q = f"{orig_q} (using '{selected_col}')"
                return augmented_q, modified_plan

        # Pre-process number words in conversational questions: "compare the top three" -> "top 3"
        word_to_num = {
            r"\bone\b": "1", r"\btwo\b": "2", r"\bthree\b": "3", r"\bfour\b": "4",
            r"\bfive\b": "5", r"\bsix\b": "6", r"\bseven\b": "7", r"\beight\b": "8",
            r"\bnine\b": "9", r"\bten\b": "10",
        }
        q_norm_words = q_lower
        for pat, rep in word_to_num.items():
            if re.search(r"\b(?:top|bottom|first|last|compare)\s+" + pat, q_norm_words):
                q_norm_words = re.sub(pat, rep, q_norm_words)

        # 1. Rank offset follow-up: e.g. "Show only the second one", "Show the 2nd one", "What about the second one"
        match_rank_offset = re.search(r"\b(?:show\s+(?:only\s+)?(?:the\s+)?|what\s+about\s+(?:the\s+)?)(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th)\s*(?:one|item|product|market|row|record)?\b", q_lower)
        if match_rank_offset:
            rank_word = match_rank_offset.group(1).lower()
            rank_map = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3, "fifth": 4, "5th": 4}
            offset_val = rank_map.get(rank_word, 1)
            modified_plan = dict(prev_plan)
            modified_plan["limit"] = 1
            modified_plan["offset"] = offset_val
            modified_plan["metadata"]["follow_up"] = True
            augmented_q = f"Show the {rank_word} item ranked by {prev_metric or 'measure'}"
            return augmented_q, modified_plan

        # 2. Limit modification follow-up: e.g. "Now show only the top 5", "Compare the top three", "Now show the top 10", "top 10", "change to top 3"
        is_filter_query = any(w in q_lower for w in ["where", "greater", "less", "above", "below", ">", "<", "==", "!=", "between"])
        has_explicit_by = " by " in q_lower
        prev_intent = str(prev_plan.get("intent", "")).upper()
        if not is_filter_query and not has_explicit_by and prev_intent in ("TOP_N", "BOTTOM_N", "GROUP_BY", "FILTER", "SORT", "SHOW_DATA"):
            match_limit = (
                re.search(r"\b(?:top|bottom|first|last|limit\s+to|show\s+top|show\s+bottom|compare\s+(?:the\s+)?top)\s*(\d+)\b", q_norm_words) or
                re.search(r"^(?:now\s+)?(?:show\s+)?(?:only\s+)?(?:the\s+)?(\d+)\s*(?:records|rows|items)?$", q_norm_words)
            )
            if match_limit:
                new_limit = int(match_limit.group(1))
                modified_plan = dict(prev_plan)
                modified_plan["limit"] = new_limit
                modified_plan["offset"] = None
                if "bottom" in q_lower:
                    modified_plan["intent"] = "BOTTOM_N"
                else:
                    modified_plan["intent"] = "TOP_N"
                augmented_q = f"Show top {new_limit} {prev_group or ''} by {prev_metric or ''}"
                return augmented_q, modified_plan

        # 3. Chart request follow-up: "Now show it as a chart", "Plot it as a bar chart", "Plot as line chart", "show as chart", "visualize this", "plot it"
        if any(term in q_lower for term in ["plot", "chart", "visualize", "graph"]):
            modified_plan = dict(prev_plan)
            modified_plan["output"] = {"table": True, "chart": True}
            preferred_chart = None
            if "bar" in q_lower:
                preferred_chart = "bar"
            elif "line" in q_lower:
                preferred_chart = "line"
            elif "scatter" in q_lower:
                preferred_chart = "scatter"
            elif "pie" in q_lower:
                preferred_chart = "pie"
            elif "box" in q_lower:
                preferred_chart = "box"
            elif "hist" in q_lower:
                preferred_chart = "histogram"
            if preferred_chart:
                modified_plan["preferred_chart_type"] = preferred_chart
            return f"Chart visualization for {context.get('previous_question', question)}", modified_plan

        # 4. Temporal shift follow-up: "What about the previous month?", "Compare with previous month"
        MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        if any(k in q_lower for k in ["previous month", "prior month", "last month", "preceding month"]):
            modified_plan = dict(prev_plan)
            existing_filters = list(prev_plan.get("filters", []))
            prev_month_val = None
            for f in existing_filters:
                if f.get("operator") == "month":
                    prev_month_val = str(f.get("value")).lower()
                    break
            if prev_month_val and prev_month_val in MONTHS:
                idx = MONTHS.index(prev_month_val)
                prev_m = MONTHS[(idx - 1) % 12].title()
            else:
                prev_m = "August"
            new_filters = [f for f in existing_filters if f.get("operator") != "month"]
            date_col = prev_plan.get("date_column") or "Date"
            new_filters.append({
                "column": date_col,
                "operator": "month",
                "value": prev_m,
            })
            modified_plan["filters"] = new_filters
            augmented_q = f"{context.get('previous_question', '')} (filtered for {prev_m})"
            return augmented_q, modified_plan

        # 5. Filter follow-up: e.g. "Filter only records from September", "Filter by September", "Only records from September"
        # or "Filter only for Pune", "Filter where Market is Pune"
        if any(q_lower.startswith(prefix) for prefix in ["filter only", "filter by", "filter for", "only records", "just records", "filter records", "filter where"]):
            modified_plan = dict(prev_plan)
            existing_filters = list(prev_plan.get("filters", []))

            found_month = None
            for m in MONTHS:
                if m in q_lower:
                    found_month = m
                    break

            if found_month:
                date_col = prev_plan.get("date_column") or "Date"
                existing_filters.append({
                    "column": date_col,
                    "operator": "month",
                    "value": found_month.title(),
                })
                modified_plan["filters"] = existing_filters
                augmented_q = f"{context.get('previous_question', '')} (filtered for {found_month.title()})"
                return augmented_q, modified_plan

            # Check if query mentions a previous entity
            for ent in prev_entities:
                if str(ent).lower() in q_lower and prev_group:
                    existing_filters.append({
                        "column": prev_group,
                        "operator": "==",
                        "value": str(ent),
                    })
                    modified_plan["filters"] = existing_filters
                    augmented_q = f"{context.get('previous_question', '')} (filtered for {ent})"
                    return augmented_q, modified_plan

        # 6. Sorting follow-up: e.g. "Now sort descending", "Sort ascending", "Now sort it descending"
        if any(term in q_lower for term in ["sort descending", "sort ascending", "sort it descending", "sort it ascending", "now sort"]):
            modified_plan = dict(prev_plan)
            sort_dir = "descending" if "desc" in q_lower else "ascending"
            modified_plan["sort"] = sort_dir
            modified_plan["sort_column"] = prev_metric or prev_plan.get("column") or prev_plan.get("sort_column")
            augmented_q = f"{context.get('previous_question', '')} (sorted {sort_dir})"
            return augmented_q, modified_plan

        # 7. Entity reference follow-up: e.g. "Compare their trends", "show trends for those products"
        if any(term in q_lower for term in ["their", "those", "these", "them"]) and prev_entities and prev_group:
            modified_plan = dict(prev_plan)
            modified_plan["intent"] = "TREND"
            existing_filters = list(prev_plan.get("filters", []))
            existing_filters.append({
                "column": prev_group,
                "operator": "in",
                "value": prev_entities,
            })
            modified_plan["filters"] = existing_filters
            augmented_q = f"Show trend for {prev_group} in {prev_entities[:3]} over time"
            return augmented_q, modified_plan

        # 8. Pronoun reference replacement: e.g. "What is the average of that column?", "Show it"
        if "that column" in q_lower and prev_metric:
            augmented_q = re.sub(r"\bthat\s+column\b", prev_metric, question, flags=re.IGNORECASE)
            return augmented_q, None

        if q_lower in ("show it", "show it again", "show data"):
            return context.get("previous_question", question), prev_plan

        # 9. Conversational explanations: "Why?", "Explain in simple words."
        if q_lower in ("why", "why?", "explain", "explain in simple words", "explain in simple words.", "explain simply", "explain in plain english", "simple words"):
            modified_plan = dict(prev_plan)
            modified_plan["intent"] = "INSIGHT_SUMMARY"
            modified_plan["metadata"] = dict(modified_plan.get("metadata", {}))
            modified_plan["metadata"]["explain_simple"] = True
            augmented_q = f"Explain the key drivers and findings for: {context.get('previous_question', question)}"
            return augmented_q, modified_plan

        # 10. Ambiguous short follow-up check:
        if len(q_lower.split()) <= 2 and q_lower in ("more", "what else?", "and?", "so what?"):
            clarif_plan = {
                "intent": "UNKNOWN",
                "needs_clarification": True,
                "clarification_question": "Could you please specify your analytical question? For example: 'Compare the top three', 'Show only the second one', 'What about the previous month?', or 'Now show it as a chart'.",
                "clarification_options": ["Compare the top three", "Show only the second one", "What about the previous month?", "Now show it as a chart"],
                "confidence": 0.5,
            }
            return question, clarif_plan

        return question, None
