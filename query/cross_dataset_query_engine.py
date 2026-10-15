"""Cross-Dataset Query Engine for Phase 6 Natural Language Query Engine.

Executes cross-dataset joins and aggregations strictly through validated relationships.
Enforces safeguards against:
- Unverified same-name column joins
- Joins on Unnamed:*, row numbers, or index artifacts
- Unsafe Many-to-Many joins
- Row explosion exceeding configured growth ratios
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import pandas as pd
from models.relationship import Relationship, JoinAudit
from query.config import normalize_query_config


IGNORED_JOIN_TERMS = ["unnamed", "index", "level_0", "row_num", "row_id", "serial"]


def _is_safe_key_name(col_name: str) -> bool:
    """Check whether a column name is not an index artifact or unnamed column."""
    c_lower = str(col_name).lower()
    return not any(term in c_lower for term in IGNORED_JOIN_TERMS)


def execute_cross_dataset_query(
    left_name: str,
    right_name: str,
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    relationships: Optional[List[Relationship]] = None,
    query_plan: Optional[Dict[str, Any]] = None,
    join_audit: Optional[List[Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute safe cross-dataset analysis using verified relationships."""
    cfg = normalize_query_config(config)
    warnings: List[str] = []

    if left_df is None or left_df.empty or right_df is None or right_df.empty:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": ["One or both datasets are empty."],
        }

    # 1. Identify validated relationship
    if not relationships:
        return {
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [f"No validated relationships found connecting '{left_name}' and '{right_name}'."],
        }

    valid_rel: Optional[Relationship] = None
    for r in relationships:
        s_ds = getattr(r, "source_dataset", "")
        t_ds = getattr(r, "target_dataset", "")
        if (s_ds == left_name and t_ds == right_name) or (s_ds == right_name and t_ds == left_name):
            valid_rel = r
            break

    if not valid_rel:
        return {
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [f"No verified relationship exists connecting '{left_name}' and '{right_name}'. Cross-dataset join refused."],
        }

    # Identify keys based on orientation
    if valid_rel.source_dataset == left_name:
        left_key = valid_rel.source_column
        right_key = valid_rel.target_column
    else:
        left_key = valid_rel.target_column
        right_key = valid_rel.source_column

    # 2. Key safety check
    if not _is_safe_key_name(left_key) or not _is_safe_key_name(right_key):
        return {
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [f"Join rejected: Columns '{left_key}' or '{right_key}' appear to be index artifacts."],
        }

    # 3. Many-to-Many Guard
    rel_type = getattr(valid_rel, "relationship_type", "Many-to-One")
    if rel_type == "Many-to-Many" and not cfg.get("allow_many_to_many", False):
        msg = f"Join rejected: Many-to-Many relationship between '{left_name}.{left_key}' and '{right_name}.{right_key}' poses severe row explosion risk."
        if join_audit is not None:
            audit = JoinAudit(
                left_dataset=left_name,
                left_key=left_key,
                right_dataset=right_name,
                right_key=right_key,
                join_type="INNER",
                confidence=getattr(valid_rel, "confidence", "LOW"),
                overlap_percentage=getattr(valid_rel, "value_overlap_pct", 0.0),
                rows_before=len(left_df),
                rows_after=len(left_df),
                status="REJECTED_ROW_EXPLOSION",
                notes=msg,
            )
            join_audit.append(audit)
        return {
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [msg],
        }

    # 4. Perform Join
    rows_before = len(left_df)
    try:
        joined_df = pd.merge(
            left_df,
            right_df,
            left_on=left_key,
            right_on=right_key,
            how="inner",
            suffixes=(f"_{left_name.split('.')[0]}", f"_{right_name.split('.')[0]}"),
        )
    except Exception as e:
        return {
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [f"Merge failed: {str(e)}"],
        }

    rows_after = len(joined_df)
    growth_ratio = (rows_after / max(rows_before, 1))

    # 5. Row explosion check
    max_growth = cfg.get("max_join_row_growth_ratio", 2.0)
    if growth_ratio > max_growth:
        msg = f"Join aborted: Output rows ({rows_after:,}) exceeded safe growth ratio {max_growth}x over input ({rows_before:,})."
        if join_audit is not None:
            audit = JoinAudit(
                left_dataset=left_name,
                left_key=left_key,
                right_dataset=right_name,
                right_key=right_key,
                join_type="INNER",
                confidence=getattr(valid_rel, "confidence", "LOW"),
                overlap_percentage=getattr(valid_rel, "value_overlap_pct", 0.0),
                rows_before=rows_before,
                rows_after=rows_after,
                status="REJECTED_ROW_EXPLOSION",
                row_ratio=growth_ratio,
                notes=msg,
            )
            join_audit.append(audit)
        return {
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [msg],
        }

    # Log successful join audit
    if join_audit is not None:
        audit = JoinAudit(
            left_dataset=left_name,
            left_key=left_key,
            right_dataset=right_name,
            right_key=right_key,
            join_type="INNER",
            confidence=getattr(valid_rel, "confidence", "HIGH"),
            overlap_percentage=getattr(valid_rel, "value_overlap_pct", 100.0),
            rows_before=rows_before,
            rows_after=rows_after,
            status="SUCCESS",
            row_ratio=growth_ratio,
            notes="Safe cross-dataset join executed.",
        )
        join_audit.append(audit)

    evidence = {
        "left_dataset": left_name,
        "left_key": left_key,
        "right_dataset": right_name,
        "right_key": right_key,
        "relationship_type": rel_type,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "growth_ratio": round(growth_ratio, 2),
    }

    # If query plan has grouping and aggregation, compute on joined table
    if query_plan:
        group_by = query_plan.get("group_by", [])
        column = query_plan.get("column")
        aggregation = query_plan.get("aggregation", "sum")
        limit = query_plan.get("limit", 10)
        sort = query_plan.get("sort", "descending")

        # Check if columns are in joined_df
        matching_groups = [g for g in group_by if g in joined_df.columns]
        if matching_groups and column and column in joined_df.columns:
            from query.aggregation_engine import compute_aggregation
            agg_res = compute_aggregation(
                joined_df,
                column=column,
                aggregation=aggregation,
                group_by=matching_groups,
                sort=sort,
                limit=limit,
            )
            agg_res["evidence"] = {**evidence, **agg_res.get("evidence", {})}
            agg_res["warnings"] = warnings + agg_res.get("warnings", [])
            return agg_res

    # Default: return preview of joined DataFrame
    return {
        "result_type": "table",
        "data": joined_df.head(25),
        "columns": list(joined_df.columns),
        "row_count": len(joined_df),
        "evidence": evidence,
        "warnings": warnings,
    }
