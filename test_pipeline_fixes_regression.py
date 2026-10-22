"""Regression tests for Ask Data Analyst pipeline fixes.

Covers:
1. Intent detection: column-count vs row-count, column name listing, dynamic SUM, intent priority.
2. Orchestrator: preamble preservation, no splitting at ', show'.
3. Query planner: prepositional filters, implicit OR conditions, nonexistent filter value preservation, measure col disambiguation.
4. Dataset 57 Q7 exact ground-truth verification (3 rows, ₹19,096 total).
5. All 46 audit questions across 4 datasets.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from query.intent_detector import detect_query_intent
from query.query_models import QueryIntent
from query.orchestrator import split_multi_part_question
from query.query_planner import build_query_plan, _extract_filters_from_question
from sqlalchemy.orm import Session
from app.database import engine
from app.models.dataset import Dataset
from app.models.user import User
from app.services.data_analyst_service import DataAnalystService
from app.schemas.analyst import AnalysisAskRequest


# -------------------------------------------------------------------------
# Unit Tests for Root Causes 1 to 4
# -------------------------------------------------------------------------

def test_intent_column_count_vs_row_count():
    """Verify column-count questions route to DATA_TYPES, not record COUNT."""
    res_col = detect_query_intent("How many columns are in clean_customer_orders (2).csv?", metadata={})
    assert res_col["intent"] == QueryIntent.DATA_TYPES.value, f"Expected DATA_TYPES, got {res_col['intent']}"

    res_row = detect_query_intent("How many rows are in clean_customer_orders (2).csv?", metadata={})
    assert res_row["intent"] == QueryIntent.COUNT.value, f"Expected COUNT, got {res_row['intent']}"


def test_intent_list_column_names():
    """Verify 'list all column names' routes to DATA_TYPES / schema, not SHOW_DATA."""
    res = detect_query_intent("List all column names in clean_customer_orders (2).csv.", metadata={})
    assert res["intent"] == QueryIntent.DATA_TYPES.value, f"Expected DATA_TYPES, got {res['intent']}"


def test_intent_dynamic_sum_from_schema():
    """Verify dynamic column name SUM detection when schema contains numeric column."""
    cols = ["Customer_ID", "Order_Amount_INR", "Category", "Quantity"]
    meta = {"orders.csv": {"columns": cols}}
    res = detect_query_intent("What is the total Order_Amount_INR for Electronics orders?", metadata=meta)
    assert res["intent"] == QueryIntent.SUM.value, f"Expected SUM, got {res['intent']}"


def test_intent_priority_compare_over_sum():
    """Verify 'Compare total records...' routes to COMPARE_DATASETS rather than SUM."""
    res = detect_query_intent("Compare total records in orders.csv and customers.csv", metadata={})
    assert res["intent"] == QueryIntent.COMPARE_DATASETS.value, f"Expected COMPARE_DATASETS, got {res['intent']}"


def test_orchestrator_no_split_on_preamble_show():
    """Verify questions with conditional preambles are not split at ', show'."""
    q = "For orders where Category is Electronics and Quantity is greater than 1, show the total Order_Amount_INR grouped by Payment_Method."
    parts = split_multi_part_question(q)
    assert len(parts) == 1, f"Expected 1 part, got {len(parts)}: {parts}"
    assert "Category is Electronics" in parts[0]
    assert "grouped by Payment_Method" in parts[0]


def test_planner_prepositional_filter_extraction():
    """Verify 'orders in the Electronics category' extracts Category == Electronics."""
    df = pd.DataFrame({"Category": ["Electronics", "Clothing"], "Order_Amount": [100, 200]})
    meta = {
        "orders.csv": {
            "columns": list(df.columns),
            "data_types": {"Category": "object", "Order_Amount": "int64"},
            "row_count": len(df),
            "column_count": len(df.columns),
            "filename": "orders.csv",
        }
    }
    plan = build_query_plan(
        question="How many orders are in the Electronics category?",
        metadata=meta,
        default_dataset="orders.csv",
    )
    filters = plan.get("filters", [])
    assert len(filters) >= 1, "Expected at least 1 filter"
    cat_filter = next((f for f in filters if f.get("column") == "Category"), None)
    assert cat_filter is not None, "Expected filter on Category"
    assert cat_filter.get("value") == "Electronics"


def test_planner_implicit_or_filter():
    """Verify 'belong to Electronics OR Books' extracts Category == Electronics and Category == Books with OR logic."""
    df = pd.DataFrame({"Category": ["Electronics", "Books", "Toys"], "Order_Amount": [100, 200, 300]})
    meta = {
        "orders.csv": {
            "columns": list(df.columns),
            "data_types": {"Category": "object", "Order_Amount": "int64"},
            "row_count": len(df),
            "column_count": len(df.columns),
            "filename": "orders.csv",
        }
    }
    plan = build_query_plan(
        question="How many rows belong to Electronics OR Books?",
        metadata=meta,
        default_dataset="orders.csv",
    )
    filters = plan.get("filters", [])
    assert len(filters) >= 2, f"Expected at least 2 filter values, got {len(filters)}"
    assert plan.get("filter_logic") == "OR", f"Expected filter_logic OR, got {plan.get('filter_logic')}"
    vals = [f.get("value") for f in filters if f.get("column") == "Category"]
    assert "Electronics" in vals
    assert "Books" in vals


def test_planner_preserve_nonexistent_filter_value():
    """Verify non-existent categorical filter values are preserved as literals, not replaced with column names."""
    df = pd.DataFrame({"Category": ["Electronics", "Books"], "Order_Amount_INR": [100, 200]})
    meta = {
        "orders.csv": {
            "columns": list(df.columns),
            "data_types": {"Category": "object", "Order_Amount_INR": "int64"},
            "row_count": len(df),
            "column_count": len(df.columns),
            "filename": "orders.csv",
        }
    }
    plan = build_query_plan(
        question="What is the total Order_Amount_INR for the category NotPresentCategory?",
        metadata=meta,
        default_dataset="orders.csv",
    )
    filters = plan.get("filters", [])
    cat_filter = next((f for f in filters if f.get("column") == "Category"), None)
    assert cat_filter is not None, "Expected filter on Category"
    assert cat_filter.get("value") == "NotPresentCategory", f"Value was incorrectly modified: {cat_filter.get('value')}"


def test_planner_measure_vs_filter_column_disambiguation():
    """Verify numeric column mentioned in filter does not shadow numeric measure column in aggregation."""
    df = pd.DataFrame({"Experience": [1, 6, 8], "Salary": [50000, 80000, 90000], "Age": [25, 32, 35]})
    meta = {
        "emp.csv": {
            "columns": list(df.columns),
            "data_types": {"Experience": "int64", "Salary": "int64", "Age": "int64"},
            "row_count": len(df),
            "column_count": len(df.columns),
            "filename": "emp.csv",
        }
    }
    plan = build_query_plan(
        question="What is the total Salary for employees where Experience is greater than 5?",
        metadata=meta,
        default_dataset="emp.csv",
    )
    assert plan.get("column") == "Salary", f"Expected Salary as column, got {plan.get('column')}"


# -------------------------------------------------------------------------
# Integration Test: Dataset 57 Q7 Ground Truth
# -------------------------------------------------------------------------

def test_dataset_57_q7_ground_truth():
    """Dataset 57 Q7 Ground Truth:

    Category == 'Electronics' and Quantity > 1 grouped by Payment_Method:
    3 rows:
      Credit Card: 11,998.00
      Debit Card:   5,499.00
      UPI:          1,599.00
    Grand total: 19,096.00 (NOT 76,400.00).
    """
    db = Session(engine)
    try:
        user = db.query(User).filter(User.id == 20).first()
        assert user is not None, "User 20 not found"
        dataset = db.query(Dataset).filter(Dataset.id == 57).first()
        assert dataset is not None, "Dataset 57 not found"

        q = "For orders where Category is Electronics and Quantity is greater than 1, show the total Order_Amount_INR grouped by Payment_Method."
        req = AnalysisAskRequest(dataset_id=57, question=q, version="original")
        resp = DataAnalystService.ask_question(request=req, current_user=user, db=db)

        assert resp.result is not None, "Result was None"
        assert resp.result.total_rows == 3, f"Expected 3 rows, got {resp.result.total_rows}"
        assert "19,096" in resp.answer, f"Expected 19,096 in answer, got: {resp.answer}"

        # Verify payment methods and amounts
        rows = resp.result.rows
        methods = {list(r.values())[0]: float(list(r.values())[1]) for r in rows}
        assert "Credit Card" in methods
        assert abs(methods["Credit Card"] - 11998.0) < 0.1
        assert "Debit Card" in methods
        assert abs(methods["Debit Card"] - 5499.0) < 0.1
        assert "UPI" in methods
        assert abs(methods["UPI"] - 1599.0) < 0.1
        assert sum(methods.values()) == 19096.0
    finally:
        db.close()


# -------------------------------------------------------------------------
# Full 46-Question Multi-Dataset Audit Integration Test
# -------------------------------------------------------------------------

@pytest.mark.parametrize("ds_id,user_id,q,expected_kind,expected_val", [
    # Dataset 57
    (57, 20, "How many rows are in clean_customer_orders (2).csv?", "COUNT_ROWS", 50),
    (57, 20, "How many columns are in clean_customer_orders (2).csv?", "COLUMN_COUNT", 11),
    (57, 20, "List all column names in clean_customer_orders (2).csv.", "COLUMN_NAMES", 11),
    (57, 20, "How many orders are in the Electronics category?", "FILTERED_COUNT", 9),
    (57, 20, "Show all rows where Category is Electronics.", "SHOW_DATA", 9),
    (57, 20, "What is the total Order_Amount_INR for Electronics orders?", "SUM", 78190.0),
    (57, 20, "For orders where Category is Electronics and Quantity is greater than 1, show the total Order_Amount_INR grouped by Payment_Method.", "GROUP_SUM", {"total": 19096.0, "rows": 3}),
    (57, 20, "How many rows belong to Electronics OR Books?", "OR_COUNT", 17),
    (57, 20, "What is the total sum of Order_Amount_INR?", "SUM", 159327.0),
    (57, 20, "What is the total Order_Amount_INR for the category NotPresentCategory?", "ZERO_MATCH", 0),
    (57, 20, "Can you please tell me the average Order_Amount_INR", "AVERAGE", 3186.54),
    (57, 20, "which category has the highest Order_Amount_INR", "TOP_N", "Electronics"),
    # Dataset 33
    (33, 14, "How many rows are in orders (1).csv?", "COUNT_ROWS", 20),
    (33, 14, "How many columns are in orders (1).csv?", "COLUMN_COUNT", 8),
    (33, 14, "List all column names in orders (1).csv.", "COLUMN_NAMES", 8),
    (33, 14, "How many orders have order_status Delivered?", "FILTERED_COUNT", 13),
    (33, 14, "Show all rows where order_status is Delivered.", "SHOW_DATA", 13),
    (33, 14, "What is the total total_amount for Delivered orders?", "SUM", 15482.0),
    (33, 14, "For orders where order_status is Delivered and quantity is greater than 1, show the total total_amount grouped by product.", "GROUP_SUM", {"total": 3591.0, "rows": 3}),
    (33, 14, "How many rows belong to Delivered OR Shipped?", "OR_COUNT", 16),
    (33, 14, "What is the total sum of total_amount?", "SUM", 28475.0),
    (33, 14, "What is the total total_amount for the product NonExistentGadget?", "ZERO_MATCH", 0),
    (33, 14, "could you please tell me the average unit_price", "AVERAGE", 1329.0),
    (33, 14, "which product has highest total_amount", "TOP_N", "Mechanical Keyboard"),
    # Dataset 32
    (32, 14, "How many rows are in cgpa.csv?", "COUNT_ROWS", 18),
    (32, 14, "How many columns are in cgpa.csv?", "COLUMN_COUNT", 4),
    (32, 14, "List all column names in cgpa.csv.", "COLUMN_NAMES", 4),
    (32, 14, "How many students are in the 2021 Year?", "FILTERED_COUNT", 5),
    (32, 14, "Show all rows where Year is 2021.", "SHOW_DATA", 5),
    (32, 14, "What is the total Package for Year 2021?", "SUM", 28.90),
    (32, 14, "How many rows belong to Year 2020 OR 2021?", "OR_COUNT", 9),
    (32, 14, "What is the total sum of Package?", "SUM", 102.40),
    (32, 14, "What is the total Package for the Year 2099?", "ZERO_MATCH", 0),
    (32, 14, "Can you please tell me the highest CGPA", "MAXIMUM", 9.80),
    (32, 14, "which student has the highest Package", "TOP_N", "9.5"),
    # Dataset 43
    (43, 1, "How many rows are in real_employee_data.csv?", "COUNT_ROWS", 10),
    (43, 1, "How many columns are in real_employee_data.csv?", "COLUMN_COUNT", 4),
    (43, 1, "List all column names in real_employee_data.csv.", "COLUMN_NAMES", 4),
    (43, 1, "How many employees have Experience greater than 5?", "FILTERED_COUNT", 6),
    (43, 1, "Show all rows where Experience is greater than 5.", "SHOW_DATA", 6),
    (43, 1, "What is the total Salary for employees where Experience is greater than 5?", "SUM", 897000.0),
    (43, 1, "For employees where Experience is greater than 5 and Age is greater than 30, show the total Salary grouped by Age.", "GROUP_SUM", {"total": 897000.0, "rows": 6}),
    (43, 1, "How many rows belong to Experience == 2 OR Experience == 3?", "OR_COUNT", 2),
    (43, 1, "What is the total sum of Salary?", "SUM", 1127000.0),
    (43, 1, "What is the total Salary for Age 99?", "ZERO_MATCH", 0),
    (43, 1, "Can you please tell me the average Salary", "AVERAGE", 112700.0),
])
def test_46_question_audit(ds_id, user_id, q, expected_kind, expected_val):
    """Executes each question in the 46-question multi-dataset audit."""
    db = Session(engine)
    try:
        user = db.query(User).filter(User.id == user_id).first()
        assert user is not None, f"User {user_id} not found"
        dataset = db.query(Dataset).filter(Dataset.id == ds_id).first()
        assert dataset is not None, f"Dataset {ds_id} not found"

        req = AnalysisAskRequest(dataset_id=ds_id, question=q, version="original")
        resp = DataAnalystService.ask_question(request=req, current_user=user, db=db)
        ans = resp.answer

        if expected_kind == "COUNT_ROWS":
            assert resp.result and resp.result.total_rows == 1
            assert str(expected_val) in ans
        elif expected_kind == "COLUMN_COUNT":
            assert resp.operation_performed == "Data Types"
            assert str(expected_val) in ans
            assert "columns" in ans.lower()
        elif expected_kind == "COLUMN_NAMES":
            assert resp.operation_performed == "Data Types"
            assert resp.result and resp.result.total_rows == expected_val
        elif expected_kind == "FILTERED_COUNT":
            assert str(expected_val) in ans
            assert resp.result and resp.result.rows and list(resp.result.rows[0].values())[0] == expected_val
        elif expected_kind == "SHOW_DATA":
            assert resp.result and resp.result.total_rows == expected_val
        elif expected_kind == "SUM":
            assert f"{expected_val:,.2f}" in ans or f"{expected_val:,.0f}" in ans or (resp.result and resp.result.rows and abs(float(list(resp.result.rows[0].values())[0]) - float(expected_val)) < 0.1)
        elif expected_kind == "GROUP_SUM":
            assert resp.result and resp.result.total_rows == expected_val["rows"]
            assert f"{expected_val['total']:,.2f}" in ans
        elif expected_kind == "OR_COUNT":
            assert str(expected_val) in ans
            assert resp.result and resp.result.rows and list(resp.result.rows[0].values())[0] == expected_val
        elif expected_kind == "ZERO_MATCH":
            assert "no records match" in ans.lower() or "cannot determine" in ans.lower() or (resp.result and resp.result.total_rows == 0)
        elif expected_kind == "AVERAGE":
            assert f"{expected_val:,.2f}" in ans or (resp.result and resp.result.rows and abs(float(list(resp.result.rows[0].values())[0]) - float(expected_val)) < 0.1)
        elif expected_kind == "MAXIMUM":
            assert f"{expected_val:,.2f}" in ans or str(expected_val) in ans
        elif expected_kind == "TOP_N":
            assert str(expected_val).lower() in ans.lower()
    finally:
        db.close()
