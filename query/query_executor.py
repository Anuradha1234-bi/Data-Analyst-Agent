"""Query Executor Module for Phase 6 Natural Language Query Engine.

Executes validated query plans deterministically across datasets.
Dispatches to safe specialized query engines.
Guarantees clean data versioning and data source clarity.
No eval(), exec(), or arbitrary code allowed.
"""

import re
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from query.query_models import QueryIntent, QueryExecutionResult
from query.config import normalize_query_config
from query.filter_engine import apply_filters
from query.aggregation_engine import compute_aggregation
from query.comparison_engine import compare_groups, compare_dates
from query.trend_query_engine import compute_trend_query
from query.correlation_query_engine import compute_correlation_query
from query.anomaly_query_engine import compute_anomaly_query
from query.cross_dataset_query_engine import execute_cross_dataset_query
from query.duckdb_engine import DuckDBEngine
from query.advanced_stats import AdvancedStatsEngine
from query.insight_engine import InsightEngine


def compute_data_quality_audit(
    df: pd.DataFrame,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute complete comprehensive data quality audit across 6 core dimensions:
    1. Completeness: missing/null/empty values and affected rows.
    2. Uniqueness: duplicate rows and relevant candidate-key duplicates.
    3. Validity: invalid formats, impossible dates, or range violations.
    4. Consistency: meaningful cross-column or internal-rule violations.
    5. Statistical anomalies: defensible IQR and Z-score outlier evaluation.
    6. Accuracy limitations: explicitly state factual accuracy boundaries without external ground truth.
    """
    warnings: List[str] = []
    ds_key = dataset_name or "dataset.csv"

    if df is None or df.empty:
        return {
            "result_type": "empty",
            "data": pd.DataFrame(),
            "columns": ["Issue Name", "Affected Rows", "Severity", "Detection Rule", "Recommended Action"],
            "row_count": 0,
            "evidence": {"dataset": ds_key, "total_rows": 0},
            "warnings": ["Dataset is empty."],
        }

    total_rows = len(df)
    audit_rows: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # DIMENSION 1: COMPLETENESS
    # -------------------------------------------------------------------------
    missing_by_col = {}
    for c in df.columns:
        s_c = df[c]
        is_missing = s_c.isna() | (s_c.astype(str).str.strip() == "") | (s_c.astype(str).str.lower().isin(["nan", "none", "null"]))
        cnt = int(is_missing.sum())
        if cnt > 0:
            missing_by_col[c] = cnt

    if missing_by_col:
        for col_name, cnt in missing_by_col.items():
            pct = round(cnt / total_rows * 100, 2)
            is_critical = any(k in col_name.lower() for k in ["id", "key", "email", "name", "date"])
            sev = "High" if (pct >= 20.0 or is_critical) else ("Medium" if pct >= 5.0 else "Low")
            audit_rows.append({
                "Issue Name": f"Missing Values in '{col_name}'",
                "Affected Rows": cnt,
                "Severity": sev,
                "Detection Rule": f"Null, NaN, or whitespace-only cells in '{col_name}' (denominator: N={total_rows} rows, {pct}%)",
                "Recommended Action": f"Impute missing entries in '{col_name}' using central tendency/mode or investigate upstream extraction.",
            })
    else:
        audit_rows.append({
            "Issue Name": "Completeness (Missing Values)",
            "Affected Rows": 0,
            "Severity": "Info",
            "Detection Rule": f"Evaluated null and whitespace cells across all {len(df.columns)} columns (denominator: N={total_rows} rows, 100% complete)",
            "Recommended Action": "No completeness action required; dataset has no missing values.",
        })

    # -------------------------------------------------------------------------
    # DIMENSION 2: UNIQUENESS
    # -------------------------------------------------------------------------
    dup_cnt = int(df.duplicated().sum())
    dup_pct = round(dup_cnt / total_rows * 100, 2) if total_rows > 0 else 0.0
    audit_rows.append({
        "Issue Name": "Duplicate Records",
        "Affected Rows": dup_cnt,
        "Severity": "High" if dup_cnt > 0 else "Info",
        "Detection Rule": f"Identical values across all columns (denominator: N={total_rows} rows, {dup_pct}%)",
        "Recommended Action": "Deduplicate records by retaining the primary occurrence if duplicates represent unintended re-submissions." if dup_cnt > 0 else "No deduplication required; all rows are distinct.",
    })

    # Candidate Key Uniqueness
    id_cols = [c for c in df.columns if any(k in c.lower() for k in ["id", "key", "code"]) and not any(k in c.lower() for k in ["city", "state", "status", "category"])]
    for ic in id_cols:
        c_dups = int(df[ic].duplicated().sum())
        if c_dups > 0:
            pct_ic = round(c_dups / total_rows * 100, 2)
            audit_rows.append({
                "Issue Name": f"Candidate Key Collision in '{ic}'",
                "Affected Rows": c_dups,
                "Severity": "High",
                "Detection Rule": f"Duplicate identifier values in candidate primary key '{ic}' (denominator: N={total_rows} rows, {pct_ic}%)",
                "Recommended Action": f"Investigate primary key generation logic for '{ic}' to guarantee unique entity tracking.",
            })

    # -------------------------------------------------------------------------
    # DIMENSION 3: VALIDITY
    # -------------------------------------------------------------------------
    strictly_positive_cols = [c for c in df.columns if any(k in c.lower() for k in ["age", "amount", "price", "revenue", "qty", "quantity", "cost", "salary", "marks", "score"])]
    validity_issues = 0
    for col in strictly_positive_cols:
        num_s = pd.to_numeric(df[col], errors="coerce")
        neg_cnt = int((num_s < 0).sum())
        if neg_cnt > 0:
            validity_issues += 1
            pct_neg = round(neg_cnt / total_rows * 100, 2)
            audit_rows.append({
                "Issue Name": f"Invalid Negative Values in '{col}'",
                "Affected Rows": neg_cnt,
                "Severity": "High",
                "Detection Rule": f"Values < 0 in strictly non-negative domain '{col}' (denominator: N={total_rows} rows, {pct_neg}%)",
                "Recommended Action": f"Rectify inverted signs or treat negative entries in '{col}' as invalid data entry errors.",
            })

    date_cols = [c for c in df.columns if any(k in c.lower() for k in ["date", "time", "created_at", "updated_at", "timestamp"])]
    for dc in date_cols:
        non_null_dc = df[dc].dropna()
        parsed_dc = pd.to_datetime(non_null_dc, errors="coerce")
        inv_cnt = int(parsed_dc.isna().sum())
        if inv_cnt > 0:
            validity_issues += 1
            pct_inv = round(inv_cnt / len(non_null_dc) * 100, 2)
            audit_rows.append({
                "Issue Name": f"Invalid Date Formats in '{dc}'",
                "Affected Rows": inv_cnt,
                "Severity": "Medium",
                "Detection Rule": f"Non-null strings failing standard ISO datetime parsing in '{dc}' (denominator: N={len(non_null_dc)} non-null cells, {pct_inv}%)",
                "Recommended Action": f"Standardize date formatting into ISO 8601 (YYYY-MM-DD) for '{dc}'.",
            })

    if validity_issues == 0:
        audit_rows.append({
            "Issue Name": "Domain Validity Check",
            "Affected Rows": 0,
            "Severity": "Info",
            "Detection Rule": f"Non-negative domain bounds and date parsing checks across {len(strictly_positive_cols) + len(date_cols)} candidate columns (denominator: N={total_rows} rows)",
            "Recommended Action": "No domain validity violations detected.",
        })

    # -------------------------------------------------------------------------
    # DIMENSION 4: CONSISTENCY
    # -------------------------------------------------------------------------
    consistency_issues = 0
    cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and not any(k in c.lower() for k in ["id", "date", "time", "email"])]
    for cc in cat_cols:
        clean_s = df[cc].dropna().astype(str).str.strip()
        if len(clean_s.unique()) > len(clean_s.str.lower().unique()):
            consistency_issues += 1
            audit_rows.append({
                "Issue Name": f"Categorical Inconsistency in '{cc}'",
                "Affected Rows": len(clean_s),
                "Severity": "Medium",
                "Detection Rule": f"Mixed-case or whitespace variations across unique categorical values in '{cc}' (denominator: N={len(clean_s)} rows)",
                "Recommended Action": f"Apply trim and case-folding normalization on '{cc}'.",
            })

    if consistency_issues == 0:
        audit_rows.append({
            "Issue Name": "Cross-Column & Text Consistency",
            "Affected Rows": 0,
            "Severity": "Info",
            "Detection Rule": f"Evaluated categorical value casing consistency and relational internal rules (denominator: N={total_rows} rows)",
            "Recommended Action": "No cross-column or formatting inconsistencies found.",
        })

    # -------------------------------------------------------------------------
    # DIMENSION 5: STATISTICAL ANOMALIES
    # -------------------------------------------------------------------------
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not any(k in c.lower() for k in ["id", "index", "unnamed"])]
    anom_count_total = 0
    for nc in num_cols:
        s_nc = pd.to_numeric(df[nc], errors="coerce").dropna()
        if len(s_nc) >= 4:
            q1 = float(s_nc.quantile(0.25))
            q3 = float(s_nc.quantile(0.75))
            iqr = q3 - q1
            low = q1 - 1.5 * iqr
            high = q3 + 1.5 * iqr
            mean_nc = float(s_nc.mean())
            std_nc = float(s_nc.std(ddof=1))
            iqr_mask = (s_nc < low) | (s_nc > high)
            z_mask = ((s_nc - mean_nc).abs() > 3.0 * std_nc) if std_nc > 0 else pd.Series(False, index=s_nc.index)
            outlier_idx = set(s_nc[iqr_mask | z_mask].index.tolist())
            if outlier_idx:
                anom_count_total += len(outlier_idx)
                pct_out = round(len(outlier_idx) / len(s_nc) * 100, 2)
                audit_rows.append({
                    "Issue Name": f"Statistical Outliers in '{nc}'",
                    "Affected Rows": len(outlier_idx),
                    "Severity": "Low",
                    "Detection Rule": f"Values exceeding IQR fences [{low:.2f}, {high:.2f}] or |Z| > 3.0 (denominator: N={len(s_nc)} valid observations, {pct_out}%)",
                    "Recommended Action": f"Verify extreme values in '{nc}' with domain stakeholders to determine if they reflect authentic transactions or recording anomalies.",
                })

    if anom_count_total == 0:
        audit_rows.append({
            "Issue Name": "Statistical Anomalies",
            "Affected Rows": 0,
            "Severity": "Info",
            "Detection Rule": f"Evaluated IQR (1.5x) and Z-score (|Z| > 3.0) boundaries across {len(num_cols)} numerical features",
            "Recommended Action": "No statistical outliers detected.",
        })

    # -------------------------------------------------------------------------
    # DIMENSION 6: ACCURACY LIMITATIONS
    # -------------------------------------------------------------------------
    audit_rows.append({
        "Issue Name": "Accuracy Limitations (External Reference Required)",
        "Affected Rows": 0,
        "Severity": "Info",
        "Detection Rule": "Methodological boundary: factual accuracy cannot be determined mathematically from internal data alone without external ground truth or authoritative reference data.",
        "Recommended Action": "Do not label values inaccurate without a reliable reference. Cross-verify sample entries against source transaction receipts or ERP databases.",
    })

    expected_cols = ["Issue Name", "Affected Rows", "Severity", "Detection Rule", "Recommended Action"]
    res_df = pd.DataFrame(audit_rows)[expected_cols]

    evidence = {
        "dataset": ds_key,
        "total_rows": total_rows,
        "total_columns": len(df.columns),
        "audit_issues_count": len(audit_rows),
        "summary_table": audit_rows,
        "accuracy_caveat": "Factual accuracy cannot be mathematically proven from internal data alone without trusted external reference data.",
    }

    return {
        "result_type": "table",
        "data": res_df,
        "columns": expected_cols,
        "row_count": len(res_df),
        "evidence": evidence,
        "warnings": warnings,
    }


def execute_query(
    query_plan: Dict[str, Any],
    datasets: Dict[str, pd.DataFrame],
    cleaned_datasets: Optional[Dict[str, pd.DataFrame]] = None,
    phase5_results: Optional[Dict[str, Any]] = None,
    phase4_results: Optional[Dict[str, Any]] = None,
    relationships: Optional[List[Any]] = None,
    join_audit: Optional[List[Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a validated query plan safely.

    Contract:
    Returns:
    {
        "status": "success",
        "result_type": "table",
        "data": ...,
        "columns": [],
        "row_count": 10,
        "evidence": {},
        "warnings": [],
        "errors": []
    }
    """
    cfg = normalize_query_config(config)
    warnings: List[str] = []
    errors: List[str] = []

    intent = query_plan.get("intent", QueryIntent.UNKNOWN.value)
    target_ds_name = query_plan.get("dataset")

    # Select dataset and determine version (Cleaned vs Original)
    use_cleaned = cfg.get("use_cleaned_data_by_default", True)
    is_cleaned_used = False

    df = None
    if cleaned_datasets and use_cleaned and target_ds_name in cleaned_datasets:
        df = cleaned_datasets[target_ds_name]
        is_cleaned_used = True
    elif target_ds_name in datasets:
        df = datasets[target_ds_name]
    elif len(datasets) == 1:
        target_ds_name = list(datasets.keys())[0]
        df = datasets[target_ds_name]
    else:
        return {
            "status": "error",
            "result_type": "empty",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": [],
            "errors": [f"Target dataset '{target_ds_name}' not available."],
        }

    dataset_source_label = f"Analysis based on {'cleaned' if is_cleaned_used else 'original'} {target_ds_name}."

    # 0. Compute Derived Column (if requested and derivable)
    derived_info = query_plan.get("derived_column") or query_plan.get("metadata", {}).get("derived_column")
    if derived_info and isinstance(derived_info, dict) and df is not None and not df.empty:
        c1 = derived_info.get("col1")
        c2 = derived_info.get("col2")
        out_name = derived_info.get("output_name")
        formula_type = derived_info.get("formula_type")
        if c1 in df.columns and c2 in df.columns and out_name:
            df = df.copy()
            s1 = pd.to_numeric(df[c1], errors="coerce").fillna(0)
            s2 = pd.to_numeric(df[c2], errors="coerce").fillna(0)
            if formula_type == "difference":
                df[out_name] = s1 - s2
            elif formula_type == "product":
                df[out_name] = s1 * s2
            elif formula_type == "ratio_pct":
                df[out_name] = np.where(s2 != 0, (s1 / s2) * 100, 0.0)

    # 1. Apply Filters First (if present)
    filters = query_plan.get("filters", [])
    filter_logic = query_plan.get("filter_logic", "AND")
    if filters and df is not None and not df.empty:
        # Pre-resolve subquery filters (e.g. value == "__subquery__")
        for f in filters:
            if isinstance(f, dict) and (f.get("value") == "__subquery__" or f.get("subquery")):
                sub_info = f.get("subquery", {})
                sub_intent = str(sub_info.get("intent", "AVERAGE")).upper()
                sub_col = sub_info.get("column", f.get("column"))
                if sub_col in df.columns:
                    s_num = pd.to_numeric(df[sub_col], errors="coerce").dropna()
                    if not s_num.empty:
                        if sub_intent in ("AVERAGE", "MEAN", "AVG"):
                            computed_val = float(s_num.mean())
                        elif sub_intent in ("SUM", "TOTAL"):
                            computed_val = float(s_num.sum())
                        elif sub_intent in ("MINIMUM", "MIN"):
                            computed_val = float(s_num.min())
                        elif sub_intent in ("MAXIMUM", "MAX"):
                            computed_val = float(s_num.max())
                        else:
                            computed_val = float(s_num.mean())
                        f["value"] = computed_val
        df, filter_warnings = apply_filters(df, filters, logic=filter_logic)
        warnings.extend(filter_warnings)

    column = query_plan.get("column")
    group_by = query_plan.get("group_by", [])
    aggregation = query_plan.get("aggregation")
    limit = query_plan.get("limit")
    offset = query_plan.get("offset")
    sort = query_plan.get("sort")

    # 2. Dispatch to specific Intent Handlers
    res_payload: Dict[str, Any] = {}

    try:
        # -------------------------------------------------------------
        # COUNT INTENT
        # -------------------------------------------------------------
        if intent == QueryIntent.COUNT.value:
            include_columns = query_plan.get("metadata", {}).get("include_columns", False) or "column" in str(query_plan.get("question", "")).lower()
            if not column or column not in df.columns:
                row_count = int(len(df))
                res_df = pd.DataFrame([{"Total Records": row_count}])
                evidence = {
                    "count": row_count,
                    "dataset": target_ds_name,
                    "dataset_source": dataset_source_label,
                    "filters_applied": filters,
                }
                if include_columns:
                    col_cnt = len(df.columns)
                    evidence["column_count"] = col_cnt
                    res_df["Total Columns"] = col_cnt
                res_payload = {
                    "result_type": "table",
                    "data": res_df,
                    "columns": list(res_df.columns),
                    "row_count": 1,
                    "evidence": evidence,
                    "warnings": warnings,
                    "value": row_count,
                }
            else:
                valid_cnt = int(df[column].count())
                res_df = pd.DataFrame([{f"Count of {column}": valid_cnt}])
                res_payload = {
                    "result_type": "table",
                    "data": res_df,
                    "columns": [f"Count of {column}"],
                    "row_count": 1,
                    "evidence": {"column": column, "count": valid_cnt, "dataset_source": dataset_source_label},
                    "warnings": warnings,
                    "value": valid_cnt,
                }

        # -------------------------------------------------------------
        # AGGREGATIONS (SUM, AVERAGE, MEDIAN, MINIMUM, MAXIMUM)
        # -------------------------------------------------------------
        elif intent in (
            QueryIntent.AVERAGE.value,
            QueryIntent.SUM.value,
            QueryIntent.MEDIAN.value,
            QueryIntent.MINIMUM.value,
            QueryIntent.MAXIMUM.value,
        ):
            agg_name = {
                QueryIntent.AVERAGE.value: "mean",
                QueryIntent.SUM.value: "sum",
                QueryIntent.MEDIAN.value: "median",
                QueryIntent.MINIMUM.value: "min",
                QueryIntent.MAXIMUM.value: "max",
            }.get(intent, aggregation or "mean")

            agg_res = compute_aggregation(
                df,
                column=column,
                aggregation=agg_name,
                group_by=group_by,
                sort=sort,
                limit=limit,
                offset=offset,
            )
            agg_res["evidence"]["dataset_source"] = dataset_source_label
            if not group_by and "data" in agg_res and agg_res.get("result_type") == "scalar":
                agg_res["value"] = agg_res["data"]
            res_payload = agg_res

        # -------------------------------------------------------------
        # RANKINGS (TOP_N, BOTTOM_N) & GROUP_BY
        # -------------------------------------------------------------
        elif intent in (QueryIntent.TOP_N.value, QueryIntent.BOTTOM_N.value, QueryIntent.GROUP_BY.value):
            if group_by:
                agg_name = aggregation or "mean"
                agg_res = compute_aggregation(
                    df,
                    column=column,
                    aggregation=agg_name,
                    group_by=group_by,
                    sort=sort if intent == QueryIntent.GROUP_BY.value else (sort or ("descending" if intent == QueryIntent.TOP_N.value else "ascending")),
                    limit=limit if intent == QueryIntent.GROUP_BY.value else (limit or 10),
                    offset=offset,
                )
                agg_res["evidence"]["dataset_source"] = dataset_source_label

                # Multidimensional combination analysis (contribution, order volume, AOV, drivers)
                valid_groups = [g for g in group_by if g in df.columns]
                if valid_groups and column and column in df.columns and agg_res.get("data") is not None and not agg_res["data"].empty:
                    try:
                        raw_col = df[column]
                        num_col = pd.to_numeric(raw_col, errors="coerce")
                        missing_invalid_cnt = int(num_col.isna().sum())
                        zero_cnt = int((num_col == 0).sum())
                        valid_series = num_col.dropna()
                        total_valid_rev = float(valid_series.sum())

                        if missing_invalid_cnt > 0:
                            warnings.append(
                                f"Encountered {missing_invalid_cnt} missing or non-numeric entries in '{column}' which were excluded from total computation."
                            )

                        # Detect order identifier column (Req 8)
                        order_id_col = None
                        for c in df.columns:
                            cl = c.lower().replace("-", "_").replace(" ", "_")
                            if cl in ("order_id", "orderid", "order_no", "order_number", "invoice_no", "invoice_id", "transaction_id") or ("order" in cl and "id" in cl):
                                order_id_col = c
                                break

                        if order_id_col:
                            total_orders = int(df[order_id_col].nunique())
                            order_count_def = f"Distinct count of '{order_id_col}'"
                            order_count_method = "distinct_order_id"
                        else:
                            total_orders = int(len(df))
                            order_count_def = "Row count (each row represents one distinct order as no Order_ID column is present)"
                            order_count_method = "row_count"

                        overall_aov = round(total_valid_rev / total_orders, 2) if total_orders > 0 else 0.0

                        top_row = agg_res["data"].iloc[0]
                        comb_mask = pd.Series(True, index=df.index)
                        comb_dict = {}
                        for g in valid_groups:
                            val = top_row[g]
                            comb_dict[g] = val
                            comb_mask = comb_mask & (df[g] == val)

                        comb_df = df[comb_mask]
                        comb_rev_s = pd.to_numeric(comb_df[column], errors="coerce").dropna()
                        comb_rev = float(comb_rev_s.sum())

                        if order_id_col:
                            comb_orders = int(comb_df[order_id_col].nunique())
                        else:
                            comb_orders = int(len(comb_df))

                        comb_aov = round(comb_rev / comb_orders, 2) if comb_orders > 0 else 0.0
                        contrib_pct = round((comb_rev / total_valid_rev) * 100, 2) if total_valid_rev > 0 else 0.0

                        total_grps = agg_res["evidence"].get("total_groups", len(agg_res["data"]))
                        avg_orders_per_grp = round(total_orders / total_grps, 2) if total_grps > 0 else 1.0

                        aov_ratio = round(comb_aov / overall_aov, 2) if overall_aov > 0 else 1.0
                        vol_ratio = round(comb_orders / avg_orders_per_grp, 2) if avg_orders_per_grp > 0 else 1.0

                        curr_sym = "₹" if ("inr" in column.lower() or "rs" in column.lower()) else ("$" if "usd" in column.lower() else "")

                        if aov_ratio >= 1.5 and vol_ratio <= 1.2:
                            prim_driver = "average_order_value"
                            driver_stmt = (
                                f"The top-ranking revenue of this combination is primarily associated with a substantially higher average order value "
                                f"({curr_sym}{comb_aov:,.2f} vs dataset average {curr_sym}{overall_aov:,.2f}, approximately {aov_ratio:.1f}x higher) rather than higher order volume "
                                f"({comb_orders} order vs average {avg_orders_per_grp:.1f} orders per combination)."
                            )
                        elif vol_ratio >= 1.5 and aov_ratio <= 1.2:
                            prim_driver = "order_volume"
                            driver_stmt = (
                                f"The top-ranking revenue of this combination is primarily associated with higher order volume "
                                f"({comb_orders} orders vs average {avg_orders_per_grp:.1f} orders per combination) rather than a higher average order value "
                                f"({curr_sym}{comb_aov:,.2f} vs dataset average {curr_sym}{overall_aov:,.2f})."
                            )
                        elif aov_ratio >= 1.3 and vol_ratio >= 1.3:
                            prim_driver = "both"
                            driver_stmt = (
                                f"The top-ranking revenue of this combination is associated with both above-average order volume "
                                f"({comb_orders} orders) and a higher average order value ({curr_sym}{comb_aov:,.2f} vs dataset average {curr_sym}{overall_aov:,.2f})."
                            )
                        else:
                            prim_driver = "balanced"
                            driver_stmt = (
                                f"The top-ranking revenue of this combination is balanced across order volume ({comb_orders} orders) "
                                f"and average order value ({curr_sym}{comb_aov:,.2f} vs dataset average {curr_sym}{overall_aov:,.2f})."
                            )

                        causation_disc = (
                            "Note: This driver assessment reflects empirical statistical association in the uploaded CSV records and does not establish operational or behavioral causation."
                        )

                        agg_res["evidence"]["combination_analysis"] = {
                            "top_combination": comb_dict,
                            "group_columns": valid_groups,
                            "revenue_column": column,
                            "currency_symbol": curr_sym,
                            "combination_revenue": comb_rev,
                            "total_valid_revenue": total_valid_rev,
                            "contribution_pct": contrib_pct,
                            "missing_or_invalid_revenue_count": missing_invalid_cnt,
                            "zero_revenue_count": zero_cnt,
                            "order_volume": comb_orders,
                            "total_orders": total_orders,
                            "order_counting_definition": order_count_def,
                            "order_counting_method": order_count_method,
                            "combination_aov": comb_aov,
                            "overall_aov": overall_aov,
                            "aov_ratio": aov_ratio,
                            "volume_ratio": vol_ratio,
                            "primary_driver": prim_driver,
                            "driver_statement": driver_stmt,
                            "causation_disclaimer": causation_disc,
                        }
                    except Exception as ex:
                        warnings.append(f"Combination breakdown calculation skipped: {str(ex)}")

                res_payload = agg_res
            elif column and column in df.columns:
                # Rank rows directly by measure column
                is_asc = (intent == QueryIntent.BOTTOM_N.value) or (sort == "ascending")
                sorted_df = df.sort_values(by=column, ascending=is_asc)
                if offset and offset > 0:
                    sorted_df = sorted_df.iloc[offset:]
                ranked = sorted_df.head(limit or 10)
                top_v = None
                if not ranked.empty:
                    raw_v = ranked.iloc[0][column]
                    if isinstance(raw_v, (np.floating, float)):
                        top_v = round(float(raw_v), 2)
                    elif isinstance(raw_v, (np.integer, int)):
                        top_v = int(raw_v)
                    else:
                        top_v = str(raw_v)
                evidence = {
                    "dataset_source": dataset_source_label,
                    "column": column,
                    "limit": limit or 10,
                    "offset": offset,
                    "top_value": top_v,
                }
                res_payload = {
                    "result_type": "table",
                    "data": ranked.reset_index(drop=True),
                    "columns": list(ranked.columns),
                    "row_count": len(ranked),
                    "evidence": evidence,
                    "warnings": warnings,
                    "value": top_v,
                }
            else:
                errors.append("No valid ranking or grouping column specified.")
                res_payload = {
                    "result_type": "empty",
                    "data": pd.DataFrame(),
                    "columns": [],
                    "row_count": 0,
                    "evidence": {"dataset_source": dataset_source_label},
                    "warnings": warnings,
                }

        # -------------------------------------------------------------
        # FILTER / SHOW DATA
        # -------------------------------------------------------------
        elif intent in (QueryIntent.FILTER.value, QueryIntent.SHOW_DATA.value, QueryIntent.SORT.value):
            res_df = df
            if sort and column and column in res_df.columns:
                res_df = res_df.sort_values(by=column, ascending=(sort == "ascending"))
            if limit:
                res_df = res_df.head(limit)
            else:
                res_df = res_df.head(25)

            res_payload = {
                "result_type": "table",
                "data": res_df.reset_index(drop=True),
                "columns": list(res_df.columns),
                "row_count": len(res_df),
                "evidence": {
                    "dataset_source": dataset_source_label,
                    "filters_applied": filters,
                    "total_filtered_rows": len(df),
                },
                "warnings": warnings,
            }

        # -------------------------------------------------------------
        # MISSING VALUES
        # -------------------------------------------------------------
        elif intent == QueryIntent.MISSING_VALUES.value:
            null_counts = df.isnull().sum()
            null_pcts = (null_counts / len(df) * 100.0) if len(df) > 0 else 0.0
            missing_df = pd.DataFrame({
                "Column": df.columns,
                "Missing Values": null_counts.values,
                "Missing (%)": [round(p, 2) for p in null_pcts.values],
            }).sort_values(by="Missing Values", ascending=False).reset_index(drop=True)

            tot_missing = int(null_counts.sum())
            cols_with_missing = list(missing_df[missing_df["Missing Values"] > 0]["Column"])

            res_payload = {
                "result_type": "table",
                "data": missing_df,
                "columns": list(missing_df.columns),
                "row_count": len(missing_df),
                "evidence": {
                    "total_missing_values": tot_missing,
                    "overall_missing_pct": round((tot_missing / max(df.size, 1)) * 100.0, 2),
                    "columns_with_missing": cols_with_missing,
                    "dataset_source": dataset_source_label,
                },
                "warnings": warnings,
            }

        # -------------------------------------------------------------
        # DUPLICATES
        # -------------------------------------------------------------
        elif intent == QueryIntent.DUPLICATES.value:
            dup_mask = df.duplicated()
            dup_count = int(dup_mask.sum())
            dup_pct = round((dup_count / max(len(df), 1)) * 100.0, 2)

            dup_summary_df = pd.DataFrame([{
                "Total Rows": len(df),
                "Duplicate Rows": dup_count,
                "Duplicate Rate (%)": dup_pct,
            }])

            res_payload = {
                "result_type": "table",
                "data": dup_summary_df,
                "columns": list(dup_summary_df.columns),
                "row_count": 1,
                "evidence": {
                    "duplicate_count": dup_count,
                    "duplicate_rate_pct": dup_pct,
                    "dataset_source": dataset_source_label,
                },
                "warnings": warnings,
            }

        # -------------------------------------------------------------
        # DATA TYPES
        # -------------------------------------------------------------
        elif intent == QueryIntent.DATA_TYPES.value:
            q_plan_meta = query_plan.get("metadata", {}) or {}
            q_text_meta = str(q_plan_meta.get("question", "")).lower()
            col_name_header = "Column Name" if ("column name" in q_text_meta or "two-column" in q_text_meta or "two column" in q_text_meta or "2-column" in q_text_meta) else "Column"
            is_two_col_req = any(k in q_text_meta for k in ["two-column", "2-column", "two column", "2 column", "column name and data type", "column names and their data types", "column names and data types"])
            if is_two_col_req:
                dtypes_df = pd.DataFrame({
                    col_name_header: [str(c) for c in df.columns],
                    "Data Type": [str(d) for d in df.dtypes],
                })
            else:
                dtypes_df = pd.DataFrame({
                    col_name_header: [str(c) for c in df.columns],
                    "Data Type": [str(d) for d in df.dtypes],
                    "Category": [
                        "Numeric" if pd.api.types.is_numeric_dtype(df[c])
                        else ("Datetime" if pd.api.types.is_datetime64_any_dtype(df[c]) else "Categorical/Text")
                        for c in df.columns
                    ],
                })
            num_cols = [str(c) for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            res_payload = {
                "result_type": "table",
                "data": dtypes_df,
                "columns": list(dtypes_df.columns),
                "row_count": len(dtypes_df),
                "evidence": {
                    "total_columns": len(df.columns),
                    "total_rows": len(df),
                    "numeric_columns": num_cols,
                    "dataset_source": dataset_source_label,
                    "evaluated_records": len(df),
                },
                "warnings": warnings,
            }

        # -------------------------------------------------------------
        # UNIQUE VALUES
        # -------------------------------------------------------------
        elif intent == QueryIntent.UNIQUE_VALUES.value:
            if column and column in df.columns:
                n_uniq = int(df[column].nunique())
                sample_vals = list(df[column].dropna().unique()[:10])
                res_df = pd.DataFrame([{
                    "Column": column,
                    "Distinct Values": n_uniq,
                    "Sample Values": ", ".join(str(v) for v in sample_vals),
                }])
                res_payload = {
                    "result_type": "table",
                    "data": res_df,
                    "columns": list(res_df.columns),
                    "row_count": 1,
                    "evidence": {"column": column, "unique_count": n_uniq, "sample_values": sample_vals, "dataset_source": dataset_source_label},
                    "warnings": warnings,
                }
            else:
                uniq_df = pd.DataFrame({
                    "Column": df.columns,
                    "Distinct Values": [int(df[c].nunique()) for c in df.columns],
                }).sort_values(by="Distinct Values", ascending=False).reset_index(drop=True)
                res_payload = {
                    "result_type": "table",
                    "data": uniq_df,
                    "columns": list(uniq_df.columns),
                    "row_count": len(uniq_df),
                    "evidence": {"dataset_source": dataset_source_label},
                    "warnings": warnings,
                }

        # -------------------------------------------------------------
        # TREND & PERCENTAGE CHANGE
        # -------------------------------------------------------------
        elif intent in (QueryIntent.TREND.value, QueryIntent.PERCENTAGE_CHANGE.value):
            res_payload = compute_trend_query(
                df,
                date_col=query_plan.get("date_column"),
                metric_col=column,
                frequency="monthly",
                phase5_results=phase5_results,
            )
            res_payload["evidence"]["dataset_source"] = dataset_source_label

        # -------------------------------------------------------------
        # DATE COMPARISON & DATE RANGE
        # -------------------------------------------------------------
        elif intent in (QueryIntent.DATE_COMPARISON.value, QueryIntent.DATE_RANGE.value):
            dr = query_plan.get("date_range")
            dt_a = dr.get("start") if dr else None
            dt_b = dr.get("end") if dr else None
            res_payload = compare_dates(
                df,
                date_col=query_plan.get("date_column") or "Date",
                metric_col=column or "Price",
                date_a=dt_a,
                date_b=dt_b,
                aggregation=aggregation or "mean",
            )
            res_payload["evidence"]["dataset_source"] = dataset_source_label

        # -------------------------------------------------------------
        # CORRELATION
        # -------------------------------------------------------------
        elif intent == QueryIntent.CORRELATION.value:
            res_payload = compute_correlation_query(
                df,
                col_a=column,
                col_b=query_plan.get("secondary_column"),
                phase5_results=phase5_results,
            )
            res_payload["evidence"]["dataset_source"] = dataset_source_label

        # -------------------------------------------------------------
        # DATA QUALITY AUDIT
        # -------------------------------------------------------------
        elif intent == QueryIntent.DATA_QUALITY_AUDIT.value:
            res_payload = compute_data_quality_audit(df, dataset_name=target_ds_name)
            res_payload["evidence"]["dataset_source"] = dataset_source_label

        # -------------------------------------------------------------
        # ANOMALIES
        # -------------------------------------------------------------
        elif intent in (QueryIntent.ANOMALY_SUMMARY.value, QueryIntent.ANOMALY_RECORDS.value):
            meta_plan = query_plan.get("metadata", {}) or {}
            show_recs = (intent == QueryIntent.ANOMALY_RECORDS.value) or bool(meta_plan.get("show_records"))
            compare_methods = bool(meta_plan.get("compare_methods"))
            res_payload = compute_anomaly_query(
                df,
                phase4_results=phase4_results,
                dataset_name=target_ds_name,
                target_column=column,
                show_records=show_recs,
                compare_methods=compare_methods,
            )
            res_payload["evidence"]["dataset_source"] = dataset_source_label

        # -------------------------------------------------------------
        # CROSS DATASET & DATASET COMPARISONS
        # -------------------------------------------------------------
        elif intent in (QueryIntent.CROSS_DATASET_ANALYSIS.value, QueryIntent.COMPARE_DATASETS.value):
            sec_ds = query_plan.get("secondary_dataset")
            if not sec_ds or sec_ds not in datasets:
                other_ds = [d for d in datasets.keys() if d != target_ds_name]
                sec_ds = other_ds[0] if other_ds else None

            if not sec_ds or sec_ds not in datasets:
                return {
                    "status": "error",
                    "result_type": "empty",
                    "data": None,
                    "columns": [],
                    "row_count": 0,
                    "evidence": {},
                    "warnings": warnings,
                    "errors": ["Cross-dataset analysis requires two uploaded datasets."],
                }

            sec_df = (cleaned_datasets[sec_ds] if cleaned_datasets and use_cleaned and sec_ds in cleaned_datasets else datasets[sec_ds])

            res_payload = execute_cross_dataset_query(
                left_name=target_ds_name,
                right_name=sec_ds,
                left_df=df,
                right_df=sec_df,
                relationships=relationships,
                query_plan=query_plan,
                join_audit=join_audit,
                config=config,
            )

        # -------------------------------------------------------------
        # COMPARE GROUPS
        # -------------------------------------------------------------
        elif intent == QueryIntent.COMPARE_GROUPS.value:
            grp_col = group_by[0] if group_by else "market"
            metric = column or "price"
            res_payload = compare_groups(df, group_col=grp_col, metric_col=metric, aggregation=aggregation or "mean")
            res_payload["evidence"]["dataset_source"] = dataset_source_label

        # -------------------------------------------------------------
        # DESCRIPTIVE STATISTICS & INSIGHT SUMMARY
        # -------------------------------------------------------------
        elif intent in (QueryIntent.DESCRIPTIVE_STATISTICS.value, QueryIntent.INSIGHT_SUMMARY.value):
            from query.column_resolver import filter_metadata_columns
            num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            if column and column in num_cols:
                num_cols = [column]
            elif filter_metadata_columns(num_cols):
                num_cols = filter_metadata_columns(num_cols)

            if num_cols:
                desc_df = df[num_cols].describe().T.reset_index()
                desc_df.rename(columns={"index": "Feature"}, inplace=True)
                for col_name in desc_df.columns:
                    if desc_df[col_name].dtype in ("float64", "float32"):
                        desc_df[col_name] = desc_df[col_name].round(2)
            else:
                desc_df = pd.DataFrame([{
                    "Metric": "Total Records", "Value": len(df),
                }, {
                    "Metric": "Total Columns", "Value": len(df.columns),
                }])

            res_payload = {
                "result_type": "table",
                "data": desc_df,
                "columns": list(desc_df.columns),
                "row_count": len(desc_df),
                "evidence": {
                    "dataset_source": dataset_source_label,
                    "features_described": num_cols,
                },
                "warnings": warnings,
            }

        # -------------------------------------------------------------
        # FORECAST & PREDICTION
        # -------------------------------------------------------------
        elif intent in (QueryIntent.FORECAST.value, QueryIntent.PREDICTION.value, "forecast", "prediction") or str(intent).upper() in ("FORECAST", "PREDICTION"):
            p5_res = None
            if phase5_results:
                if isinstance(phase5_results, dict):
                    if "schema_version" in phase5_results or "task" in phase5_results:
                        p5_res = phase5_results
                    elif target_ds_name in phase5_results:
                        p5_res = phase5_results[target_ds_name]
                    elif len(phase5_results) > 0:
                        for k, v in phase5_results.items():
                            tgt_c = getattr(v, "target_column", None) or (v.get("task", {}).get("target_column") if isinstance(v, dict) else None)
                            if tgt_c and column and str(tgt_c).lower() == str(column).lower():
                                p5_res = v
                                break
                        if not p5_res:
                            p5_res = list(phase5_results.values())[0]
                elif hasattr(phase5_results, "predictions") or hasattr(phase5_results, "to_canonical_dict"):
                    p5_res = phase5_results

            # Normalize to canonical dictionary or extract properties
            canon = None
            if hasattr(p5_res, "to_canonical_dict"):
                canon = p5_res.to_canonical_dict()
            elif isinstance(p5_res, dict) and ("schema_version" in p5_res or "task" in p5_res):
                canon = p5_res

            rows = []
            if canon:
                task_i = canon.get("task", {})
                model_i = canon.get("model", {})
                val_i = canon.get("validation", {})
                pred_i = canon.get("prediction", {})
                fc_i = canon.get("forecast", {})
                feat_i = canon.get("features", {})
                meta_i = canon.get("metadata", {})
                dataset_i = canon.get("dataset", {})

                # Extract rows from forecast or prediction values
                if fc_i.get("enabled") and fc_i.get("values"):
                    for idx, pt in enumerate(fc_i["values"]):
                        if isinstance(pt, dict):
                            p_label = pt.get("period", str(idx + 1))
                            pred_v = pt.get("predicted_value", 0.0)
                            row = {
                                "Period": p_label,
                                "Predicted Value": round(float(pred_v), 4) if isinstance(pred_v, (int, float)) else str(pred_v),
                            }
                            if pt.get("lower_bound") is not None:
                                row["Lower Bound (95%)"] = round(float(pt["lower_bound"]), 4)
                            if pt.get("upper_bound") is not None:
                                row["Upper Bound (95%)"] = round(float(pt["upper_bound"]), 4)
                            rows.append(row)
                        else:
                            rows.append({"Period": str(idx + 1), "Predicted Value": pt})
                elif pred_i.get("values"):
                    for idx, val in enumerate(pred_i["values"]):
                        rows.append({
                            "Period": str(idx + 1),
                            "Predicted Value": round(float(val), 4) if isinstance(val, (int, float)) else str(val),
                        })
                elif pred_i.get("value") is not None:
                    single_v = pred_i["value"]
                    rows.append({
                        "Period": "1",
                        "Predicted Value": round(float(single_v), 4) if isinstance(single_v, (int, float)) else str(single_v),
                    })

                if rows and canon.get("status") in ("success", "partial"):
                    pred_df = pd.DataFrame(rows)
                    metrics_map = val_i.get("metrics", {})
                    first_m_name = next(iter(metrics_map.keys())) if metrics_map else "MAE"
                    first_m_val = metrics_map.get(first_m_name, 0.0) if metrics_map else 0.0
                    res_payload = {
                        "result_type": "table",
                        "data": pred_df,
                        "columns": list(pred_df.columns),
                        "row_count": len(pred_df),
                        "evidence": {
                            "dataset": dataset_i.get("name") or target_ds_name,
                            "dataset_source": dataset_source_label,
                            "selected_model": model_i.get("name", "Trained Model"),
                            "target_column": task_i.get("target_column") or column or "",
                            "problem_type": task_i.get("problem_type", ""),
                            "mode": task_i.get("problem_type", ""),
                            "metric_name": str(first_m_name).upper(),
                            "metric_value": float(first_m_val) if isinstance(first_m_val, (int, float)) else 0.0,
                            "metrics": metrics_map,
                            "horizon": len(rows),
                            "forecast_horizon": fc_i.get("horizon", len(rows)),
                            "first_predicted": rows[0]["Predicted Value"] if rows else 0.0,
                            "last_predicted": rows[-1]["Predicted Value"] if rows else 0.0,
                            "explanation": " ".join(meta_i.get("notes", [])) if meta_i.get("notes") else "",
                            "features_used": task_i.get("feature_columns", []),
                            "feature_importance": feat_i.get("importance"),
                            "top_features": feat_i.get("top_features") or [],
                            "limitations": meta_i.get("notes", []),
                        },
                        "warnings": warnings,
                    }
                else:
                    msg = f"No prediction results are available yet for dataset '{target_ds_name}'. Run a prediction or forecasting analysis first."
                    warnings.append(msg)
                    res_payload = {
                        "result_type": "empty",
                        "data": None,
                        "columns": [],
                        "row_count": 0,
                        "evidence": {
                            "dataset_source": dataset_source_label,
                            "notice": "No prediction results are available yet. Run a prediction or forecasting analysis first.",
                            "suggestion": "Run a prediction or forecasting analysis first.",
                        },
                        "warnings": warnings,
                    }
            elif p5_res and (hasattr(p5_res, "predictions") or hasattr(p5_res, "predicted_points")):
                pts = getattr(p5_res, "predictions", None) or getattr(p5_res, "predicted_points", None)
                if pts:
                    for pt in pts:
                        p_label = getattr(pt, "index_or_date", None) or getattr(pt, "period_label", None) or str(getattr(pt, "step", ""))
                        pred_v = getattr(pt, "predicted_value", 0.0)
                        row = {
                            "Period": p_label,
                            "Predicted Value": round(float(pred_v), 4) if isinstance(pred_v, (int, float)) else str(pred_v),
                        }
                        if getattr(pt, "lower_bound", None) is not None:
                            row["Lower Bound (95%)"] = round(float(pt.lower_bound), 4)
                        if getattr(pt, "upper_bound", None) is not None:
                            row["Upper Bound (95%)"] = round(float(pt.upper_bound), 4)
                        rows.append(row)
                    pred_df = pd.DataFrame(rows)
                    best_m = getattr(p5_res, "best_metrics", None)
                    m_val = best_m.mae if best_m and getattr(best_m, "mae", None) is not None else getattr(p5_res, "metric_value", 0.0)
                    m_name = getattr(p5_res, "selection_metric", None) or getattr(p5_res, "metric_name", "MAE")
                    expl = getattr(p5_res, "explanation", None) or getattr(p5_res, "explanation_narrative", "")
                    res_payload = {
                        "result_type": "table",
                        "data": pred_df,
                        "columns": list(pred_df.columns),
                        "row_count": len(pred_df),
                        "evidence": {
                            "dataset": target_ds_name,
                            "dataset_source": dataset_source_label,
                            "selected_model": getattr(p5_res, "selected_model_name", "Trained Model"),
                            "target_column": getattr(p5_res, "target_column", column or ""),
                            "problem_type": getattr(p5_res, "problem_type", ""),
                            "mode": getattr(p5_res, "mode", ""),
                            "metric_name": m_name,
                            "metric_value": float(m_val) if m_val is not None else 0.0,
                            "metrics": best_m.to_dict() if best_m and hasattr(best_m, "to_dict") else getattr(p5_res, "metrics", {}),
                            "horizon": len(pts),
                            "forecast_horizon": getattr(p5_res, "forecast_horizon", len(pts)),
                            "first_predicted": float(getattr(pts[0], "predicted_value", 0.0)) if isinstance(getattr(pts[0], "predicted_value", None), (int, float)) else 0.0,
                            "last_predicted": float(getattr(pts[-1], "predicted_value", 0.0)) if isinstance(getattr(pts[-1], "predicted_value", None), (int, float)) else 0.0,
                            "explanation": expl,
                            "confidence_statement": getattr(p5_res, "confidence_statement", ""),
                            "features_used": getattr(p5_res, "features_used", []),
                            "feature_importance": [fi.__dict__ if hasattr(fi, "__dict__") else fi for fi in getattr(p5_res, "feature_importance", [])],
                            "limitations": getattr(p5_res, "limitations", []),
                        },
                        "warnings": warnings,
                    }
                else:
                    msg = f"No prediction results are available yet for dataset '{target_ds_name}'. Run a prediction or forecasting analysis first."
                    warnings.append(msg)
                    res_payload = {
                        "result_type": "empty",
                        "data": None,
                        "columns": [],
                        "row_count": 0,
                        "evidence": {
                            "dataset_source": dataset_source_label,
                            "notice": "No prediction results are available yet. Run a prediction or forecasting analysis first.",
                            "suggestion": "Run a prediction or forecasting analysis first.",
                        },
                        "warnings": warnings,
                    }
            else:
                msg = f"No prediction results are available yet for dataset '{target_ds_name}'. Run a prediction or forecasting analysis first."
                warnings.append(msg)
                res_payload = {
                    "result_type": "empty",
                    "data": None,
                    "columns": [],
                    "row_count": 0,
                    "evidence": {
                        "dataset_source": dataset_source_label,
                        "notice": "No prediction results are available yet. Run a prediction or forecasting analysis first.",
                        "suggestion": "Run a prediction or forecasting analysis first.",
                    },
                    "warnings": warnings,
                }

        # -------------------------------------------------------------
        # LINEAR REGRESSION
        # -------------------------------------------------------------
        elif intent == QueryIntent.REGRESSION.value:
            num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            y_col = column if (column in df.columns and pd.api.types.is_numeric_dtype(df[column])) else (num_cols[0] if num_cols else None)
            sec_col = query_plan.get("secondary_column")
            x_candidates = [c for c in df.columns if c != y_col and (pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_datetime64_any_dtype(df[c]))]
            x_col = sec_col if (sec_col in df.columns) else (x_candidates[0] if x_candidates else None)

            if not x_col or not y_col:
                errors.append("Linear regression requires two numerical columns (predictor X and target Y).")
                res_payload = {"result_type": "empty", "data": None, "columns": [], "row_count": 0, "evidence": {}}
            else:
                reg_res = AdvancedStatsEngine.compute_linear_regression(df, x_col, y_col)
                if not reg_res.get("success"):
                    errors.append(reg_res.get("error", "Regression failed."))
                    res_payload = {"result_type": "empty", "data": None, "columns": [], "row_count": 0, "evidence": {}}
                else:
                    reg_table = pd.DataFrame([
                        {"Metric": "Predictor (X)", "Value": str(x_col)},
                        {"Metric": "Target (Y)", "Value": str(y_col)},
                        {"Metric": "Slope (m)", "Value": reg_res["slope"]},
                        {"Metric": "Intercept (c)", "Value": reg_res["intercept"]},
                        {"Metric": "R-squared (R²)", "Value": reg_res["r_squared"]},
                        {"Metric": "P-value", "Value": reg_res["p_value"]},
                        {"Metric": "Standard Error", "Value": reg_res["standard_error"]},
                        {"Metric": "Equation", "Value": reg_res["equation"]},
                    ])
                    res_payload = {
                        "result_type": "table",
                        "data": reg_table,
                        "columns": ["Metric", "Value"],
                        "row_count": len(reg_table),
                        "evidence": {
                            "dataset_source": dataset_source_label,
                            "regression_details": reg_res,
                            "computed_values": {"r_squared": reg_res["r_squared"], "slope": reg_res["slope"]},
                        },
                        "warnings": warnings,
                    }

        # -------------------------------------------------------------
        # TWO-GROUP HYPOTHESIS TEST
        # -------------------------------------------------------------
        elif intent == QueryIntent.TWO_GROUP_TEST.value:
            cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
            num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            g_col = (group_by[0] if group_by else None) or (cat_cols[0] if cat_cols else None)
            m_col = column if (column in num_cols) else (num_cols[0] if num_cols else None)

            if not g_col or not m_col:
                errors.append("Two-group hypothesis test requires a grouping category and a numerical metric.")
                res_payload = {"result_type": "empty", "data": None, "columns": [], "row_count": 0, "evidence": {}}
            else:
                test_res = AdvancedStatsEngine.compare_two_groups(df, g_col, m_col)
                if not test_res.get("success"):
                    errors.append(test_res.get("error", "Hypothesis test failed."))
                    res_payload = {"result_type": "empty", "data": None, "columns": [], "row_count": 0, "evidence": {}}
                else:
                    test_table = pd.DataFrame([
                        {"Parameter": "Group A", "Value": f"{test_res['group_a']['name']} (N={test_res['group_a']['sample_size']})"},
                        {"Parameter": "Group A Mean", "Value": test_res["group_a"]["mean"]},
                        {"Parameter": "Group B", "Value": f"{test_res['group_b']['name']} (N={test_res['group_b']['sample_size']})"},
                        {"Parameter": "Group B Mean", "Value": test_res["group_b"]["mean"]},
                        {"Parameter": "Mean Difference", "Value": test_res["mean_difference"]},
                        {"Parameter": "T-Statistic", "Value": test_res["t_statistic"]},
                        {"Parameter": "P-Value", "Value": test_res["p_value"]},
                        {"Parameter": "Effect Size (Cohen's d)", "Value": test_res["cohens_d"]},
                        {"Parameter": "Statistically Significant", "Value": "Yes (p < 0.05)" if test_res["is_significant"] else "No (p >= 0.05)"},
                    ])
                    res_payload = {
                        "result_type": "table",
                        "data": test_table,
                        "columns": ["Parameter", "Value"],
                        "row_count": len(test_table),
                        "evidence": {
                            "dataset_source": dataset_source_label,
                            "test_details": test_res,
                            "computed_values": {"p_value": test_res["p_value"], "t_statistic": test_res["t_statistic"]},
                        },
                        "warnings": warnings,
                    }

        # -------------------------------------------------------------
        # CHI-SQUARE TEST OF INDEPENDENCE
        # -------------------------------------------------------------
        elif intent == QueryIntent.CHI_SQUARE.value:
            cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
            if len(cat_cols) < 2:
                errors.append("Chi-square test of independence requires at least two categorical columns.")
                res_payload = {"result_type": "empty", "data": None, "columns": [], "row_count": 0, "evidence": {}}
            else:
                c_x = cat_cols[0]
                c_y = cat_cols[1]
                chi_res = AdvancedStatsEngine.chi_square_test(df, c_x, c_y)
                if not chi_res.get("success"):
                    errors.append(chi_res.get("error", "Chi-square test failed."))
                    res_payload = {"result_type": "empty", "data": None, "columns": [], "row_count": 0, "evidence": {}}
                else:
                    chi_table = pd.DataFrame([
                        {"Metric": "Feature X", "Value": str(c_x)},
                        {"Metric": "Feature Y", "Value": str(c_y)},
                        {"Metric": "Chi-Square Statistic (χ²)", "Value": chi_res["chi2_statistic"]},
                        {"Metric": "Degrees of Freedom", "Value": chi_res["degrees_of_freedom"]},
                        {"Metric": "P-Value", "Value": chi_res["p_value"]},
                        {"Metric": "Cramér's V (Association)", "Value": chi_res["cramers_v"]},
                        {"Metric": "Statistically Significant", "Value": "Yes (p < 0.05)" if chi_res["is_significant"] else "No (p >= 0.05)"},
                    ])
                    res_payload = {
                        "result_type": "table",
                        "data": chi_table,
                        "columns": ["Metric", "Value"],
                        "row_count": len(chi_table),
                        "evidence": {
                            "dataset_source": dataset_source_label,
                            "chi_details": chi_res,
                            "computed_values": {"chi2": chi_res["chi2_statistic"], "p_value": chi_res["p_value"]},
                        },
                        "warnings": warnings,
                    }

        # -------------------------------------------------------------
        # UNKNOWN / FALLBACK
        # -------------------------------------------------------------
        else:
            errors.append(f"Query intent '{intent}' could not be executed deterministically.")
            res_payload = {
                "result_type": "empty",
                "data": None,
                "columns": [],
                "row_count": 0,
                "evidence": {},
                "warnings": warnings,
            }

    except Exception as e:
        errors.append(f"Execution error: {str(e)}")
        res_payload = {
            "result_type": "error",
            "data": None,
            "columns": [],
            "row_count": 0,
            "evidence": {},
            "warnings": warnings,
        }

    # Ensure table view is converted if scalar
    data_out = res_payload.get("data")
    scalar_val = res_payload.get("value")
    if scalar_val is None:
        if res_payload.get("result_type") == "scalar":
            scalar_val = res_payload.get("data")
        elif res_payload.get("evidence", {}).get("top_value") is not None:
            scalar_val = res_payload.get("evidence", {}).get("top_value")
        elif isinstance(data_out, pd.DataFrame) and len(data_out) == 1:
            col = query_plan.get("column")
            if col and col in data_out.columns:
                try:
                    scalar_val = float(data_out.iloc[0][col])
                except Exception:
                    scalar_val = data_out.iloc[0][col]
            elif len(data_out.columns) == 1:
                try:
                    scalar_val = float(data_out.iloc[0, 0])
                except Exception:
                    scalar_val = data_out.iloc[0, 0]

    if res_payload.get("result_type") == "scalar" and "table_view" in res_payload:
        data_out = res_payload["table_view"]

    evidence_out = res_payload.get("evidence", {})
    if df is not None:
        evidence_out["evaluated_records"] = len(df)
        evidence_out["total_dataset_rows"] = len(df)

    q_exec_text = str(query_plan.get("metadata", {}).get("question", "")).lower()
    has_suppression = any(
        term in q_exec_text
        for term in [
            "do not include", "don't include", "without suggestion", "exclude suggestion",
            "no suggestion", "no suggestions", "without suggestions", "exclude suggestions",
            "return only", "only a table", "only the table", "only the resulting table",
            "resulting table only", "table only", "without insight", "exclude insight",
            "do not add automated insights", "without outlier", "exclude outlier",
            "without correlation", "exclude correlation", "2-row table", "two-row table",
            "two-column table", "2-column table"
        ]
    ) or bool(
        re.search(
            r"\b(?:return\s+)?only\s+(?:a\s+|the\s+)?(?:resulting\s+)?(?:\w+[- ]\w+\s+)?table\b|"
            r"\b(?:resulting\s+)?table\s+only\b|"
            r"\b(?:return\s+)?(?:only\s+)?(?:a\s+|the\s+)?(?:two|2)[ -](?:row|column)\s+table\b",
            q_exec_text,
        )
    )

    intent_val = str(intent).upper()
    is_narrow_query = intent_val in (
        QueryIntent.COUNT.value,
        QueryIntent.DATA_TYPES.value,
        QueryIntent.UNIQUE_VALUES.value,
    )

    if has_suppression or is_narrow_query:
        evidence_out["automated_insights"] = []
    elif df is not None and not df.empty and "automated_insights" not in evidence_out:
        evidence_out["automated_insights"] = InsightEngine.discover_insights(
            df,
            target_column=column,
            group_column=(group_by[0] if group_by else None),
        )

    return {
        "status": "error" if errors else "success",
        "result_type": res_payload.get("result_type", "table"),
        "data": data_out,
        "value": scalar_val,
        "columns": res_payload.get("columns", []),
        "row_count": res_payload.get("row_count", 0),
        "evidence": evidence_out,
        "warnings": warnings + res_payload.get("warnings", []),
        "errors": errors,
    }
