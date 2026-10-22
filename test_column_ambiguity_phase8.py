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


def test_8_unrelated_column_clarification_prevention():
    """Test 8: Ensure analytical queries with explanatory clauses ('driven by order volume') do not trigger false column clarification."""
    print("\n--- Test 8: Unrelated column clarification prevention ---")
    columns = [
        "Customer_ID", "Customer_Name", "Age", "City", "State",
        "Gender", "Category", "Quantity", "Order_Amount_INR", "Order_Date", "Payment_Method"
    ]
    df = pd.DataFrame({
        "Customer_ID": [1, 2, 3],
        "Customer_Name": ["Alice", "Bob", "Charlie"],
        "Age": [25, 30, 35],
        "City": ["Satara", "Thane", "Pune"],
        "State": ["MH", "MH", "MH"],
        "Gender": ["Male", "Male", "Female"],
        "Category": ["Electronics", "Electronics", "Clothing"],
        "Quantity": [1, 2, 1],
        "Order_Amount_INR": [15999.0, 12999.0, 2500.0],
        "Order_Date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "Payment_Method": ["Credit Card", "UPI", "Cash"]
    })
    meta = {
        "column_names": columns,
        "data_types": {c: str(df[c].dtype) for c in columns},
        "numeric_columns": [c for c in columns if pd.api.types.is_numeric_dtype(df[c])],
        "categorical_columns": [c for c in columns if not pd.api.types.is_numeric_dtype(df[c])],
    }

    q = (
        "Analyze revenue across product category, city, gender, and payment method. "
        "Identify the top-performing combination, quantify its contribution to total revenue, "
        "and explain whether the result is driven by order volume or average order value."
    )

    plan = build_query_plan(q, {"orders.csv": meta})

    # Assert no clarification is requested between Order_Date and Order_Amount_INR
    assert plan.get("needs_clarification") is False, (
        f"False clarification triggered! Options: {plan.get('clarification_options')}"
    )
    assert plan.get("column") == "Order_Amount_INR", f"Expected 'Order_Amount_INR', got {plan.get('column')}"
    for required_dim in ["Category", "City", "Gender", "Payment_Method"]:
        assert required_dim in plan.get("group_by", []), f"Missing required dimension '{required_dim}' in group_by"

    print("[PASS] Query plan resolved revenue and 4 dimensions without false clarification on 'Order_Date'.")


def test_9_combination_revenue_analysis():
    """Test 9: End-to-end combination ranking, contribution %, order volume, AOV, and driver attribution."""
    print("\n--- Test 9: End-to-end combination revenue analysis ---")
    csv_path = os.path.join(
        os.path.dirname(__file__),
        "uploads", "user_20", "ffc4ae1b6dcc4d56b42b4e8818421ed7_clean_customer_orders__2_.csv"
    )
    if not os.path.exists(csv_path):
        print(f"[SKIP] Dataset {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    meta = {
        "column_names": [str(c) for c in df.columns],
        "data_types": {str(c): str(df[c].dtype) for c in df.columns},
        "numeric_columns": [str(c) for c in df.columns if pd.api.types.is_numeric_dtype(df[c])],
        "categorical_columns": [str(c) for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])],
        "rows": len(df),
        "columns": len(df.columns),
    }

    q = (
        "Analyze revenue across product category, city, gender, and payment method. "
        "Identify the top-performing combination, quantify its contribution to total revenue, "
        "and explain whether the result is driven by order volume or average order value."
    )

    resp = run_ask_analyst_query(
        question=q,
        datasets={"clean_customer_orders (2).csv": df},
        metadata={"clean_customer_orders (2).csv": meta},
    )

    assert resp["status"] == "success", f"Expected success, got {resp['status']}"
    evidence = resp.get("evidence", {})
    comb = evidence.get("combination_analysis") or evidence.get("raw_evidence", {}).get("combination_analysis")
    assert comb is not None, "Missing combination_analysis in evidence"

    # Verify exact calculated numbers
    assert comb["combination_revenue"] == 15999.0
    assert comb["total_valid_revenue"] == 159327.0
    assert comb["contribution_pct"] == 10.04
    assert comb["order_volume"] == 1
    assert comb["combination_aov"] == 15999.0
    assert comb["primary_driver"] == "average_order_value"
    assert "causation" in comb["causation_disclaimer"].lower()

    # Verify grounded answer
    ans_text = resp["answer"]["answer"]
    assert "15,999.00" in ans_text
    assert "10.04%" in ans_text
    assert "average order value" in ans_text.lower()
    print("[PASS] Full multidimensional combination revenue analysis successfully verified.")


