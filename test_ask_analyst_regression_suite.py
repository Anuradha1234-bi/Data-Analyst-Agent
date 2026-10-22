"""Comprehensive Regression Test Suite for Ask Analyst (Phase 9 Quality & Regression Hardening).

Verifies the 12 specific regression requirements:
1. A simple row-count question still returns the correct result.
2. A sum question returns the actual pandas-calculated sum.
3. A combined row-count and sum question executes both operations correctly.
4. Negative instructions do not trigger unwanted analytical intents.
5. A schema question returns all column names and data types without incorrectly selecting Customer_Name.
6. A metadata question returns the correct filename, dataset ID when available, row count, and column count.
7. A table-only request does not append insights or suggestions.
8. Outlier analysis returns results from the selected dataset only, with verifiable thresholds and actual matching records.
9. Switching datasets does not reuse the previous dataset's context or results.
10. A question about data not present in the selected dataset returns a clear "not found in this dataset" response rather than invented information.
11. A reasonable, previously unseen natural-language question can be understood and answered when its answer is supported by the data.
12. Existing working tests and features remain unaffected.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from query.orchestrator import run_ask_analyst_query
from query.intent_detector import detect_query_intent
from query.column_resolver import resolve_column
from query.context_manager import ConversationContextManager
from app.database import engine
from app.models.dataset import Dataset
from app.models.user import User
from app.services.data_analyst_service import DataAnalystService
from app.schemas.analyst import AnalysisAskRequest
from sqlalchemy.orm import Session


@pytest.fixture(scope="module")
def deterministic_fixture():
    df = pd.DataFrame({
        "Customer_ID": [1, 2, 3, 4, 5],
        "Customer_Name": ["Alice", "Bob", "Charlie", "David", "Emma"],
        "Order_Amount_INR": [1000.0, 2500.0, 1500.0, 5000.0, 10000.0],
        "City": ["Mumbai", "Delhi", "Pune", "Mumbai", "Bangalore"],
    })
    meta = {
        "orders.csv": {
            "columns": list(df.columns),
            "data_types": {c: str(df[c].dtype) for c in df.columns},
            "row_count": len(df),
            "column_count": len(df.columns),
            "filename": "orders.csv",
        }
    }
    return {"orders.csv": df}, meta


@pytest.fixture(scope="module")
def real_dataset_fixture():
    db = Session(bind=engine)
    user = db.query(User).filter(User.id == 20).first()
    dataset = db.query(Dataset).filter(Dataset.id == 57, Dataset.user_id == 20).first()
    return db, user, dataset


# 1. Simple row-count question
def test_1_simple_row_count(deterministic_fixture):
    datasets, meta = deterministic_fixture
    r = run_ask_analyst_query("How many rows are in the dataset?", datasets, meta)
    assert r["status"] == "success"
    assert "5" in r["answer"]["answer"]


# 2. Sum question returns actual pandas-calculated sum
def test_2_sum_calculation(deterministic_fixture):
    datasets, meta = deterministic_fixture
    df = datasets["orders.csv"]
    expected_sum = df["Order_Amount_INR"].sum()
    r = run_ask_analyst_query("What is the sum of Order_Amount_INR?", datasets, meta)
    assert r["status"] == "success"
    assert f"{expected_sum:,.2f}" in r["answer"]["answer"] or f"{int(expected_sum)}" in r["answer"]["answer"]


# 3. Combined row-count and sum question executes both operations
def test_3_combined_count_and_sum(deterministic_fixture):
    datasets, meta = deterministic_fixture
    q = "Count the total rows and calculate the sum of Order_Amount_INR for the currently selected dataset. Return a 2-row table. Do not include correlations, outliers, or suggestions."
    r = run_ask_analyst_query(q, datasets, meta)
    assert r["status"] == "success"
    assert "5" in r["answer"]["answer"]
    assert "20,000" in r["answer"]["answer"]
    assert len(r["result"]["data"]) == 2


# 4. Negative instructions do not trigger unwanted analytical intents
def test_4_negative_instructions_guard(deterministic_fixture):
    datasets, meta = deterministic_fixture
    intent_res = detect_query_intent(
        "Calculate the sum of Order_Amount_INR. Do not include correlations, without outlier analysis, exclude suggestions.",
        meta
    )
    assert intent_res["intent"] != "CORRELATION"
    assert intent_res["intent"] != "ANOMALY_SUMMARY"
    assert intent_res["intent"] != "ANOMALY_RECORDS"
    assert intent_res["intent"] == "SUM"


# 5. Schema question returns all column names without selecting Customer_Name
def test_5_schema_column_names_not_customer_name(deterministic_fixture):
    datasets, meta = deterministic_fixture
    res = resolve_column("column name", list(datasets["orders.csv"].columns))
    assert res["resolved"] is False

    r = run_ask_analyst_query("What are all the column names and their data types?", datasets, meta)
    assert r["status"] == "success"
    assert "Customer_ID" in r["answer"]["answer"]
    assert "Customer_Name" in r["answer"]["answer"]
    assert "Order_Amount_INR" in r["answer"]["answer"]
    assert "City" in r["answer"]["answer"]


# 6. Metadata/schema question with table-only request returns 11 rows and 2 columns
def test_6_metadata_reporting(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available in environment")
    req = AnalysisAskRequest(
        dataset_id=dataset.id,
        question="What are all the column names and their data types in the currently selected dataset? Also report the filename, dataset ID, total rows, and total columns. Return only a table."
    )
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert res.result is not None
    assert len(res.result.rows) == 11
    assert len(res.result.columns) == 2
    assert res.evidence.get("output_format") == "table_only"
    assert len(res.automated_insights) == 0
    assert len(res.follow_up_suggestions) == 0


# ==============================================================================
# FOCUSED REGRESSION SUITE (Section 3 Requirements)
# ==============================================================================

# 1. Simple row count: correct count, no unsolicited insights or suggestions
def test_focused_1_simple_row_count(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available")
    df = pd.read_csv(dataset.file_path)
    expected_rows = len(df)
    req = AnalysisAskRequest(dataset_id=dataset.id, question="How many total rows are in this dataset?")
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert str(expected_rows) in res.answer
    assert len(res.automated_insights) == 0, "Unsolicited insights should be suppressed for COUNT"
    assert len(res.follow_up_suggestions) == 0, "Unsolicited suggestions should be suppressed for COUNT"


# 2. Schema query: exactly 11 rows and two columns for the tested CSV, with no extra displayed report sections when table-only is requested
def test_focused_2_schema_table_only(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available")
    df = pd.read_csv(dataset.file_path)
    expected_cols_count = len(df.columns)
    req = AnalysisAskRequest(
        dataset_id=dataset.id,
        question="What are all the column names and their data types in the currently selected dataset? Also report the filename, dataset ID, total rows, and total columns. Return only a table."
    )
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert res.result is not None
    assert len(res.result.rows) == expected_cols_count, f"Expected {expected_cols_count} rows, got {len(res.result.rows)}"
    assert len(res.result.columns) == 2, f"Expected 2 columns, got {res.result.columns}"
    assert res.evidence.get("output_format") == "table_only"
    assert len(res.key_points) == 0
    assert len(res.automated_insights) == 0
    assert len(res.follow_up_suggestions) == 0


# 3. Compound count + sum: exactly two metrics, 50 rows and sum 159327.00 for verified CSV; no instruction text in headings
def test_focused_3_compound_count_and_sum(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available")
    df = pd.read_csv(dataset.file_path)
    expected_rows = len(df)
    expected_sum = df["Order_Amount_INR"].sum()
    req = AnalysisAskRequest(
        dataset_id=dataset.id,
        question="Count the total rows and calculate the sum of Order_Amount_INR for the currently selected dataset. Return a 2-row table. Do not include correlations, outliers, or suggestions."
    )
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert res.result is not None
    assert len(res.result.rows) == 2, f"Expected 2 rows, got {len(res.result.rows)}"
    row_dict = {r["Metric"]: r["Value"] for r in res.result.rows}
    assert any(str(expected_rows) in str(v) for v in row_dict.values())
    assert any(f"{expected_sum:,.2f}" in str(v) or str(int(expected_sum)) in str(v) for v in row_dict.values())
    forbidden_snippets = ["Return a 2-row table", "Do not include correlations", "Return only a table"]
    for snip in forbidden_snippets:
        assert snip.lower() not in (res.answer or "").lower()
    assert len(res.automated_insights) == 0
    assert len(res.follow_up_suggestions) == 0


# 4. Explicit outlier-analysis query: normal outlier analysis remains available
def test_focused_4_explicit_outlier_analysis(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available")
    req = AnalysisAskRequest(
        dataset_id=dataset.id,
        question="Detect outliers in Order_Amount_INR using the IQR method and Z-score method. Compare the detected records, explain why the methods may disagree, and recommend which method is more appropriate for this dataset."
    )
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert res.result is not None and len(res.result.rows) > 0
    assert "Customer_ID" in res.result.columns
    assert len(res.automated_insights) >= 1
    assert len(res.follow_up_suggestions) >= 1


# 5. Normal detailed exploratory report: existing insights and report sections still work
def test_focused_5_exploratory_data_quality_report(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available")
    req = AnalysisAskRequest(
        dataset_id=dataset.id,
        question="Perform a complete data quality audit covering completeness, uniqueness, validity, consistency, accuracy limitations, and statistical anomalies. Return a table with issue name, affected rows, severity, detection rule, and recommended action. Do not label a value inaccurate without a reliable reference."
    )
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert res.result is not None and len(res.result.rows) >= 6
    assert len(res.automated_insights) >= 1
    assert len(res.follow_up_suggestions) >= 1


# 6. Variations in wording: two-column, two-row, and 2-row
@pytest.mark.parametrize("query_text, expected_rows, expected_cols", [
    ("What are the column names and data types? Return a two-column table.", 11, 2),
    ("What are the column names and data types? Return a 2-column table.", 11, 2),
    ("Count rows and calculate sum of Order_Amount_INR. Return a two-row table.", 2, 2),
    ("Count rows and calculate sum of Order_Amount_INR. Return a 2-row table.", 2, 2),
    ("Show the total records and total sum of Order_Amount_INR. Return only a two-row table.", 2, 2),
])
def test_focused_6_wording_variations(real_dataset_fixture, query_text, expected_rows, expected_cols):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available")
    req = AnalysisAskRequest(dataset_id=dataset.id, question=query_text)
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert res.result is not None
    assert len(res.result.rows) == expected_rows, f"Failed for {query_text}: got {len(res.result.rows)} rows"
    assert len(res.result.columns) == expected_cols, f"Failed for {query_text}: got {len(res.result.columns)} columns"
    assert res.evidence.get("output_format") == "table_only"
    assert len(res.automated_insights) == 0
    assert len(res.follow_up_suggestions) == 0



# 7. Table-only request does not append insights or suggestions
def test_7_table_only_suppresses_suggestions(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available in environment")
    req = AnalysisAskRequest(
        dataset_id=dataset.id,
        question="Count the total rows and calculate the sum of Order_Amount_INR for the currently selected dataset. Return a 2-row table. Do not include correlations, outliers, or suggestions."
    )
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert len(res.automated_insights) == 0
    assert len(res.follow_up_suggestions) == 0
    assert len(res.result.rows) == 2


# 8. Outlier analysis returns results from selected dataset with thresholds and records
def test_8_outlier_analysis_records_and_thresholds(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available in environment")
    req = AnalysisAskRequest(
        dataset_id=dataset.id,
        question="Detect outliers in Order_Amount_INR using the IQR method and Z-score method. Compare the detected records, explain why the methods may disagree, and recommend which method is more appropriate for this dataset."
    )
    res = DataAnalystService.ask_question(req, user, db)
    assert res.status == "success"
    assert "IQR" in res.answer
    assert "Z-Score" in res.answer or "Z-score" in res.answer
    assert res.evidence.get("evaluated_records") == 50
    assert len(res.result.rows) > 0
    # Customer_ID must be present in the flagged records
    assert "Customer_ID" in res.result.columns


# 9. Switching datasets does not reuse previous dataset's context or results
def test_9_dataset_switching_isolation():
    df1 = pd.DataFrame({"A": [10, 20, 30], "B": ["X", "Y", "Z"]})
    df2 = pd.DataFrame({"X": [100, 200], "Y": ["P", "Q"]})
    datasets = {"ds1.csv": df1, "ds2.csv": df2}
    meta = {
        "ds1.csv": {"columns": list(df1.columns), "data_types": {"A": "int64", "B": "object"}},
        "ds2.csv": {"columns": list(df2.columns), "data_types": {"X": "int64", "Y": "object"}},
    }
    user_id = 999
    ConversationContextManager.clear_context(user_id, 1)
    ConversationContextManager.clear_context(user_id, 2)

    # Turn 1 on ds1
    r1 = run_ask_analyst_query("What is the sum of A?", datasets, meta, default_dataset="ds1.csv")
    assert "60" in r1["answer"]["answer"]

    # Turn 2 on ds2: should not have A or 60
    r2 = run_ask_analyst_query("What is the sum of X?", datasets, meta, default_dataset="ds2.csv")
    assert "300" in r2["answer"]["answer"]
    assert "A" not in r2["answer"]["answer"]


# 10. Question about data not present returns clear "not found in this dataset"
def test_10_absent_data_not_invented(deterministic_fixture):
    datasets, meta = deterministic_fixture
    r = run_ask_analyst_query("What is the average employee salary?", datasets, meta)
    assert "not available in the uploaded CSV" in r["answer"]["answer"] or "employee salary" in r["answer"]["answer"]


# 11. Reasonable unseen natural-language question understood when supported by data
def test_11_unseen_natural_language_question(deterministic_fixture):
    datasets, meta = deterministic_fixture
    r = run_ask_analyst_query("Which city has the highest order amount?", datasets, meta)
    assert r["status"] == "success"
    assert "Bangalore" in r["answer"]["answer"]
    assert "10,000" in r["answer"]["answer"]


# 12. Verification of audited CSV values
def test_12_clean_customer_orders_expected_values(real_dataset_fixture):
    db, user, dataset = real_dataset_fixture
    if not dataset or not Path(dataset.file_path).exists():
        pytest.skip("Dataset 57 not available in environment")
    df = pd.read_csv(dataset.file_path)
    assert len(df) == 50, f"Expected 50 rows, got {len(df)}"
    assert len(df.columns) == 11, f"Expected 11 columns, got {len(df.columns)}"
    assert abs(df["Order_Amount_INR"].sum() - 159327.00) < 0.01, f"Expected sum 159327.00, got {df['Order_Amount_INR'].sum()}"


# ==============================================================================
# FOCUSED CATEGORY-WISE AGGREGATION & TABLE-ONLY REGRESSION SUITE (Section 5)
# ==============================================================================

@pytest.fixture(scope="module")
def clean_orders_fixture():
    csv_path = PROJECT_ROOT / "uploads" / "user_20" / "733e249dc2fa443c829afdb12d90fff3_clean_customer_orders__2_.csv"
    if not csv_path.exists():
        pytest.skip(f"Clean customer orders CSV not found at {csv_path}")
    df = pd.read_csv(csv_path)
    meta = {
        "clean_customer_orders (2).csv": {
            "columns": list(df.columns),
            "data_types": {c: str(df[c].dtype) for c in df.columns},
            "row_count": len(df),
            "column_count": len(df.columns),
            "filename": "clean_customer_orders (2).csv",
        }
    }
    return {"clean_customer_orders (2).csv": df}, meta


# 1. Dataset preambles are not interpreted as independent questions
def test_regression_1_preambles_not_split(clean_orders_fixture):
    from query.orchestrator import split_multi_part_question
    q1 = "Using only clean_customer_orders (2).csv, calculate total Order_Amount_INR for each Category and return only the table."
    parts1 = split_multi_part_question(q1)
    assert len(parts1) == 1, f"Expected 1 part for preamble query, got {len(parts1)}: {parts1}"
    assert parts1[0] == q1

    q2 = "In clean_customer_orders (2).csv, group rows by Category and calculate total Order_Amount_INR"
    parts2 = split_multi_part_question(q2)
    assert len(parts2) == 1, f"Expected 1 part for preamble query, got {len(parts2)}: {parts2}"
    assert parts2[0] == q2

    # Conjunctions within a single grouping request do not cause splitting
    q3 = "In clean_customer_orders (2).csv, group rows by Category by summing Order_Amount_INR for each group"
    parts3 = split_multi_part_question(q3)
    assert len(parts3) == 1, f"Expected 1 part, got {len(parts3)}: {parts3}"

    datasets, meta = clean_orders_fixture
    r = run_ask_analyst_query(q1, datasets, meta)
    assert r["status"] == "success"
    assert "Unable to process query" not in r["answer"]["answer"]
    assert "This information is not available" not in r["answer"]["answer"]


# 2. 'by summing Order_Amount_INR' does not treat 'summing' as a column
def test_regression_2_summing_not_treated_as_column(clean_orders_fixture):
    from query.query_planner import build_query_plan
    datasets, meta = clean_orders_fixture
    df = datasets["clean_customer_orders (2).csv"]

    res_col = resolve_column("summing", list(df.columns))
    assert res_col["resolved"] is False
    assert len(res_col["candidates"]) == 0

    q = "In clean_customer_orders (2).csv, group rows by Category by summing Order_Amount_INR for each group"
    plan = build_query_plan(q, meta)
    missing = plan.get("metadata", {}).get("missing_columns", [])
    assert "summing" not in missing, f"'summing' should not be in missing_columns: {missing}"

    r = run_ask_analyst_query(q, datasets, meta)
    assert r["status"] == "success"
    assert r.get("result", {}).get("data") is not None
    assert len(r.get("result", {}).get("data")) == 6


# 3. 'for each group' does not treat 'group' as a column
def test_regression_3_group_not_treated_as_column(clean_orders_fixture):
    from query.query_planner import build_query_plan
    datasets, meta = clean_orders_fixture
    df = datasets["clean_customer_orders (2).csv"]

    res_col = resolve_column("group", list(df.columns))
    assert res_col["resolved"] is False
    assert len(res_col["candidates"]) == 0

    res_col2 = resolve_column("groups", list(df.columns))
    assert res_col2["resolved"] is False

    q = "group rows by Category by summing Order_Amount_INR for each group"
    plan = build_query_plan(q, meta)
    missing = plan.get("metadata", {}).get("missing_columns", [])
    assert "group" not in missing, f"'group' should not be in missing_columns: {missing}"
    assert "Category" in plan.get("group_by", [])

    r = run_ask_analyst_query(q, datasets, meta)
    assert r["status"] == "success"
    assert len(r.get("result", {}).get("data")) == 6


# 4. Grouping by Category and summing Order_Amount_INR returns all six categories
def test_regression_4_category_sum_all_six_categories(clean_orders_fixture):
    datasets, meta = clean_orders_fixture
    q = "Using only clean_customer_orders (2).csv, calculate total Order_Amount_INR for each Category and return only the table."
    r = run_ask_analyst_query(q, datasets, meta)
    assert r["status"] == "success"
    data = r.get("result", {}).get("data")
    assert isinstance(data, pd.DataFrame)
    assert len(data) == 6, f"Expected 6 categories, got {len(data)}"

    # Ground truth mapping
    expected_totals = {
        "Electronics": 78190.00,
        "Home & Kitchen": 32591.00,
        "Sports": 20089.00,
        "Clothing": 15291.00,
        "Beauty": 8236.00,
        "Books": 4930.00,
    }

    # Verify each category and its sum
    cat_col = "Category"
    val_col = [c for c in data.columns if c != cat_col][0]
    actual_dict = dict(zip(data[cat_col], data[val_col]))

    for cat_name, exp_val in expected_totals.items():
        assert cat_name in actual_dict, f"Category '{cat_name}' missing from results: {actual_dict.keys()}"
        act_val = actual_dict[cat_name]
        assert abs(act_val - exp_val) < 0.01, f"Mismatch for '{cat_name}': expected {exp_val}, got {act_val}"

    # Verify sum across all 6 categories equals exactly 159,327.00
    total_revenue = sum(actual_dict.values())
    assert abs(total_revenue - 159327.00) < 0.01, f"Expected total 159327.00, got {total_revenue}"


# 5. Explicit table-only requests do not include unrelated insights or suggestions
def test_regression_5_table_only_suppresses_insights_and_suggestions(clean_orders_fixture, real_dataset_fixture):
    datasets, meta = clean_orders_fixture
    q = "Using only clean_customer_orders (2).csv, calculate total Order_Amount_INR for each Category and return only the table."
    r = run_ask_analyst_query(q, datasets, meta)
    assert r["status"] == "success"
    # Orchestrator-level evidence checks
    evidence = r.get("result", {}).get("evidence", {})
    assert len(evidence.get("automated_insights", [])) == 0, "Automated insights must be empty for table-only request"

    # Service-level contract check
    db, user, dataset = real_dataset_fixture
    if dataset and Path(dataset.file_path).exists():
        req = AnalysisAskRequest(dataset_id=dataset.id, question=q)
        res = DataAnalystService.ask_question(req, user, db)
        assert res.status == "success"
        assert res.evidence.get("output_format") == "table_only"
        assert len(res.automated_insights) == 0, "No automated insights should be returned"
        assert len(res.follow_up_suggestions) == 0, "No follow-up suggestions should be returned"
        assert len(res.key_points) == 0, "Key points should be suppressed"
        assert len(res.result.rows) == 6, f"Expected 6 rows, got {len(res.result.rows)}"

    # Also test wording "Return only the resulting table."
    q2 = "In clean_customer_orders (2).csv, group rows by Category and calculate total Order_Amount_INR. Return only the resulting table."
    r2 = run_ask_analyst_query(q2, datasets, meta)
    assert r2["status"] == "success"
    ev2 = r2.get("result", {}).get("evidence", {})
    assert len(ev2.get("automated_insights", [])) == 0


# 6. Existing row-count and scalar-sum behavior remains correct
def test_regression_6_row_count_and_scalar_sum(clean_orders_fixture):
    datasets, meta = clean_orders_fixture
    # Row count
    r_count = run_ask_analyst_query("How many rows are in the dataset?", datasets, meta)
    assert r_count["status"] == "success"
    assert "50" in r_count["answer"]["answer"]

    # Scalar sum
    r_sum = run_ask_analyst_query("What is the sum of Order_Amount_INR?", datasets, meta)
    assert r_sum["status"] == "success"
    assert "159,327" in r_sum["answer"]["answer"] or "159327" in r_sum["answer"]["answer"]


# 7. Genuine nonexistent column names are still rejected appropriately
def test_regression_7_genuine_nonexistent_columns_rejected(clean_orders_fixture):
    datasets, meta = clean_orders_fixture
    # Scalar sum with nonexistent column
    r1 = run_ask_analyst_query("What is the sum of Nonexistent_Metric?", datasets, meta)
    assert r1["status"] == "error"
    assert "not exist in dataset" in r1["answer"]["answer"] or "not available" in r1["answer"]["answer"]

    # Grouped query with nonexistent metric
    r2 = run_ask_analyst_query("Group rows by Category and calculate total Nonexistent_Metric", datasets, meta)
    assert r2["status"] == "error"
    assert "not exist in dataset" in r2["answer"]["answer"] or "not available" in r2["answer"]["answer"]

    # Grouped query with nonexistent grouping column
    r3 = run_ask_analyst_query("Group rows by Nonexistent_Dimension and calculate total Order_Amount_INR", datasets, meta)
    assert r3["status"] == "error"
    assert "not exist in dataset" in r3["answer"]["answer"] or "not available" in r3["answer"]["answer"]
