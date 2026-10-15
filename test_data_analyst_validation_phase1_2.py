"""Regression Test Suite for Phase 1 (Strict Column Validation) & Phase 2 (Metadata-Aware Selection).

Validates:
1. Missing-column questions return schema-aware limitations listing available columns.
2. Prevention of 'The mean None is ...' and fabricated student/marks/attendance statistics.
3. Metadata-only datasets do not receive automatic domain correlation results.
4. Explicit valid requests for metadata columns (e.g. PDF_Page) remain supported.
5. False fuzzy matching for ordinary words ('flagged', 'failed') is eliminated.
6. Existing valid workflows (CGPA/Package correlation, orders/product/total_amount) are fully preserved.
7. Suggested questions exclude technical extraction metadata from statistical prompts.
"""

import os
import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
backend_path = PROJECT_ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from query.column_resolver import resolve_column, is_metadata_column, filter_metadata_columns
from query.orchestrator import run_ask_analyst_query
from query.query_planner import build_query_plan
from query.query_validator import validate_query_plan
from query.correlation_query_engine import compute_correlation_query
from query.aggregation_engine import compute_aggregation

# Datasets Fixtures
LEDGER_CSV = PROJECT_ROOT / "uploads" / "user_20" / "ed2904653a1144169cb88f21665e921c_ledger_sem6_extracted.csv"
CGPA_CSV = PROJECT_ROOT / "uploads" / "user_14" / "d27813f65c604efa8c65f221678caafa_cgpa.csv"
ORDERS_CSV = PROJECT_ROOT / "uploads" / "user_14" / "d8c9e8e095e24d5283df02eafe6fe6a0_orders__1_.csv"


def get_ledger_data():
    if LEDGER_CSV.exists():
        df = pd.read_csv(LEDGER_CSV, nrows=2000)
    else:
        df = pd.DataFrame({
            "PDF_Page": [1, 1, 2, 2, 3],
            "Line_Number": [10, 20, 10, 30, 15],
            "Extracted_Text": ["Theory Marks", "Grade A", "Passed", "Total 450", "Remark"],
        })
    meta = {
        "ledger_sem6_extracted.csv": {
            "column_names": list(df.columns),
            "data_types": {c: str(df[c].dtype) for c in df.columns},
            "rows": len(df),
            "columns": len(df.columns),
        }
    }
    return df, meta


def get_cgpa_data():
    if CGPA_CSV.exists():
        df = pd.read_csv(CGPA_CSV)
    else:
        df = pd.DataFrame({
            "Name": ["Alice", "Bob", "Charlie", "David"],
            "Year": [2021, 2021, 2022, 2022],
            "CGPA": [8.5, 9.2, 7.8, 8.9],
            "Package": [12.0, 18.0, 8.5, 15.0],
        })
    meta = {
        "cgpa.csv": {
            "column_names": list(df.columns),
            "data_types": {c: str(df[c].dtype) for c in df.columns},
            "rows": len(df),
            "columns": len(df.columns),
        }
    }
    return df, meta


def get_orders_data():
    if ORDERS_CSV.exists():
        df = pd.read_csv(ORDERS_CSV)
    else:
        df = pd.DataFrame({
            "order_id": [1, 2, 3],
            "customer_id": [101, 102, 103],
            "order_date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "product": ["Mechanical Keyboard", "Wireless Mouse", "USB-C Hub"],
            "quantity": [2, 1, 3],
            "unit_price": [2499.0, 899.0, 1299.0],
            "order_status": ["Completed", "Completed", "Pending"],
            "total_amount": [4998.0, 899.0, 3897.0],
        })
    meta = {
        "orders (1).csv": {
            "column_names": list(df.columns),
            "data_types": {c: str(df[c].dtype) for c in df.columns},
            "rows": len(df),
            "columns": len(df.columns),
        }
    }
    return df, meta


def test_phase1_missing_columns_in_academic_dataset():
    """Phase 1: Question with missing requested columns returns schema-aware limitation."""
    df, meta = get_ledger_data()
    q = "What is the correlation between marks and attendance?"
    resp = run_ask_analyst_query(q, {"ledger_sem6_extracted.csv": df}, meta)

    # Must NOT succeed in computing correlation on PDF_Page or Line_Number
    assert resp["status"] == "error", f"Expected error for missing columns, got {resp['status']}"
    ans = resp["answer"]["answer"]
    assert "marks" in ans.lower() or "attendance" in ans.lower()
    assert "available columns" in ans.lower() or "not exist" in ans.lower()
    assert "PDF_Page" not in ans or "available columns" in ans.lower()
    # Confirm no fabricated correlation
    assert "0.44" not in ans
    print("\n[PASS] Test 1: Missing columns in academic dataset rejected with schema limitation.")


def test_phase1_prevent_mean_none_output():
    """Phase 1: Aggregation on missing column never outputs 'The mean None is ...' or Year mean."""
    df, meta = get_cgpa_data()
    q = "What is the average attendance by department?"
    resp = run_ask_analyst_query(q, {"cgpa.csv": df}, meta)

    assert resp["status"] == "error"
    ans = resp["answer"]["answer"]
    assert "mean none" not in ans.lower()
    assert "2021" not in ans  # Must not compute mean of Year
    assert "attendance" in ans.lower() or "department" in ans.lower()
    assert "available columns" in ans.lower()
    print("[PASS] Test 2: 'The mean None is ...' and fabricated Year statistics prevented.")