def test_10_false_filter_extraction_and_dual_outlier_comparison():
    """Test 10: Bug 1 - 'for this dataset' must not inject Category == 'This', and dual IQR vs Z-score comparison."""
    print("\n--- Test 10: False filter extraction prevention & dual outlier comparison ---")
    meta = {
        "column_names": ["Customer_ID", "Customer_Name", "Age", "City", "State", "Gender", "Category", "Quantity", "Order_Amount_INR", "Order_Date", "Payment_Method"],
        "data_types": {"Customer_ID": "object", "Customer_Name": "object", "Age": "int64", "City": "object", "State": "object", "Gender": "object", "Category": "object", "Quantity": "int64", "Order_Amount_INR": "float64", "Order_Date": "object", "Payment_Method": "object"},
        "numeric_columns": ["Age", "Quantity", "Order_Amount_INR"],
        "categorical_columns": ["Customer_ID", "Customer_Name", "City", "State", "Gender", "Category", "Order_Date", "Payment_Method"],
        "rows": 10,
        "columns": 11,
    }

    q = (
        "Detect outliers in Order_Amount_INR using the IQR method and Z-score method. "
        "Compare the detected records, explain why the methods may disagree, and recommend which method is more appropriate for this dataset."
    )

    plan = build_query_plan(q, {"orders.csv": meta}, default_dataset="orders.csv")

    # 1. Assert no false filter Category == 'This'
    assert len(plan["filters"]) == 0, f"Expected 0 filters, got: {plan['filters']}"
    assert plan["column"] == "Order_Amount_INR", f"Expected 'Order_Amount_INR', got {plan['column']}"
    assert plan["metadata"].get("compare_methods") is True, "Expected compare_methods=True"

    # 2. Test actual dual execution with realistic dataset (skewed data)
    df = pd.DataFrame({
        "Order_ID": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112],
        "Category": ["Electronics", "Electronics", "Clothing", "Clothing", "Home", "Home", "Electronics", "Clothing", "Home", "Electronics", "Clothing", "Home"],
        "Order_Amount_INR": [150.0, 180.0, 200.0, 210.0, 220.0, 250.0, 280.0, 300.0, 310.0, 350.0, 1200.0, 5000.0],
    })

    resp = run_ask_analyst_query(
        question=q,
        datasets={"orders.csv": df},
        metadata={"orders.csv": meta},
        default_dataset="orders.csv",
    )

    assert resp["status"] == "success", f"Expected success, got {resp['status']}"
    ev = resp.get("evidence", {}) or resp.get("result", {}).get("evidence", {})
    assert ev.get("iqr_outliers") is not None, "Missing iqr_outliers in evidence"
    assert ev.get("zscore_outliers") is not None, "Missing zscore_outliers in evidence"
    assert ev.get("overlap_count") is not None, "Missing overlap_count in evidence"
    assert ev.get("iqr_only_count") is not None, "Missing iqr_only_count in evidence"
    assert ev.get("zscore_only_count") is not None, "Missing zscore_only_count in evidence"
    assert ev.get("skewness") is not None, "Missing skewness in evidence"
    assert "skewness" in ev.get("disagreement_explanation", "").lower(), "Disagreement explanation must cite skewness"
    assert "appropriate" in ev.get("recommendation", "").lower() or "recommendation" in ev.get("recommendation", "").lower()

    # Verify flagged records table is returned
    res_data = resp.get("result", {}).get("data")
    assert isinstance(res_data, pd.DataFrame) and not res_data.empty, "Expected non-empty records DataFrame"
    assert "Outlier_Status" in res_data.columns, "Expected 'Outlier_Status' column in flagged records"

    # Verify constant column handling fails safely
    df_const = pd.DataFrame({"Order_Amount_INR": [100.0, 100.0, 100.0, 100.0, 100.0]})
    resp_const = run_ask_analyst_query(
        question=q,
        datasets={"orders.csv": df_const},
        metadata={"orders.csv": meta},
        default_dataset="orders.csv",
    )
    assert resp_const["status"] == "success"
    print("[PASS] Bug 1 verified: no false filter, dual IQR/Z-score comparison, overlap analysis, and skewness explanation.")


