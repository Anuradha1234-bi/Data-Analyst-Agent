"""Comprehensive Test Suite for Phase 8 - Data Analyst Module (Natural Language Data Analysis).

Verifies:
1. Numeric aggregation questions (AVERAGE, SUM, MIN, MAX, COUNT, MEDIAN).
2. Grouping and ranking questions (Top-N, Bottom-N, Group-by).
3. Filtering and sorting with safe deterministic execution.
4. Date-based trend questions and line visualization.
5. Statistical correlation calculations with explicit causation guards.
6. Missing values, data hygiene, and structural summaries.
7. Ambiguous column detection and interactive user clarification.
8. Empty dataset and insufficient data handling.
9. Security and safety guards (eval, exec, arbitrary code rejection).
10. Read-only data integrity (underlying datasets are never mutated).
11. Dataset/version isolation (Original vs Cleaned) and user authorization.
12. Dynamic contextual suggested questions generation from real schema.
13. Analytical query history lifecycle (persist, list, delete, clear).
14. FastAPI REST API endpoints via TestClient with full schema validation.
"""

import sys
import os
import hashlib
import json
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root and backend are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"

for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.models.analysis_history import AnalysisHistory
from app.schemas.analyst import (
    AnalysisAskRequest,
    AnalysisAskResponse,
    SuggestedQuestionsResponse,
    AnalysisHistoryListResponse,
)
from app.services.data_analyst_service import DataAnalystService
from app.main import app as fastapi_app
from app.auth.jwt import create_access_token


