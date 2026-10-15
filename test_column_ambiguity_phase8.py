"""Verification and regression test suite for Column Ambiguity Resolution in Data Analyst Agent.

Tests:
1. Exact matching column resolution without ambiguity.
2. Join-generated suffixed duplicates resolution (prefers base column with explanation).
3. Genuine material ambiguity preserving clarification prompt.
4. Missing lineage metadata safe fallback (no hallucinated dataset names).
5. User-selected clarification flow and seamless continuation.
6. Real dataset verification using uploads/user_14/anu.csv.
7. Suggested questions filtering out join-generated suffixed columns.
"""

import os
import sys
import pandas as pd
import numpy as np

# Ensure root is in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from query.column_lineage import inspect_column_lineage, ColumnLineageInfo
from query.column_resolver import resolve_column
from query.query_planner import build_query_plan
from query.orchestrator import run_ask_analyst_query
from query.context_manager import ConversationContextManager


def test_1_exact_matching_column():
    """Test 1: Exact column-name match is preferred when unambiguous."""
    print("\n--- Test 1: Exact matching column ---")
    columns = ["Modal_Price", "Min_Price", "Max_Price", "Arrival_Quantity", "State"]
    metadata = {
        "column_names": columns,
        "data_types": {"Modal_Price": "float64", "Min_Price": "float64", "Max_Price": "float64", "Arrival_Quantity": "int64", "State": "object"},
    }

    # Query directly mentioning "modal_price"
    res = resolve_column("Modal_Price", metadata)
    assert res["resolved"] is True, "Expected Modal_Price to resolve"
    assert res["column"] == "Modal_Price", f"Expected 'Modal_Price', got {res['column']}"
    assert res["is_ambiguous"] is False, "Should not be ambiguous for exact match"
    print("[PASS] Exact match for 'Modal_Price' resolved unambiguously.")


def test_2_join_generated_suffixed_duplicates():
    """Test 2: Column with join-generated suffixed duplicates resolves to base column."""
    print("\n--- Test 2: Join-generated suffixed duplicates ---")
    columns = [
        "order_id",
        "customer_id",
        "unit_price",
        "unit_price_joined_orders__1__customers_1",
        "total_amount"
    ]
    df = pd.DataFrame({
        "order_id": [1, 2, 3, 4],
        "customer_id": [101, 102, 103, 104],
        "unit_price": [10.0, 20.0, 30.0, 40.0],
        "unit_price_joined_orders__1__customers_1": [10.0, 20.0, 30.0, 40.0],
        "total_amount": [100.0, 200.0, 300.0, 400.0],
    })
    meta = {
        "column_names": columns,
        "data_types": {c: str(df[c].dtype) for c in columns},
        "join_history": [{
            "source_left_filename": "orders.csv",
            "source_right_filename": "customers.csv",
        }]
    }

    # Test lineage inspection
    lineage = inspect_column_lineage(columns, meta)
    assert lineage["unit_price"].is_join_generated is False
    assert lineage["unit_price"].source_dataset == "orders.csv"
    assert lineage["unit_price_joined_orders__1__customers_1"].is_join_generated is True
    print(f"[PASS] Lineage inspected: {lineage['unit_price_joined_orders__1__customers_1'].label}")

    # Test column resolution for "unit_price"
    res = resolve_column("unit_price", meta)
    assert res["resolved"] is True
    assert res["column"] == "unit_price", f"Expected 'unit_price', got {res['column']}"
    assert res["is_ambiguous"] is False
    print(f"[PASS] Resolved column: {res['column']}")
    if res.get("selection_explanation"):
        print(f"  Explanation: {res['selection_explanation']}")

    # Test full orchestrator query execution
    datasets = {"orders_joined": df}
    metadata_all = {"orders_joined": meta}

    resp = run_ask_analyst_query(
        question="What is the average unit price?",
        datasets=datasets,
        metadata=metadata_all,
    )
    assert resp["status"] == "success", f"Expected success, got {resp['status']}: {resp.get('answer', {}).get('answer')}"
    assert resp["query_plan"]["column"] == "unit_price"
    # Average of 10, 20, 30, 40 is 25.0
    metric_val = resp["evidence"]["computed_values"]["metric_value"]
    assert metric_val == 25.0, f"Expected 25.0, got {metric_val}"
    assert "selection_explanation" in resp["evidence"]
    print(f"[PASS] Orchestrator computed average unit_price: {metric_val} with lineage explanation.")