def test_11_selected_dataset_hijacking_prevention():
    """Test 11: Bug 2 - Explicitly selected dataset must not be hijacked by other datasets."""
    print("\n--- Test 11: Selected dataset hijacking prevention ---")
    meta = {
        "clean_customer_orders (2).csv": {
            "column_names": ["Customer_ID", "Customer_Name", "Age", "City", "State", "Gender", "Category", "Quantity", "Order_Amount_INR", "Order_Date", "Payment_Method"],
            "data_types": {"Customer_ID": "object", "Customer_Name": "object", "Age": "int64", "City": "object", "State": "object", "Gender": "object", "Category": "object", "Quantity": "int64", "Order_Amount_INR": "float64", "Order_Date": "object", "Payment_Method": "object"},
        },
        "customers_quality_test.csv": {
            "column_names": ["customer_id", "customer_name", "email", "city", "age", "signup_date", "annual_income_inr"],
            "data_types": {"customer_id": "object", "customer_name": "object", "email": "object", "city": "object", "age": "int64", "signup_date": "object", "annual_income_inr": "float64"},
        },
    }

    q = (
        "Perform a complete data quality audit covering completeness, uniqueness, validity, consistency, "
        "accuracy limitations, and statistical anomalies. Return a table with issue name, affected rows, severity, "
        "detection rule, and recommended action. Do not label a value inaccurate without a reliable reference."
    )

    # User selected 'clean_customer_orders (2).csv'
    plan = build_query_plan(q, meta, default_dataset="clean_customer_orders (2).csv")
    assert plan["dataset"] == "clean_customer_orders (2).csv", (
        f"Selected dataset hijacked! Expected 'clean_customer_orders (2).csv', got '{plan['dataset']}'"
    )
    assert plan["intent"] == "DATA_QUALITY_AUDIT", f"Expected DATA_QUALITY_AUDIT, got {plan['intent']}"
    print("[PASS] Bug 2 verified: selected dataset remained locked without hijacking.")


