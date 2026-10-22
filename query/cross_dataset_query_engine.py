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

    # Check intent and query text
    intent = str(query_plan.get("intent", "")) if query_plan else ""
    q_str = str(query_plan.get("metadata", {}).get("question", "")).lower() if query_plan else ""

    # 1. Dataset comparison (Row counts / Column schemas) without requiring a join
    is_compare_rows = any(w in q_str for w in ["row count", "row counts", "total records", "number of rows", "records in"])
    is_compare_cols = any(w in q_str for w in ["column", "columns", "feature", "features", "schema"])
    is_pure_compare = intent == "COMPARE_DATASETS" or (
        any(k in q_str for k in ["compare row counts", "compare columns", "compare total records", "compare records between", "compare the row count"])
    )

    if is_pure_compare and not any(w in q_str for w in ["join", "merge", "across", "not present in", "absent in"]):
        left_cols = list(left_df.columns)
        right_cols = list(right_df.columns)
        left_set = set(left_cols)
        right_set = set(right_cols)
        shared_cols = sorted(list(left_set.intersection(right_set)))

        comp_df = pd.DataFrame([
            {"Dataset": left_name, "Row Count": len(left_df), "Column Count": len(left_cols)},
            {"Dataset": right_name, "Row Count": len(right_df), "Column Count": len(right_cols)},
        ])

        return {
            "status": "success",
            "result_type": "comparison",
            "data": comp_df,
            "columns": list(comp_df.columns),
            "row_count": len(comp_df),
            "evidence": {
                "comparison_type": "column_schemas" if is_compare_cols else "row_and_column_counts",
                "left_dataset": left_name,
                "right_dataset": right_name,
                "left_rows": len(left_df),
                "right_rows": len(right_df),
                "left_cols": left_cols,
                "right_cols": right_cols,
                "shared_columns": shared_cols,
                "unique_left_columns": sorted(list(left_set - right_set)),
                "unique_right_columns": sorted(list(right_set - left_set)),
                "row_difference": abs(len(left_df) - len(right_df)),
            },
            "warnings": warnings,
        }

    # Auto-detect relationships if not supplied
    if relationships is None:
        try:
            from services.relationship_detector import RelationshipDetector
            relationships = RelationshipDetector.detect_all_relationships({left_name: left_df, right_name: right_df})
        except Exception:
            relationships = []

    valid_rel: Optional[Relationship] = None
    if relationships:
        for r in relationships:
            s_ds = getattr(r, "source_dataset", "")
            t_ds = getattr(r, "target_dataset", "")
            if (s_ds == left_name and t_ds == right_name) or (s_ds == right_name and t_ds == left_name):
                valid_rel = r
                break

    # 2. Unmatched / Difference queries (Anti-Join): "Which records in A not in B?"
    is_diff_query = any(w in q_str for w in [
        "not present in", "not in", "absent in", "no matching", "without any", "have customer_id not present in"
    ])
    if is_diff_query:
        if valid_rel:
            left_key = valid_rel.source_column if valid_rel.source_dataset == left_name else valid_rel.target_column
            right_key = valid_rel.target_column if valid_rel.source_dataset == left_name else valid_rel.source_column
        else:
            common = [c for c in left_df.columns if c in right_df.columns and _is_safe_key_name(c)]
            if common:
                left_key = common[0]
                right_key = common[0]
            else:
                return {
                    "status": "error",
                    "result_type": "error",
                    "data": None,
                    "columns": [],
                    "row_count": 0,
                    "evidence": {},
                    "warnings": [f"Cannot determine a valid comparison key between '{left_name}' and '{right_name}' to find unmatched records."],
                    "errors": [f"Cannot find valid relationship or comparison key connecting '{left_name}' and '{right_name}'."],
                }

        right_keys = set(right_df[right_key].dropna().astype(str).str.strip().unique())
        left_key_series = left_df[left_key].astype(str).str.strip()
        unmatched_mask = ~left_key_series.isin(right_keys)
        unmatched_df = left_df[unmatched_mask]

        return {
            "status": "success",
            "result_type": "table",
            "data": unmatched_df,
            "columns": list(unmatched_df.columns),
            "row_count": len(unmatched_df),
            "evidence": {
                "query_type": "unmatched_records",
                "left_dataset": left_name,
                "right_dataset": right_name,
                "left_key": left_key,
                "right_key": right_key,
                "unmatched_count": len(unmatched_df),
            },
            "warnings": warnings,
        }

    # 3. Validated Relational Join
    if not valid_rel:
        return {
            "status": "error",
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [f"No verified relationship exists connecting '{left_name}' and '{right_name}'. Cross-dataset join refused."],
            "errors": [f"No verified relationship exists connecting '{left_name}' and '{right_name}'. Cross-dataset join refused."],
        }

    # Identify keys based on orientation
    if valid_rel.source_dataset == left_name:
        left_key = valid_rel.source_column
        right_key = valid_rel.target_column
    else:
        left_key = valid_rel.target_column
        right_key = valid_rel.source_column

    # Key safety check
    if not _is_safe_key_name(left_key) or not _is_safe_key_name(right_key):
        return {
            "status": "error",
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [f"Join rejected: Columns '{left_key}' or '{right_key}' appear to be index artifacts."],
            "errors": [f"Join rejected: Columns '{left_key}' or '{right_key}' appear to be index artifacts."],
        }

    # Many-to-Many Guard
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
            "status": "error",
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [msg],
            "errors": [msg],
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
            "status": "error",
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [f"Merge failed: {str(e)}"],
            "errors": [f"Merge failed: {str(e)}"],
        }

    rows_after = len(joined_df)
    growth_ratio = (rows_after / max(rows_before, 1))

    # Row explosion check
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
            "status": "error",
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [msg],
            "errors": [msg],
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

    # 5. If query plan has grouping and/or aggregation, compute on joined table
    if query_plan:
        group_by = query_plan.get("group_by", [])
        column = query_plan.get("column")
        aggregation = query_plan.get("aggregation", "sum")
        limit = query_plan.get("limit", 10)
        sort = query_plan.get("sort", "descending")

        def _find_in_joined(c_name: Optional[str]) -> Optional[str]:
            if not c_name:
                return None
            if c_name in joined_df.columns:
                return c_name
            c_low = c_name.lower().strip()
            for jc in joined_df.columns:
                jc_l = jc.lower().strip()
                if jc_l == c_low or jc_l.startswith(c_low + "_") or jc_l.endswith("_" + c_low):
                    return jc
            return None

        actual_groups = [_find_in_joined(g) for g in group_by if _find_in_joined(g)]
        actual_col = _find_in_joined(column)

        if actual_groups and actual_col:
            from query.aggregation_engine import compute_aggregation
            agg_res = compute_aggregation(
                joined_df,
                column=actual_col,
                aggregation=aggregation,
                group_by=actual_groups,
                sort=sort,
                limit=limit,
            )
            agg_res["status"] = "success"
            agg_res["evidence"] = {**evidence, **agg_res.get("evidence", {})}
            agg_res["warnings"] = warnings + agg_res.get("warnings", [])
            return agg_res
        elif actual_col and not actual_groups and aggregation in ("sum", "mean", "count", "min", "max"):
            from query.aggregation_engine import compute_aggregation
            agg_res = compute_aggregation(
                joined_df,
                column=actual_col,
                aggregation=aggregation,
                sort=sort,
                limit=limit,
            )
            agg_res["status"] = "success"
            agg_res["evidence"] = {**evidence, **agg_res.get("evidence", {})}
            agg_res["warnings"] = warnings + agg_res.get("warnings", [])
            return agg_res

    # Default: return preview of joined DataFrame
    return {
        "status": "success",
        "result_type": "table",
        "data": joined_df if len(joined_df) <= 100 else joined_df.head(100),
        "columns": list(joined_df.columns),
        "row_count": len(joined_df),
        "evidence": evidence,
        "warnings": warnings,
    }