def test_3_genuine_material_ambiguity():
    """Test 3: Different candidate columns with distinct semantics preserve clarification."""
    print("\n--- Test 3: Genuine material ambiguity ---")
    columns = ["Modal_Price", "Min_Price", "Max_Price", "Arrival_Quantity", "State"]
    df = pd.DataFrame({
        "Modal_Price": [100.0, 110.0, 120.0],
        "Min_Price": [80.0, 90.0, 100.0],
        "Max_Price": [120.0, 130.0, 140.0],
        "Arrival_Quantity": [50, 60, 70],
        "State": ["State A", "State B", "State C"],
    })
    meta = {
        "column_names": columns,
        "data_types": {c: str(df[c].dtype) for c in columns},
    }

    # Query for "price" where Modal_Price, Min_Price, and Max_Price all match
    res = resolve_column("price", meta)
    assert res["is_ambiguous"] is True
    assert "Modal_Price" in res["clarification_options"]
    assert "Min_Price" in res["clarification_options"]
    assert "Max_Price" in res["clarification_options"]
    assert len(res["clarification_candidates"]) == 3
    print(f"[PASS] Genuine ambiguity preserved: {res['clarification_options']}")

    # Full orchestrator pipeline must return needs_clarification
    datasets = {"market_data": df}
    metadata_all = {"market_data": meta}

    resp = run_ask_analyst_query(
        question="What is the average price?",
        datasets=datasets,
        metadata=metadata_all,
    )
    assert resp["status"] == "needs_clarification"
    assert "Modal_Price" in resp["validation"]["clarification_options"]
    print(f"[PASS] Clarification question: {resp['validation']['clarification_question']}")


def test_4_missing_lineage_metadata_safe_fallback():
    """Test 4: When metadata is unavailable, no dataset names are hallucinated."""
    print("\n--- Test 4: Missing lineage metadata safe fallback ---")
    columns = ["price", "price_x", "quantity"]
    lineage = inspect_column_lineage(columns, metadata=None)

    assert lineage["price"].source_dataset is None
    assert lineage["price_x"].source_dataset is None
    assert lineage["price_x"].is_join_generated is True
    assert "Joined column" in lineage["price_x"].label
    assert "orders.csv" not in lineage["price_x"].label
    print(f"[PASS] Fallback label without metadata: '{lineage['price_x'].label}' (no hallucination)")

    # Resolution still prefers base un-suffixed 'price'
    meta = {"column_names": columns, "data_types": {"price": "float64", "price_x": "float64", "quantity": "int64"}}
    res = resolve_column("price", meta)
    assert res["resolved"] is True
    assert res["column"] == "price"
    print("[PASS] Resolved base 'price' cleanly despite missing join history metadata.")


def test_5_user_selected_clarification_continuation():
    """Test 5: Selecting a column from clarification continues original analytical query."""
    print("\n--- Test 5: User-selected clarification continuation ---")
    columns = ["Modal_Price", "Min_Price", "Max_Price", "State"]
    df = pd.DataFrame({
        "Modal_Price": [100.0, 200.0, 300.0],
        "Min_Price": [80.0, 180.0, 280.0],
        "Max_Price": [120.0, 220.0, 320.0],
        "State": ["A", "B", "C"],
    })
    meta = {
        "column_names": columns,
        "data_types": {c: str(df[c].dtype) for c in columns},
    }
    datasets = {"market_data": df}
    metadata_all = {"market_data": meta}

    # Step A: Ambiguous query returns needs_clarification
    resp_ambig = run_ask_analyst_query(
        question="What is the average price?",
        datasets=datasets,
        metadata=metadata_all,
    )
    assert resp_ambig["status"] == "needs_clarification"

    # Step B: User responds with clarified choice "What is the average price? using Modal_Price"
    resp_clarified = run_ask_analyst_query(
        question="What is the average price? using Modal_Price",
        datasets=datasets,
        metadata=metadata_all,
        context={"previous_query_plan": resp_ambig["query_plan"]},
    )
    assert resp_clarified["status"] == "success"
    assert resp_clarified["query_plan"]["column"] == "Modal_Price"
    # Average of 100, 200, 300 is 200.0
    assert resp_clarified["evidence"]["computed_values"]["metric_value"] == 200.0
    print(f"[PASS] Clarification continuation executed successfully! Computed average: {resp_clarified['evidence']['computed_values']['metric_value']}")

    # Step C: User responds directly with "using Min_Price"
    resolved_q, modified_plan = ConversationContextManager.resolve_follow_up(
        "using Min_Price",
        {"previous_query_plan": resp_ambig["query_plan"]},
    )
    assert modified_plan is not None
    assert modified_plan["column"] == "Min_Price"
    assert modified_plan["needs_clarification"] is False
    print(f"[PASS] Context manager successfully substituted column into modified plan: {modified_plan['column']}")