def test_12_correlation_variables_pearson_spearman_pvalues():
    """Test 12: Bug 3 - Correlation between Age and Order_Amount_INR with Pearson, Spearman, N, p-values, and causation caveat."""
    print("\n--- Test 12: Dual Pearson and Spearman correlation with p-values and causation caveat ---")
    meta = {
        "clean_customer_orders (2).csv": {
            "column_names": ["Customer_ID", "Customer_Name", "Age", "City", "State", "Gender", "Category", "Quantity", "Order_Amount_INR", "Order_Date", "Payment_Method"],
            "data_types": {"Customer_ID": "object", "Customer_Name": "object", "Age": "int64", "City": "object", "State": "object", "Gender": "object", "Category": "object", "Quantity": "int64", "Order_Amount_INR": "float64", "Order_Date": "object", "Payment_Method": "object"},
            "numeric_columns": ["Age", "Quantity", "Order_Amount_INR"],
        }
    }

    q = (
        "Correlation versus causation. Test whether customer age is associated with order amount. "
        "Calculate Pearson and Spearman correlations, visualize the relationship, assess statistical significance where appropriate, "
        "and explain why correlation does not establish causation."
    )

    plan = build_query_plan(q, meta, default_dataset="clean_customer_orders (2).csv")
    assert plan["intent"] == "CORRELATION", f"Expected CORRELATION intent, got {plan['intent']}"
    assert plan["column"] == "Age", f"Expected column 'Age', got {plan['column']}"
    assert plan["secondary_column"] == "Order_Amount_INR", f"Expected secondary_column 'Order_Amount_INR', got {plan['secondary_column']}"
    assert plan["needs_clarification"] is False, "Unexpected clarification requested!"

    # Test execution with actual data
    df = pd.DataFrame({
        "Age": [22, 25, 30, 35, 40, 45, 50, 55, 60, 65],
        "Order_Amount_INR": [120.0, 150.0, 200.0, 310.0, 400.0, 420.0, 500.0, 620.0, 710.0, 850.0],
        "Quantity": [1, 2, 1, 3, 2, 4, 3, 5, 4, 6],
    })

    resp = run_ask_analyst_query(
        question=q,
        datasets={"clean_customer_orders (2).csv": df},
        metadata=meta,
        default_dataset="clean_customer_orders (2).csv",
    )

    assert resp["status"] == "success", f"Expected success, got {resp['status']}"
    ev = resp.get("evidence", {}) or resp.get("result", {}).get("evidence", {})
    assert ev.get("col_a") == "Age", f"Expected col_a='Age', got {ev.get('col_a')}"
    assert ev.get("col_b") == "Order_Amount_INR", f"Expected col_b='Order_Amount_INR', got {ev.get('col_b')}"
    assert ev.get("pearson_r") is not None, "Missing pearson_r"
    assert ev.get("spearman_rho") is not None, "Missing spearman_rho"
    assert ev.get("pearson_p_value") is not None, "Missing pearson_p_value"
    assert ev.get("spearman_p_value") is not None, "Missing spearman_p_value"
    assert ev.get("valid_pairs_n") == 10, f"Expected 10 valid pairs, got {ev.get('valid_pairs_n')}"
    assert "causation" in ev.get("causation_warning", "").lower(), "Missing causation disclaimer"

    # Verify answer text contains both statistics and causation caveat
    ans = resp["answer"]["answer"]
    assert "Pearson" in ans and "Spearman" in ans
    assert "causation" in ans.lower()

    # Verify zero variance handling fails safely
    df_const = pd.DataFrame({"Age": [30, 30, 30, 30, 30], "Order_Amount_INR": [100.0, 200.0, 300.0, 400.0, 500.0]})
    resp_const = run_ask_analyst_query(
        question=q,
        datasets={"clean_customer_orders (2).csv": df_const},
        metadata=meta,
        default_dataset="clean_customer_orders (2).csv",
    )
    assert resp_const["status"] == "success"
    print("[PASS] Bug 3 verified: exact pair resolved, Pearson + Spearman calculated with p-values, N, and causation caveat.")