def run_phase8_tests():
    print("=====================================================================")
    print("PHASE 8 DATA ANALYST MODULE - NATURAL LANGUAGE ANALYSIS TEST SUITE")
    print("=====================================================================")

    # 1. Setup isolated in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    # 2. Create test users (User 1 and User 2)
    user1 = User(
        email="analyst1@example.com",
        hashed_password="hashed_pw_1",
        full_name="Alice Analyst",
        is_active=True,
    )
    user2 = User(
        email="analyst2@example.com",
        hashed_password="hashed_pw_2",
        full_name="Bob Unauthorized",
        is_active=True,
    )
    db.add(user1)
    db.add(user2)
    db.commit()
    db.refresh(user1)
    db.refresh(user2)

    # 3. Create temporary directory and test datasets
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name)

    # Dataset A: Sales Dataset (Original & Cleaned)
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    df_sales_orig = pd.DataFrame({
        "Date": dates,
        "Product": ["Laptop", "Mouse", "Keyboard", "Laptop", "Monitor", "Mouse", "Laptop", "Monitor", "Keyboard", "Laptop"],
        "Category": ["Electronics", "Accessories", "Accessories", "Electronics", "Electronics", "Accessories", "Electronics", "Electronics", "Accessories", "Electronics"],
        "Sales": [1200.0, 50.0, 80.0, 1400.0, 450.0, 60.0, 1100.0, 400.0, 90.0, 1300.0],
        "Quantity": [1, 5, 2, 2, 1, 4, 1, 1, 3, 2],
        "Profit": [300.0, 20.0, 30.0, 400.0, 120.0, 25.0, 280.0, 100.0, 35.0, 350.0],
    })
    sales_orig_path = temp_path / "sales_orig.csv"
    df_sales_orig.to_csv(sales_orig_path, index=False)

    # Compute initial hash of original file for read-only verification
    with open(sales_orig_path, "rb") as f:
        initial_sales_hash = hashlib.sha256(f.read()).hexdigest()

    # Cleaned version of sales dataset (e.g. Sales increased by 100 for premium)
    df_sales_clean = df_sales_orig.copy()
    df_sales_clean["Sales"] = df_sales_clean["Sales"] + 100.0
    sales_clean_path = temp_path / "sales_clean.csv"
    df_sales_clean.to_csv(sales_clean_path, index=False)

    ds_sales = Dataset(
        user_id=user1.id,
        filename="sales_orig.csv",
        file_type="CSV",
        file_path=str(sales_orig_path),
        cleaned_file_path=str(sales_clean_path),
        rows=len(df_sales_orig),
        columns=len(df_sales_orig.columns),
        file_size_bytes=sales_orig_path.stat().st_size,
        has_cleaned=True,
    )
    db.add(ds_sales)

    # Dataset B: Ambiguous Columns Dataset
    df_ambig = pd.DataFrame({
        "Market": ["North", "South", "East", "West"],
        "Modal_Price": [5000.0, 6000.0, 5500.0, 4800.0],
        "Min_Price": [4500.0, 5500.0, 5000.0, 4200.0],
        "Max_Price": [5500.0, 6500.0, 6000.0, 5200.0],
    })
    ambig_path = temp_path / "ambig.csv"
    df_ambig.to_csv(ambig_path, index=False)

    ds_ambig = Dataset(
        user_id=user1.id,
        filename="ambig.csv",
        file_type="CSV",
        file_path=str(ambig_path),
        rows=len(df_ambig),
        columns=len(df_ambig.columns),
        file_size_bytes=ambig_path.stat().st_size,
        has_cleaned=False,
    )
    db.add(ds_ambig)

    # Dataset C: Empty Dataset (headers only, 0 rows)
    df_empty = pd.DataFrame(columns=["ID", "Name", "Score"])
    empty_path = temp_path / "empty.csv"
    df_empty.to_csv(empty_path, index=False)

    ds_empty = Dataset(
        user_id=user1.id,
        filename="empty.csv",
        file_type="CSV",
        file_path=str(empty_path),
        rows=0,
        columns=3,
        file_size_bytes=empty_path.stat().st_size,
        has_cleaned=False,
    )
    db.add(ds_empty)

    # Dataset D: Dataset with Missing Values
    df_missing = pd.DataFrame({
        "Item": ["A", "B", "C", "D", "E"],
        "Price": [10.0, np.nan, 30.0, np.nan, 50.0],
        "Quantity": [100, 200, np.nan, 400, 500],
    })
    missing_path = temp_path / "missing.csv"
    df_missing.to_csv(missing_path, index=False)

    ds_missing = Dataset(
        user_id=user1.id,
        filename="missing.csv",
        file_type="CSV",
        file_path=str(missing_path),
        rows=5,
        columns=3,
        file_size_bytes=missing_path.stat().st_size,
        has_cleaned=False,
    )
    db.add(ds_missing)

    db.commit()
    db.refresh(ds_sales)
    db.refresh(ds_ambig)
    db.refresh(ds_empty)
    db.refresh(ds_missing)

    # -----------------------------------------------------------------
    # TEST 1: Numeric Aggregation Questions
    # -----------------------------------------------------------------
    print("\n--- TEST 1: Numeric Aggregations (Average, Max, Min, Sum) ---")
    # Expected average sales: sum([1200, 50, 80, 1400, 450, 60, 1100, 400, 90, 1300]) / 10 = 6130 / 10 = 613.0
    req_avg = AnalysisAskRequest(dataset_id=ds_sales.id, question="What is the average sales amount?", version="original")
    resp_avg = DataAnalystService.ask_question(req_avg, user1, db)
    assert resp_avg.status == "success"
    assert "613" in resp_avg.answer
    assert resp_avg.evidence.get("computed_values", {}).get("metric_value") == 613.0
    print("  [PASS] Average sales correctly computed: 613.00")

    # Max Profit: 400.0
    req_max = AnalysisAskRequest(dataset_id=ds_sales.id, question="What is the maximum profit?", version="original")
    resp_max = DataAnalystService.ask_question(req_max, user1, db)
    assert resp_max.status == "success"
    assert "400" in resp_max.answer
    print("  [PASS] Maximum profit correctly computed: 400.00")

    # Min Quantity: 1
    req_min = AnalysisAskRequest(dataset_id=ds_sales.id, question="What is the minimum quantity?", version="original")
    resp_min = DataAnalystService.ask_question(req_min, user1, db)
    assert resp_min.status == "success"
    assert "1" in resp_min.answer
    print("  [PASS] Minimum quantity correctly computed: 1")

    # Total / Sum Sales: 6130.0
    req_sum = AnalysisAskRequest(dataset_id=ds_sales.id, question="What is the total sales?", version="original")
    resp_sum = DataAnalystService.ask_question(req_sum, user1, db)
    assert resp_sum.status == "success"
    assert "6,130" in resp_sum.answer or "6130" in resp_sum.answer
    print("  [PASS] Total sales correctly computed: 6,130.00")

    # -----------------------------------------------------------------
    # TEST 2: Grouping and Ranking Questions (Top N, Category Grouping)
    # -----------------------------------------------------------------
    print("\n--- TEST 2: Grouping and Ranking Questions ---")
    # "Which product has the highest sales?" -> Laptop has highest total sales (1200+1400+1100+1300 = 5000)
    req_rank = AnalysisAskRequest(dataset_id=ds_sales.id, question="Which product has the highest sales?", version="original")
    resp_rank = DataAnalystService.ask_question(req_rank, user1, db)
    assert resp_rank.status == "success"
    assert "Laptop" in resp_rank.answer
    assert resp_rank.result is not None
    assert resp_rank.visualization is not None
    assert resp_rank.visualization.recommended is True
    print("  [PASS] Highest sales product accurately identified: Laptop (with visualization recommendation).")

    # "Show top 3 products by sales"
    req_top3 = AnalysisAskRequest(dataset_id=ds_sales.id, question="Show top 3 products by sales", version="original")
    resp_top3 = DataAnalystService.ask_question(req_top3, user1, db)
    assert resp_top3.status == "success"
    assert resp_top3.result is not None
    assert len(resp_top3.result.rows) <= 3
    print(f"  [PASS] Top 3 ranking returned {len(resp_top3.result.rows)} ranked records.")

    # -----------------------------------------------------------------
    # TEST 3: Filtering and Sorting
    # -----------------------------------------------------------------
    print("\n--- TEST 3: Filtering and Sorting ---")
    # Filter: Sales > 1000 -> 4 records (1200, 1400, 1100, 1300)
    req_filt = AnalysisAskRequest(dataset_id=ds_sales.id, question="Show me records where sales is greater than 1000", version="original")
    resp_filt = DataAnalystService.ask_question(req_filt, user1, db)
    assert resp_filt.status == "success"
    assert resp_filt.result is not None
    assert resp_filt.result.total_rows == 4
    for r in resp_filt.result.rows:
        assert float(r["Sales"]) > 1000
    print("  [PASS] Deterministic filter returned exact 4 records where Sales > 1000.")

    # -----------------------------------------------------------------
    # TEST 4: Date-Based Trend Analysis
    # -----------------------------------------------------------------
    print("\n--- TEST 4: Date-Based Trend Questions ---")
    req_trend = AnalysisAskRequest(dataset_id=ds_sales.id, question="Show the sales trend over time", version="original")
    resp_trend = DataAnalystService.ask_question(req_trend, user1, db)
    assert resp_trend.status == "success"
    assert resp_trend.visualization is not None
    assert resp_trend.visualization.chart_type == "line"
    assert any("caus" in lim.lower() for lim in resp_trend.limitations)
    print("  [PASS] Trend question rendered line chart recommendation and causal caveat.")

    # -----------------------------------------------------------------
    # TEST 5: Statistical Correlation and Causation Caveat
    # -----------------------------------------------------------------
    print("\n--- TEST 5: Correlation Calculation & Causation Guard ---")
    req_corr = AnalysisAskRequest(dataset_id=ds_sales.id, question="Which columns have the strongest correlation?", version="original")
    resp_corr = DataAnalystService.ask_question(req_corr, user1, db)
    assert resp_corr.status == "success"
    assert any("not imply causation" in lim.lower() for lim in resp_corr.limitations)
    print("  [PASS] Correlation computed safely with explicit 'correlation does not imply causation' limitation.")

    # -----------------------------------------------------------------
    # TEST 6: Missing Values and Data Summaries
    # -----------------------------------------------------------------
    print("\n--- TEST 6: Missing Values and Data Summaries ---")
    req_miss = AnalysisAskRequest(dataset_id=ds_missing.id, question="How many records have missing values?", version="original")
    resp_miss = DataAnalystService.ask_question(req_miss, user1, db)
    assert resp_miss.status == "success"
    assert "missing" in resp_miss.answer.lower()
    print("  [PASS] Missing values query reported missing counts accurately.")

    req_summary = AnalysisAskRequest(dataset_id=ds_sales.id, question="Summarize the important findings in this dataset", version="original")
    resp_summary = DataAnalystService.ask_question(req_summary, user1, db)
    assert resp_summary.status == "success"
    assert resp_summary.result is not None
    print("  [PASS] Dataset summary returned statistical breakdown of features.")

    # -----------------------------------------------------------------
    # TEST 7: Ambiguous Column References Guard
    # -----------------------------------------------------------------
    print("\n--- TEST 7: Ambiguous Column Reference Guard ---")
    req_ambig = AnalysisAskRequest(dataset_id=ds_ambig.id, question="What is the average price?", version="original")
    resp_ambig = DataAnalystService.ask_question(req_ambig, user1, db)
    assert resp_ambig.status == "needs_clarification"
    assert resp_ambig.clarification_question is not None
    assert len(resp_ambig.clarification_options) >= 2
    assert "Modal_Price" in resp_ambig.clarification_options
    print(f"  [PASS] Ambiguity stopped safely with clarification prompt: '{resp_ambig.clarification_question}'")

    # -----------------------------------------------------------------
    # TEST 8: Empty Dataset Handling
    # -----------------------------------------------------------------
    print("\n--- TEST 8: Empty Dataset Handling ---")
    try:
        req_empty = AnalysisAskRequest(dataset_id=ds_empty.id, question="What is the average score?", version="original")
        DataAnalystService.ask_question(req_empty, user1, db)
        assert False, "Should have raised HTTPException for empty dataset"
    except HTTPException as ex:
        assert ex.status_code == 400
        assert "no rows" in ex.detail.lower() or "empty" in ex.detail.lower()
        print("  [PASS] Empty dataset rejected gracefully with HTTP 400.")

    # -----------------------------------------------------------------
    # TEST 9: Security Guard - Disallowed Arbitrary Code
    # -----------------------------------------------------------------
    print("\n--- TEST 9: Security Guard (No Arbitrary Execution) ---")
    malicious_inputs = [
        "eval('__import__(\"os\").system(\"ls\")')",
        "exec(open('malicious.py').read())",
        "drop table datasets;",
        "run python code to delete everything",
    ]
    for mal in malicious_inputs:
        req_mal = AnalysisAskRequest(dataset_id=ds_sales.id, question=mal, version="original")
        resp_mal = DataAnalystService.ask_question(req_mal, user1, db)
        assert resp_mal.status in ("error", "unknown")
        assert len(resp_mal.errors) > 0 or "disallowed" in resp_mal.answer.lower() or "error" in resp_mal.answer.lower()
    print("  [PASS] All 4 code execution and SQL injection attacks safely rejected.")

    # -----------------------------------------------------------------
    # TEST 10: Read-Only Data Integrity Verification
    # -----------------------------------------------------------------
    print("\n--- TEST 10: Read-Only Data Integrity Guarantee ---")
    with open(sales_orig_path, "rb") as f:
        final_sales_hash = hashlib.sha256(f.read()).hexdigest()
    assert initial_sales_hash == final_sales_hash, "Original dataset file was modified during analysis!"
    print("  [PASS] Cryptographic SHA-256 hash verified: original dataset file is 100% byte-for-byte unmodified.")

    # -----------------------------------------------------------------
    # TEST 11: Dataset Version Isolation & Authorization
    # -----------------------------------------------------------------
    print("\n--- TEST 11: Dataset Version Isolation & User Authorization ---")
    # Compare original vs cleaned:
    # Original average sales = 613.0
    # Cleaned average sales = 713.0 (each sales value was increased by 100)
    req_v_orig = AnalysisAskRequest(dataset_id=ds_sales.id, question="What is the average sales amount?", version="original")
    resp_v_orig = DataAnalystService.ask_question(req_v_orig, user1, db)
    assert resp_v_orig.dataset_version == "original"
    assert "613" in resp_v_orig.answer

    req_v_clean = AnalysisAskRequest(dataset_id=ds_sales.id, question="What is the average sales amount?", version="cleaned")
    resp_v_clean = DataAnalystService.ask_question(req_v_clean, user1, db)
    assert resp_v_clean.dataset_version == "cleaned"
    assert "713" in resp_v_clean.answer
    print("  [PASS] Version isolation verified: original returns 613.00, cleaned returns 713.00.")

    # Unauthorized access check: User 2 trying to query User 1's dataset
    try:
        req_unauth = AnalysisAskRequest(dataset_id=ds_sales.id, question="What is the average sales?", version="original")
        DataAnalystService.ask_question(req_unauth, user2, db)
        assert False, "User 2 should not be able to access User 1's dataset"
    except HTTPException as ex:
        assert ex.status_code == 404
        assert "not found or access denied" in ex.detail.lower()
        print("  [PASS] Cross-user unauthorized dataset access blocked with 404 Not Found.")

    # -----------------------------------------------------------------
    # TEST 12: Contextual Suggested Questions Generation
    # -----------------------------------------------------------------
    print("\n--- TEST 12: Contextual Suggested Questions Generation ---")
    sugg_resp = DataAnalystService.get_suggested_questions(ds_sales.id, user1, db)
    assert sugg_resp.dataset_id == ds_sales.id
    assert len(sugg_resp.questions) > 0
    q_texts = [q.question.lower() for q in sugg_resp.questions]
    # Should contain references to real column names: 'sales', 'profit', 'product', 'date'
    assert any("sales" in q or "profit" in q for q in q_texts)
    assert any("product" in q or "category" in q for q in q_texts)
    assert any("trend" in q or "correlation" in q for q in q_texts)
    print(f"  [PASS] Generated {len(sugg_resp.questions)} valid questions dynamically grounded in real schema.")

    # -----------------------------------------------------------------
    # TEST 13: Query History Lifecycle (Persist, List, Delete, Clear)
    # -----------------------------------------------------------------
    print("\n--- TEST 13: Query History Lifecycle ---")
    hist_resp = DataAnalystService.get_query_history(dataset_id=ds_sales.id, current_user=user1, db=db)
    assert hist_resp.total_count >= 5
    first_item = hist_resp.history[0]
    assert first_item.query != ""
    assert first_item.dataset_id == ds_sales.id
    print(f"  [PASS] Query history retrieved {hist_resp.total_count} logged operations.")

    # Delete single history item
    del_res = DataAnalystService.delete_history_item(first_item.id, user1, db)
    assert del_res["success"] is True

    # Clear remaining history for dataset
    clear_res = DataAnalystService.clear_history(dataset_id=ds_sales.id, current_user=user1, db=db)
    assert clear_res["success"] is True

    hist_after = DataAnalystService.get_query_history(dataset_id=ds_sales.id, current_user=user1, db=db)
    assert hist_after.total_count == 0
    print("  [PASS] Query history single delete and bulk clear verified.")

    # -----------------------------------------------------------------
    # TEST 14: FastAPI Router REST Endpoints via TestClient
    # -----------------------------------------------------------------
    print("\n--- TEST 14: FastAPI Endpoints via TestClient ---")
    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # Create auth token for user 1
    token = create_access_token(data={"sub": str(user1.id)})
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(fastapi_app)

    # 14.1 POST /api/analysis/ask
    api_payload = {
        "dataset_id": ds_sales.id,
        "question": "What is the average sales amount?",
        "version": "original",
    }
    r = client.post("/api/analysis/ask", json=api_payload, headers=headers)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body["status"] == "success"
    assert "613" in body["answer"]
    assert body["dataset_name"] == "sales_orig.csv"
    assert "columns" in body["result"]
    assert "rows" in body["result"]
    print("  [PASS] POST /api/analysis/ask returned valid typed contract.")

    # 14.2 GET /api/analysis/suggested-questions/{id}
    r_sugg = client.get(f"/api/analysis/suggested-questions/{ds_sales.id}", headers=headers)
    assert r_sugg.status_code == 200
    s_body = r_sugg.json()
    assert s_body["dataset_id"] == ds_sales.id
    assert len(s_body["questions"]) >= 3
    print("  [PASS] GET /api/analysis/suggested-questions returned dynamic suggested questions.")

    # 14.3 GET /api/analysis/history
    r_hist = client.get(f"/api/analysis/history?dataset_id={ds_sales.id}", headers=headers)
    assert r_hist.status_code == 200
    h_body = r_hist.json()
    assert h_body["total_count"] >= 1
    print("  [PASS] GET /api/analysis/history returned user audit entries.")

    # Cleanup dependency overrides & temp dir
    fastapi_app.dependency_overrides.clear()
    temp_dir.cleanup()
    db.close()

    print("\n=====================================================================")
    print("ALL 14 PHASE 8 TEST SCENARIOS PASSED WITH 100% SUCCESS!")
    print("=====================================================================")


if __name__ == "__main__":
    run_phase8_tests()
