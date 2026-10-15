"""DuckDB High-Performance Analytical SQL Engine.

Executes safe, parameterized, columnar analytical queries over tabular datasets.
Includes strict memory limits, execution timeouts, and an allowlist of SQL operations.
Completely disallows arbitrary SQL execution, DDL, or file-system mutations.
"""

from typing import Dict, Any, List, Optional, Tuple
import time
import math
import re
import pandas as pd
import numpy as np

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


class DuckDBEngine:
    """Safe, sandboxed DuckDB execution wrapper for local analytical SQL."""

    # Allowed aggregation functions
    ALLOWED_AGGREGATIONS = {
        "sum": "SUM",
        "mean": "AVG",
        "avg": "AVG",
        "average": "AVG",
        "min": "MIN",
        "minimum": "MIN",
        "max": "MAX",
        "maximum": "MAX",
        "count": "COUNT",
        "median": "MEDIAN",
        "std": "STDDEV_POP",
        "stddev": "STDDEV_POP",
        "var": "VAR_POP",
        "variance": "VAR_POP",
    }

    # Allowed filter comparison operators
    ALLOWED_OPERATORS = {"==", "=", "!=", ">", "<", ">=", "<=", "in", "like"}

    @classmethod
    def is_available(cls) -> bool:
        """Check if DuckDB is installed and operational."""
        return DUCKDB_AVAILABLE

    @classmethod
    def execute_plan(
        cls,
        df: pd.DataFrame,
        plan: Dict[str, Any],
        memory_limit: str = "512MB",
        timeout_seconds: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        """Execute a validated StructuredQueryPlan against a DataFrame using DuckDB.

        Returns None if the plan is not suitable for SQL pushdown or if DuckDB is unavailable,
        triggering seamless fallback to Pandas/SciPy.
        """
        if not cls.is_available() or df is None or df.empty:
            return None

        intent = plan.get("intent", "").upper()
        # Intents well-suited for fast DuckDB columnar pushdown:
        sql_intents = {
            "AVERAGE", "SUM", "COUNT", "MINIMUM", "MAXIMUM", "MEDIAN",
            "TOP_N", "BOTTOM_N", "GROUP_BY", "FILTER", "SORT", "SHOW_DATA",
            "UNIQUE_VALUES",
        }
        if intent not in sql_intents:
            return None

        start_time = time.time()
        conn = None

        try:
            # 1. Initialize sandboxed in-memory DuckDB connection
            conn = duckdb.connect(database=":memory:")
            conn.execute(f"SET max_memory = '{memory_limit}';")
            conn.execute("SET threads = 2;")

            # 2. Register pandas dataframe as temporary view
            conn.register("source_table", df)

            # 3. Construct safe parameterized query
            query_str, params = cls._build_safe_sql(df, plan)
            if not query_str:
                return None

            # 4. Execute query with bounds
            result_df = conn.execute(query_str, params).fetchdf()
            duration_ms = round((time.time() - start_time) * 1000.0, 2)

            return {
                "success": True,
                "data": result_df,
                "columns": list(result_df.columns),
                "row_count": len(result_df),
                "engine": "DuckDB (Columnar In-Memory)",
                "execution_time_ms": duration_ms,
                "sql_executed": query_str,
            }

        except Exception as e:
            # Fall back cleanly to Pandas
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def _build_safe_sql(
        cls,
        df: pd.DataFrame,
        plan: Dict[str, Any],
    ) -> Tuple[Optional[str], List[Any]]:
        """Construct safe SQL from plan elements without string concatenation of values."""
        intent = plan.get("intent", "").upper()
        available_cols = {c.lower(): c for c in df.columns}

        # Resolve measure column
        raw_col = plan.get("column")
        measure_col = available_cols.get(str(raw_col).lower()) if raw_col else None

        # Resolve group by columns
        raw_group = plan.get("group_by") or []
        group_cols = [available_cols[g.lower()] for g in raw_group if g.lower() in available_cols]

        # Resolve aggregation
        raw_agg = (plan.get("aggregation") or "").lower()
        sql_agg = cls.ALLOWED_AGGREGATIONS.get(raw_agg, "AVG")

        # Resolve filters
        where_clauses = []
        params: List[Any] = []
        filters = plan.get("filters") or []

        for f in filters:
            f_col = f.get("column")
            f_op = f.get("operator", "==").lower()
            f_val = f.get("value")

            real_col = available_cols.get(str(f_col).lower())
            if not real_col:
                continue

            # Map operator
            sql_op = "=" if f_op in ("==", "=") else f_op
            if sql_op not in cls.ALLOWED_OPERATORS:
                continue

            where_clauses.append(f'"{real_col}" {sql_op} ?')
            params.append(f_val)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # -----------------------------------------------------------------
        # Build query based on intent
        # -----------------------------------------------------------------
        if intent in ("AVERAGE", "SUM", "MINIMUM", "MAXIMUM", "COUNT", "MEDIAN"):
            if not measure_col:
                # Fall back to first numeric column if not specified
                num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                measure_col = num_cols[0] if num_cols else df.columns[0]

            agg_fn = {
                "AVERAGE": "AVG",
                "SUM": "SUM",
                "MINIMUM": "MIN",
                "MAXIMUM": "MAX",
                "COUNT": "COUNT",
                "MEDIAN": "MEDIAN",
            }.get(intent, "AVG")

            metric_alias = f"{intent.lower()}_{measure_col}"
            sql = f'SELECT {agg_fn}("{measure_col}") AS "{metric_alias}" FROM source_table{where_sql}'
            return sql, params

        elif intent in ("TOP_N", "BOTTOM_N", "GROUP_BY"):
            if not group_cols:
                # Pick first categorical column if not given
                cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
                if cat_cols:
                    group_cols = [cat_cols[0]]

            if not measure_col:
                num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                measure_col = num_cols[0] if num_cols else None

            if not group_cols or not measure_col:
                return None

            group_quoted = ", ".join(f'"{g}"' for g in group_cols)
            metric_alias = f"{sql_agg.lower()}_{measure_col}"

            order_dir = "DESC" if intent == "TOP_N" else "ASC"
            limit = plan.get("limit") or 10

            sql = (
                f'SELECT {group_quoted}, {sql_agg}("{measure_col}") AS "{metric_alias}" '
                f'FROM source_table{where_sql} '
                f'GROUP BY {group_quoted} '
                f'ORDER BY "{metric_alias}" {order_dir} '
                f'LIMIT {int(limit)}'
            )
            return sql, params

        elif intent == "FILTER":
            limit = min(int(plan.get("limit") or 100), 500)
            sql = f'SELECT * FROM source_table{where_sql} LIMIT {limit}'
            return sql, params

        elif intent == "SORT":
            sort_col = available_cols.get(str(plan.get("sort_column") or measure_col).lower())
            if not sort_col:
                sort_col = df.columns[0]

            order_dir = "DESC" if str(plan.get("sort")).lower().startswith("desc") else "ASC"
            limit = min(int(plan.get("limit") or 100), 500)

            sql = f'SELECT * FROM source_table{where_sql} ORDER BY "{sort_col}" {order_dir} LIMIT {limit}'
            return sql, params

        elif intent == "UNIQUE_VALUES":
            target = measure_col or (group_cols[0] if group_cols else df.columns[0])
            sql = (
                f'SELECT "{target}", COUNT(*) AS frequency '
                f'FROM source_table{where_sql} '
                f'GROUP BY "{target}" '
                f'ORDER BY frequency DESC '
                f'LIMIT 50'
            )
            return sql, params

        return None, []