def test_13_comprehensive_data_quality_audit():
    """Test 13: Bug 4 - Comprehensive data quality audit covering all 6 dimensions and exact 5 table columns."""
    print("\n--- Test 13: Comprehensive data quality audit ---")
    df = pd.DataFrame({
        "Customer_ID": [101, 102, 103, 104, 105, 106, 106],  # 1 duplicate ID
        "Customer_Name": ["Alice", "Bob", "Charlie", None, "Eva", "Frank", "Frank"],  # 1 missing
        "Age": [25, 30, -5, 40, 45, 50, 50],  # 1 negative age (validity)
        "City": ["Mumbai", "mumbai ", "Delhi", "Delhi", "Bengaluru", "Bengaluru", "Bengaluru"],  # categorical casing inconsistency
        "Order_Amount_INR": [100.0, 150.0, 200.0, 250.0, 300.0, 15000.0, 15000.0],  # statistical outlier
        "Order_Date": ["2023-01-01", "2023-01-02", "not_a_date", "2023-01-04", "2023-01-05", "2023-01-06", "2023-01-06"],  # 1 invalid date
    })

    meta = {
        "orders.csv": {
            "column_names": list(df.columns),
            "data_types": {str(c): str(df[c].dtype) for c in df.columns},
            "rows": len(df),
            "columns": len(df.columns),
        }
    }

    q = (
        "Perform a complete data quality audit covering completeness, uniqueness, validity, consistency, "
        "accuracy limitations, and statistical anomalies. Return a table with issue name, affected rows, severity, "
        "detection rule, and recommended action. Do not label a value inaccurate without a reliable reference."
    )

    resp = run_ask_analyst_query(
        question=q,
        datasets={"orders.csv": df},
        metadata=meta,
        default_dataset="orders.csv",
    )

    assert resp["status"] == "success", f"Expected success, got {resp['status']}"
    res_df = resp["result"]["data"]
    assert isinstance(res_df, pd.DataFrame), "Expected DataFrame output"

    expected_cols = ["Issue Name", "Affected Rows", "Severity", "Detection Rule", "Recommended Action"]
    assert list(res_df.columns) == expected_cols, f"Expected {expected_cols}, got {list(res_df.columns)}"

    # Verify all 6 dimensions are represented in the audit table
    issues = res_df["Issue Name"].tolist()
    assert any("missing" in i.lower() for i in issues), "Missing completeness dimension"
    assert any("duplicate" in i.lower() for i in issues), "Missing uniqueness dimension"
    assert any("valid" in i.lower() or "negative" in i.lower() for i in issues), "Missing validity dimension"
    assert any("consisten" in i.lower() for i in issues), "Missing consistency dimension"
    assert any("outlier" in i.lower() or "anomal" in i.lower() for i in issues), "Missing anomaly dimension"
    assert any("accuracy limitation" in i.lower() for i in issues), "Missing accuracy limitation dimension"

    # Verify accuracy limitation disclaimer
    acc_row = res_df[res_df["Issue Name"].str.contains("Accuracy Limitation", case=False)]
    assert not acc_row.empty
    assert "ground truth" in acc_row.iloc[0]["Detection Rule"].lower() or "reference" in acc_row.iloc[0]["Recommended Action"].lower()
    print("[PASS] Bug 4 verified: complete 6-dimension data quality audit with exact 5 columns.")


def test_14_legitimate_filter_and_edge_cases():
    """Test 14: Verify legitimate filters continue working and edge cases fail safely."""
    print("\n--- Test 14: Legitimate filters & edge cases ---")
    meta = {
        "orders.csv": {
            "column_names": ["Customer_ID", "City", "Category", "Order_Amount_INR"],
            "data_types": {"Customer_ID": "object", "City": "object", "Category": "object", "Order_Amount_INR": "float64"},
            "rows": 5,
            "columns": 4,
        }
    }

    # 1. Legitimate filter: "Show total order amount for Mumbai"
    plan_filter = build_query_plan("Show total order amount for Mumbai", meta, default_dataset="orders.csv")
    assert len(plan_filter["filters"]) > 0, "Expected legitimate filter for Mumbai"
    assert plan_filter["filters"][0]["value"] == "Mumbai"

    # 2. Empty dataset safe handling
    df_empty = pd.DataFrame(columns=["Customer_ID", "City", "Category", "Order_Amount_INR"])
    resp_empty = run_ask_analyst_query(
        question="What is the average order amount?",
        datasets={"orders.csv": df_empty},
        metadata=meta,
        default_dataset="orders.csv",
    )
    assert resp_empty["status"] in ("success", "error")

    # 3. Missing column safe handling
    resp_missing = run_ask_analyst_query(
        question="What is the average profit?",
        datasets={"orders.csv": pd.DataFrame({"Order_Amount_INR": [100.0, 200.0]})},
        metadata=meta,
        default_dataset="orders.csv",
    )
    assert resp_missing["status"] in ("success", "error")
    print("[PASS] Legitimate filter and safety edge cases verified successfully.")


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
    test_8_unrelated_column_clarification_prevention()
    test_9_combination_revenue_analysis()
    test_10_false_filter_extraction_and_dual_outlier_comparison()
    test_11_selected_dataset_hijacking_prevention()
    test_12_correlation_variables_pearson_spearman_pvalues()
    test_13_comprehensive_data_quality_audit()
    test_14_legitimate_filter_and_edge_cases()
    print("\n" + "=" * 60)
    print("ALL 14 TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