def test_phase2_metadata_helpers():
    """Phase 2: Metadata classification correctly identifies technical/extraction fields."""
    assert is_metadata_column("PDF_Page") is True
    assert is_metadata_column("Line_Number") is True
    assert is_metadata_column("page_no") is True
    assert is_metadata_column("row_id") is True
    assert is_metadata_column("Unnamed: 0") is True
    assert is_metadata_column("bbox") is True
    assert is_metadata_column("offset") is True

    # Domain metrics must NOT be flagged as metadata
    assert is_metadata_column("CGPA") is False
    assert is_metadata_column("Package") is False
    assert is_metadata_column("unit_price") is False
    assert is_metadata_column("total_amount") is False
    assert is_metadata_column("quantity") is False
    assert is_metadata_column("Modal_Price") is False

    cols = ["PDF_Page", "Line_Number", "CGPA", "Package"]
    assert filter_metadata_columns(cols) == ["CGPA", "Package"]
    print("[PASS] Test 3: Metadata classification helpers verified.")


def test_phase2_prevent_metadata_only_automatic_correlation():
    """Phase 2: Metadata-only dataset receives clear notice when automatic correlation is requested."""
    df, meta = get_ledger_data()
    q = "Which numerical columns have the strongest correlation?"
    resp = run_ask_analyst_query(q, {"ledger_sem6_extracted.csv": df}, meta)

    # Automatic correlation must not return PDF_Page vs Line_Number as a domain correlation
    ans = resp["answer"]["answer"]
    assert "extraction metadata" in ans.lower() or "insufficient" in ans.lower() or resp["status"] != "success" or len(resp.get("result", {}).get("data", [])) == 0
    print("[PASS] Test 4: Automatic correlation on metadata-only dataset prevented.")


def test_phase2_explicit_metadata_column_request_allowed():
    """Phase 2: User explicitly asking for PDF_Page and Line_Number is honored."""
    df, meta = get_ledger_data()
    q = "What is the correlation between PDF_Page and Line_Number?"
    resp = run_ask_analyst_query(q, {"ledger_sem6_extracted.csv": df}, meta)

    assert resp["status"] == "success", f"Explicit metadata correlation failed: {resp}"
    ans = resp["answer"]["answer"]
    assert "PDF_Page" in ans
    assert "Line_Number" in ans
    assert "correlation" in ans.lower()
    print(f"[PASS] Test 5: Explicit metadata column correlation honored: {ans}")


def test_phase2_fuzzy_matching_stopwords_protection():
    """Phase 2: Ordinary words like 'flagged' or 'failed' do NOT resolve to 'PDF_Page'."""
    df, meta = get_ledger_data()
    ds_meta = meta["ledger_sem6_extracted.csv"]

    res_flagged = resolve_column("flagged", ds_meta)
    assert res_flagged["resolved"] is False, f"Expected 'flagged' NOT to resolve, got {res_flagged}"

    res_failed = resolve_column("failed", ds_meta)
    assert res_failed["resolved"] is False, f"Expected 'failed' NOT to resolve, got {res_failed}"

    res_case = resolve_column("case", ds_meta)
    assert res_case["resolved"] is False, f"Expected 'case' NOT to resolve, got {res_case}"

    # Plan with complex question containing 'flagged case' and 'failed subjects'
    q = "identify students who may be at academic risk based on low marks, failed subjects, or low sgpa. explain the criteria and provide evidence for each flagged case"
    plan = build_query_plan(q, meta)
    # Must NOT have PDF_Page in group_by or column
    assert plan["column"] != "PDF_Page", "Plan falsely assigned PDF_Page as measure column!"
    assert "PDF_Page" not in plan["group_by"], "Plan falsely assigned PDF_Page to group_by!"
    print("[PASS] Test 6: Fuzzy matching stopwords protection verified ('flagged' and 'failed' rejected).")


def test_preserve_cgpa_package_correlation():
    """Preservation check: Valid CGPA/Package correlation remains fully functional."""
    df, meta = get_cgpa_data()
    q = "What is the correlation between CGPA and Package?"
    resp = run_ask_analyst_query(q, {"cgpa.csv": df}, meta)

    assert resp["status"] == "success"
    ans = resp["answer"]["answer"]
    assert "CGPA" in ans and "Package" in ans
    assert "+0.98" in ans or "0.98" in ans or "Strong" in ans
    print(f"[PASS] Test 7: Valid CGPA/Package correlation preserved: {ans}")


def test_preserve_orders_product_total_amount():
    """Preservation check: Valid orders/product/total_amount query remains fully functional."""
    df, meta = get_orders_data()
    q = "Which product generates the highest total amount?"
    resp = run_ask_analyst_query(q, {"orders (1).csv": df}, meta)

    assert resp["status"] == "success"
    ans = resp["answer"]["answer"]
    assert "Mechanical Keyboard" in ans
    assert "4998" in ans or "4,998" in ans
    print(f"[PASS] Test 8: Valid orders product query preserved: {ans}")


def test_aggregation_engine_no_silent_fallback():
    """Phase 1: Aggregation engine returns empty/error result when column is missing."""
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    res = compute_aggregation(df, column=None, aggregation="mean")
    assert res["result_type"] == "empty"
    assert res["data"] is None
    assert any("Cannot compute" in w for w in res["warnings"])
    print("[PASS] Test 9: Aggregation engine rejects column=None safely without falling back to 'A'.")


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING PHASE 1 & 2 REGRESSION TEST SUITE")
    print("=" * 70)
    test_phase1_missing_columns_in_academic_dataset()
    test_phase1_prevent_mean_none_output()
    test_phase2_metadata_helpers()
    test_phase2_prevent_metadata_only_automatic_correlation()
    test_phase2_explicit_metadata_column_request_allowed()
    test_phase2_fuzzy_matching_stopwords_protection()
    test_preserve_cgpa_package_correlation()
    test_preserve_orders_product_total_amount()
    test_aggregation_engine_no_silent_fallback()
    print("\n" + "=" * 70)
    print("ALL 9 REGRESSION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)