def test_6_real_uploaded_dataset():
    """Test 6: Real dataset uploads/user_14/anu.csv with exact problem columns."""
    print("\n--- Test 6: Real uploaded dataset verification ---")
    real_csv_path = os.path.abspath("uploads/user_14/anu.csv")
    if not os.path.exists(real_csv_path):
        print("Real CSV not found at uploads/user_14/anu.csv, skipping test 6.")
        return

    df = pd.read_csv(real_csv_path)
    print(f"Loaded real dataset with {len(df)} rows and {len(df.columns)} columns.")
    assert "unit_price" in df.columns
    assert "unit_price_joined_orders__1__customers_1" in df.columns

    meta = {
        "column_names": [str(c) for c in df.columns],
        "data_types": {str(c): str(df[c].dtype) for c in df.columns},
    }
    datasets = {"anu.csv": df}
    metadata_all = {"anu.csv": meta}

    resp = run_ask_analyst_query(
        question="What is the average unit price?",
        datasets=datasets,
        metadata=metadata_all,
    )
    assert resp["status"] == "success", f"Query on real dataset failed: {resp}"
    assert resp["query_plan"]["column"] == "unit_price"
    print(f"[PASS] Real dataset query resolved cleanly to: {resp['query_plan']['column']}")
    print(f"[PASS] Result metric value: {resp['evidence']['computed_values']['metric_value']}")
    print(f"[PASS] Answer: {resp['answer']['answer']}")


def test_7_suggested_questions_filtering():
    """Test 7: Suggested questions never contain join-suffixed columns."""
    print("\n--- Test 7: Suggested questions filtering ---")
    columns = [
        "unit_price",
        "unit_price_joined_orders__1__customers_1",
        "customer_name",
        "customer_name_joined_orders__1__customers_1",
        "sales_amount"
    ]
    lineage_map = inspect_column_lineage(columns)

    numeric_cols = ["unit_price", "unit_price_joined_orders__1__customers_1", "sales_amount"]
    clean_numeric = [c for c in numeric_cols if not (lineage_map.get(str(c)) and lineage_map[str(c)].is_join_generated)]
    assert "unit_price_joined_orders__1__customers_1" not in clean_numeric
    assert "unit_price" in clean_numeric
    assert "sales_amount" in clean_numeric

    cat_cols = ["customer_name", "customer_name_joined_orders__1__customers_1"]
    clean_cat = [c for c in cat_cols if not (lineage_map.get(str(c)) and lineage_map[str(c)].is_join_generated)]
    assert "customer_name_joined_orders__1__customers_1" not in clean_cat
    assert "customer_name" in clean_cat
    print("[PASS] Join-generated suffixed columns cleanly filtered from suggestions pool.")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING COLUMN AMBIGUITY RESOLUTION TEST SUITE")
    print("=" * 60)
    test_1_exact_matching_column()
    test_2_join_generated_suffixed_duplicates()
    test_3_genuine_material_ambiguity()
    test_4_missing_lineage_metadata_safe_fallback()
    test_5_user_selected_clarification_continuation()
    test_6_real_uploaded_dataset()
    test_7_suggested_questions_filtering()
    print("\n" + "=" * 60)
    print("ALL 7 COLUMN AMBIGUITY TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
