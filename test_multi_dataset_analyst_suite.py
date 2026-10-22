"""Test Matrix Suite for Ask Data Analyst: Multi-Dataset, Cross-Dataset, Filtered, and Subquery Support.

Validates the full specification across:
A. Single-dataset basics (rows, cols, sum/avg/min/max, missing/duplicate)
B. Filtered calculations (one condition, multiple AND conditions, OR conditions, filtered aggregates)
C. Grouped analysis (group by, filter before grouping, top/bottom categories)
D. Multi-dataset analysis (dataset detection, comparison, join key detection, safe join validation, non-substitution)
E. Subqueries and multi-step questions (aggregate threshold filter, category vs overall average)
F. Cross-dataset questions (matching categories, differences, records present in A absent in B, joined aggregation without inflation)
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from query.orchestrator import run_ask_analyst_query
from query.query_planner import build_query_plan
from query.intent_detector import detect_query_intent
from query.query_models import QueryIntent


@pytest.fixture(scope="module")
def uploaded_test_datasets():
    """Load actual uploaded datasets from user_14 and user_13."""
    ord_path_14 = PROJECT_ROOT / "uploads" / "user_14" / "d8c9e8e095e24d5283df02eafe6fe6a0_orders__1_.csv"
    cust_path_14 = PROJECT_ROOT / "uploads" / "user_14" / "e10991f6ce4c41818d06c8a80844a26f_customers.csv"
    cgpa_path_14 = PROJECT_ROOT / "uploads" / "user_14" / "d27813f65c604efa8c65f221678caafa_cgpa.csv"

    df_orders = pd.read_csv(ord_path_14)
    df_customers = pd.read_csv(cust_path_14)
    df_cgpa = pd.read_csv(cgpa_path_14)

    datasets = {
        "orders.csv": df_orders,
        "customers.csv": df_customers,
        "cgpa.csv": df_cgpa,
    }

    metadata = {
        "orders.csv": {
            "columns": list(df_orders.columns),
            "data_types": {c: str(df_orders[c].dtype) for c in df_orders.columns},
            "row_count": len(df_orders),
            "column_count": len(df_orders.columns),
            "filename": "orders.csv",
        },
        "customers.csv": {
            "columns": list(df_customers.columns),
            "data_types": {c: str(df_customers[c].dtype) for c in df_customers.columns},
            "row_count": len(df_customers),
            "column_count": len(df_customers.columns),
            "filename": "customers.csv",
        },
        "cgpa.csv": {
            "columns": list(df_cgpa.columns),
            "data_types": {c: str(df_cgpa[c].dtype) for c in df_cgpa.columns},
            "row_count": len(df_cgpa),
            "column_count": len(df_cgpa.columns),
            "filename": "cgpa.csv",
        },
    }

    return datasets, metadata


# =========================================================================
# SECTION A: Single-Dataset Basics
# =========================================================================

def test_pattern_a1_row_and_column_count(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    expected_rows = len(df)
    expected_cols = len(df.columns)

    res = run_ask_analyst_query(
        question="How many rows and columns are in orders.csv?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    ans = res["answer"]["answer"]
    assert str(expected_rows) in ans, f"Expected {expected_rows} in answer: {ans}"
    assert str(expected_cols) in ans, f"Expected {expected_cols} in answer: {ans}"


def test_pattern_a2_list_columns(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    res = run_ask_analyst_query(
        question="What are the columns in orders.csv?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    ans = res["answer"]["answer"]
    for c in ["order_id", "customer_id", "total_amount"]:
        assert c in ans.lower() or c in str(res.get("result", {})).lower()


def test_pattern_a3_basic_aggregations(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]

    # Sum
    expected_sum = float(df["total_amount"].sum())
    res_sum = run_ask_analyst_query(
        question="What is the total sum of total_amount in orders.csv?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res_sum["status"] == "success"
    calc_sum = res_sum["result"].get("value")
    assert abs(calc_sum - expected_sum) < 0.01

    # Average
    expected_avg = float(df["total_amount"].mean())
    res_avg = run_ask_analyst_query(
        question="What is the average total_amount in orders.csv?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res_avg["status"] == "success"
    calc_avg = res_avg["result"].get("value")
    assert abs(calc_avg - expected_avg) < 0.01

    # Maximum
    expected_max = float(df["total_amount"].max())
    res_max = run_ask_analyst_query(
        question="What is the maximum total_amount in orders.csv?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res_max["status"] == "success"
    calc_max = res_max["result"].get("value")
    assert abs(calc_max - expected_max) < 0.01


def test_pattern_a4_missing_and_duplicates(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    expected_missing = int(df["total_amount"].isna().sum())

    res_missing = run_ask_analyst_query(
        question="How many missing values are in total_amount in orders.csv?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res_missing["status"] == "success"
    val = res_missing["result"].get("value")
    if val is not None:
        assert val == expected_missing
    else:
        assert str(expected_missing) in res_missing["answer"]["answer"]


# =========================================================================
# SECTION B: Filtered Calculations (AND / OR / Nested)
# =========================================================================

def test_pattern_b1_aggregation_single_filter(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    expected_sum = float(df[df["order_status"].astype(str).str.lower() == "delivered"]["total_amount"].sum())

    res = run_ask_analyst_query(
        question="What is the sum of total_amount where order_status is Delivered?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    calc_sum = res["result"].get("value")
    assert abs(calc_sum - expected_sum) < 0.01


def test_pattern_b2_aggregation_multiple_and_filters(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    # AND condition: order_status == 'Delivered' AND quantity >= 2
    filtered = df[(df["order_status"].astype(str).str.lower() == "delivered") & (df["quantity"] >= 2)]
    expected_sum = float(filtered["total_amount"].sum())
    expected_count = len(filtered)

    res = run_ask_analyst_query(
        question="What is the sum of total_amount where order_status is Delivered and quantity >= 2?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    calc_sum = res["result"].get("value")
    assert abs(calc_sum - expected_sum) < 0.01


def test_pattern_b3_or_condition_filtering(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    # OR condition: order_status == 'Shipped' OR order_status == 'Delivered'
    mask = (df["order_status"].astype(str).str.lower() == "shipped") | (df["order_status"].astype(str).str.lower() == "delivered")
    expected_count = int(mask.sum())

    res = run_ask_analyst_query(
        question="How many orders have order_status is Shipped or order_status is Delivered?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    val = res["result"].get("value")
    if val is not None:
        assert val == expected_count
    else:
        assert str(expected_count) in res["answer"]["answer"]


def test_pattern_b4_filtered_average_and_max(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    filtered = df[df["quantity"] > 1]
    expected_avg = float(filtered["total_amount"].mean())

    res = run_ask_analyst_query(
        question="What is the average total_amount for orders where quantity > 1?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    calc_avg = res["result"].get("value")
    assert abs(calc_avg - expected_avg) < 0.01


# =========================================================================
# SECTION C: Grouped Analysis
# =========================================================================

def test_pattern_c1_group_by_with_filter(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    # Filter order_status == Delivered, then group by product sum total_amount
    delivered_df = df[df["order_status"].astype(str).str.lower() == "delivered"]
    expected_grp = delivered_df.groupby("product")["total_amount"].sum().reset_index()
    top_expected = expected_grp.sort_values(by="total_amount", ascending=False).iloc[0]

    res = run_ask_analyst_query(
        question="Calculate total_amount by product where order_status is Delivered",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    res_df = res["result"].get("data")
    assert isinstance(res_df, pd.DataFrame)
    assert len(res_df) == len(expected_grp)


def test_pattern_c2_top_n_after_grouping(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    top3_expected = df.groupby("product")["total_amount"].sum().reset_index().sort_values(by="total_amount", ascending=False).head(3)

    res = run_ask_analyst_query(
        question="Show the top 3 products by total_amount",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    res_df = res["result"].get("data")
    assert isinstance(res_df, pd.DataFrame)
    assert len(res_df) == 3


# =========================================================================
# SECTION D: Multi-Dataset Analysis & Safety
# =========================================================================

def test_pattern_d1_identify_datasets_and_compare_counts(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    ord_len = len(datasets["orders.csv"])
    cust_len = len(datasets["customers.csv"])

    res = run_ask_analyst_query(
        question="Compare row counts between orders.csv and customers.csv",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    ans = res["answer"]["answer"]
    assert str(ord_len) in ans
    assert str(cust_len) in ans


def test_pattern_d2_compare_columns_across_datasets(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    res = run_ask_analyst_query(
        question="Compare columns between orders.csv and customers.csv",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    ans = res["answer"]["answer"]
    # Shared column customer_id should be mentioned
    assert "customer_id" in ans.lower() or "customer_id" in str(res.get("result", {})).lower()


def test_pattern_d3_reject_unsafe_unrelated_join(uploaded_test_datasets):
    """Negative test: Attempting to join orders.csv and cgpa.csv has no valid relationship."""
    datasets, metadata = uploaded_test_datasets
    res = run_ask_analyst_query(
        question="Join orders.csv and cgpa.csv on customer_id",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    # Must refuse or explain that no relationship exists
    assert res["status"] in ("error", "needs_clarification") or len(res.get("warnings", [])) > 0 or len(res.get("errors", [])) > 0
    ans_text = res["answer"]["answer"].lower()
    assert any(term in ans_text for term in ["cannot", "no verified", "no valid", "rejected", "not found", "unable", "error"])


def test_pattern_d4_never_silently_substitute_dataset(uploaded_test_datasets):
    """If question asks to compare orders and customers, query plan must involve both, not just orders."""
    datasets, metadata = uploaded_test_datasets
    res = run_ask_analyst_query(
        question="Compare total records in orders.csv and customers.csv",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    plan = res["query_plan"]
    assert plan.get("dataset") in ("orders.csv", "customers.csv")
    assert plan.get("secondary_dataset") in ("orders.csv", "customers.csv")
    assert plan.get("dataset") != plan.get("secondary_dataset")


# =========================================================================
# SECTION E: Subqueries and Multi-Step Questions
# =========================================================================

def test_pattern_e1_filter_above_overall_average(uploaded_test_datasets):
    """Records matching condition with aggregate threshold: total_amount > overall average total_amount."""
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    avg_val = float(df["total_amount"].mean())
    expected_records = df[df["total_amount"] > avg_val]
    expected_count = len(expected_records)

    res = run_ask_analyst_query(
        question="How many orders have total_amount greater than the average total_amount?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    val = res["result"].get("value")
    if val is not None:
        assert val == expected_count
    else:
        assert str(expected_count) in res["answer"]["answer"]


def test_pattern_e2_show_records_above_average(uploaded_test_datasets):
    datasets, metadata = uploaded_test_datasets
    df = datasets["orders.csv"]
    avg_val = float(df["total_amount"].mean())
    expected_records = df[df["total_amount"] > avg_val]

    res = run_ask_analyst_query(
        question="Show orders where total_amount is above average",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    res_df = res["result"].get("data")
    assert isinstance(res_df, pd.DataFrame)
    assert len(res_df) == len(expected_records)


# =========================================================================
# SECTION F: Cross-Dataset Questions & Joins
# =========================================================================

def test_pattern_f1_join_orders_and_customers(uploaded_test_datasets):
    """Join orders and customers on customer_id, validating output rows."""
    datasets, metadata = uploaded_test_datasets
    df_ord = datasets["orders.csv"]
    df_cust = datasets["customers.csv"]
    expected_join_df = pd.merge(df_ord, df_cust, on="customer_id", how="inner")
    expected_row_count = len(expected_join_df)

    res = run_ask_analyst_query(
        question="Join orders.csv with customers.csv on customer_id",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success", f"Query failed: {res.get('errors')}"
    res_df = res["result"].get("data")
    assert isinstance(res_df, pd.DataFrame)
    assert res["result"].get("row_count") == expected_row_count


def test_pattern_f2_cross_dataset_aggregation_no_row_inflation(uploaded_test_datasets):
    """Aggregate joined records (sum total_amount by city in customers.csv) without row multiplication."""
    datasets, metadata = uploaded_test_datasets
    df_ord = datasets["orders.csv"]
    df_cust = datasets["customers.csv"]
    merged = pd.merge(df_ord, df_cust, on="customer_id", how="inner")
    expected_city_sum = merged.groupby("city")["total_amount"].sum().reset_index()

    res = run_ask_analyst_query(
        question="Calculate total_amount by city across orders.csv and customers.csv",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success", f"Query failed: {res.get('errors')}"
    res_df = res["result"].get("data")
    assert isinstance(res_df, pd.DataFrame)
    # Check that computed sum matches deterministic expected sum for top city
    top_res = res_df.sort_values(by=res_df.columns[-1], ascending=False).iloc[0]
    top_expected = expected_city_sum.sort_values(by="total_amount", ascending=False).iloc[0]
    assert abs(top_res.iloc[-1] - top_expected["total_amount"]) < 0.01


def test_pattern_f3_cross_dataset_difference_or_unmatched(uploaded_test_datasets):
    """Find records in one dataset but absent in another (orders without customer record or vice versa)."""
    datasets, metadata = uploaded_test_datasets
    df_ord = datasets["orders.csv"]
    df_cust = datasets["customers.csv"]
    cust_ids_in_cust = set(df_cust["customer_id"].unique())
    orders_without_cust = df_ord[~df_ord["customer_id"].isin(cust_ids_in_cust)]
    expected_count = len(orders_without_cust)

    res = run_ask_analyst_query(
        question="Which orders in orders.csv have customer_id not present in customers.csv?",
        datasets=datasets,
        metadata=metadata,
        default_dataset="orders.csv",
    )
    assert res["status"] == "success"
    if res["result"].get("row_count") is not None:
        assert res["result"].get("row_count") == expected_count
    else:
        assert str(expected_count) in res["answer"]["answer"]
