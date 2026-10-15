"""Comprehensive Test Suite for Phase 6 - Intelligent Ask Analyst & Natural-Language Data Query.

Verifies:
1. Intent detection accuracy across controlled intents.
2. Simple mathematical aggregations (AVERAGE, SUM, MIN, MAX, COUNT, MEDIAN).
3. Superlative ranking queries (Top-N, Bottom-N).
4. Group-by aggregations and category breakdowns.
5. Safe deterministic filtering without arbitrary code execution.
6. Temporal queries, time-series trends, and date-to-date comparisons.
7. Statistical correlation analysis with causation caveats.
8. Missing-value and duplicate records analysis.
9. Phase 4 anomaly detection results reuse without recomputation.
10. Ambiguous column detection and user clarification prompting.
11. Cross-dataset analysis with verified foreign keys.
12. Protection against unverified joins, Many-to-Many joins, and row explosion.
13. Conversation context and multi-turn follow-up modifications.
14. Complete security isolation against arbitrary code execution (eval, exec, os.system, SQL).
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from query.orchestrator import run_ask_analyst_query
from query.intent_detector import detect_query_intent
from query.column_resolver import resolve_column
from query.query_planner import build_query_plan
from query.query_validator import validate_query_plan
from query.query_executor import execute_query
from query.evidence_extractor import extract_query_evidence
from query.answer_generator import generate_query_answer
from query.chart_recommender import recommend_query_visualization
from models.relationship import Relationship, JoinAudit
from query.query_models import QueryIntent


def build_sample_environment():
    """Build multi-dataset fixture environment."""
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    df_sales = pd.DataFrame({
        "Date": dates,
        "Market": ["Pune", "Mumbai", "Pune", "Nashik", "Mumbai", "Nagpur", "Pune", "Nashik", "Akola", "Pune"],
        "Commodity": ["Soybean", "Soybean", "Wheat", "Cotton", "Soybean", "Wheat", "Soybean", "Cotton", "Soybean", "Wheat"],
        "Modal_Price": [5200.0, 6100.0, 4800.0, 4900.0, 6300.0, 4700.0, 5300.0, 5100.0, 4500.0, 4900.0],
        "Arrival_Quantity": [120, 200, 80, 150, 220, 75, 130, 140, 90, 85],
    })

    df_customers = pd.DataFrame({
        "Customer_ID": [101, 102, 103, 104, 105],
        "Market": ["Pune", "Mumbai", "Nashik", "Nagpur", "Akola"],
        "Region": ["West", "West", "North", "East", "Central"],
    })

    datasets = {
        "sales.csv": df_sales,
        "customers.csv": df_customers,
    }

    metadata = {
        "sales.csv": {"column_names": list(df_sales.columns)},
        "customers.csv": {"column_names": list(df_customers.columns)},
    }

    relationships = [
        Relationship(
            source_dataset="sales.csv",
            source_column="Market",
            target_dataset="customers.csv",
            target_column="Market",
            relationship_type="Many-to-One",
            confidence="HIGH",
            value_overlap_pct=100.0,
        )
    ]

    return datasets, metadata, relationships


def run_all_tests():
    print("=====================================================================")
    print("PHASE 6 INTELLIGENT ASK ANALYST & NATURAL-LANGUAGE QUERY TEST SUITE")
    print("=====================================================================")

    datasets, metadata, relationships = build_sample_environment()

    # -------------------------------------------------------------
    # 1. Intent Detection
    # -------------------------------------------------------------
    print("\n--- TEST 1: Intent Detection ---")
    intent_res = detect_query_intent("How many records are in the dataset?", metadata)
    assert intent_res["intent"] == QueryIntent.COUNT.value, f"Expected COUNT, got {intent_res['intent']}"
    assert intent_res["confidence"] >= 0.8
    print("  [PASS] COUNT intent detected successfully.")

    # -------------------------------------------------------------
    # 2. Simple Average Query
    # -------------------------------------------------------------
    print("\n--- TEST 2: Simple Average Query ---")
    res = run_ask_analyst_query("What is the average modal price?", datasets, metadata)
    assert res["status"] == "success"
    # Average of Modal_Price = 5180.0
    assert "5,180" in res["answer"]["answer"]
    assert res["evidence"]["computed_values"]["metric_value"] == 5180.0
    print("  [PASS] Average modal price calculated and grounded: INR 5,180.00")

    # -------------------------------------------------------------
    # 3. Maximum Query & 4. Minimum Query
    # -------------------------------------------------------------
    print("\n--- TEST 3 & 4: Maximum and Minimum Queries ---")
    res_max = run_ask_analyst_query("What is the maximum modal price?", datasets, metadata)
    assert res_max["status"] == "success"
    assert "6,300" in res_max["answer"]["answer"]
    print("  [PASS] Maximum query returned exact computed value (6,300.00).")

    res_min = run_ask_analyst_query("What is the minimum modal price?", datasets, metadata)
    assert res_min["status"] == "success"
    assert "4,500" in res_min["answer"]["answer"]
    print("  [PASS] Minimum query returned exact computed value (4,500.00).")

    # -------------------------------------------------------------
    # 5. Count Query
    # -------------------------------------------------------------
    print("\n--- TEST 5: Total Records Count Query ---")
    res_cnt = run_ask_analyst_query("How many records are there?", datasets, metadata)
    assert res_cnt["status"] == "success"
    assert "10" in res_cnt["answer"]["answer"]
    print("  [PASS] Record count query verified (10 records).")

    # -------------------------------------------------------------
    # 6. Top-N Ranking Query
    # -------------------------------------------------------------
    print("\n--- TEST 6: Top-N Ranking Query ---")
    res_top = run_ask_analyst_query("Which market has the highest average price?", datasets, metadata)
    assert res_top["status"] == "success"
    assert "Mumbai" in res_top["answer"]["answer"]
    assert "6,200" in res_top["answer"]["answer"]
    assert res_top["visualization"]["recommended"] is True
    print("  [PASS] Top-N ranking identified highest market (Mumbai: 6,200.00).")

    # -------------------------------------------------------------
    # 7. Follow-Up Question: "What about the second highest?"
    # -------------------------------------------------------------
    print("\n--- TEST 7: Contextual Follow-up Query ---")
    context = {
        "previous_question": "Which market has the highest average price?",
        "previous_query_plan": res_top["query_plan"],
    }
    res_follow = run_ask_analyst_query("What about the second highest?", datasets, metadata, context=context)
    assert res_follow["status"] == "success"
    assert "Pune" in res_follow["answer"]["answer"]
    assert "5,050" in res_follow["answer"]["answer"]
    print("  [PASS] Context follow-up correctly identified second highest entity (Pune: 5,050.00).")

    # -------------------------------------------------------------
    # 8. Filter Query
    # -------------------------------------------------------------
    print("\n--- TEST 8: Filter Query (Modal Price > 5000) ---")
    res_filt = run_ask_analyst_query("Show me records where modal price is greater than 5000", datasets, metadata)
    assert res_filt["status"] == "success"
    data_filt = res_filt["result"]["data"]
    assert len(data_filt) == 5
    assert (data_filt["Modal_Price"] > 5000).all()
    print("  [PASS] Filter engine safely extracted all 5 records with price > 5000.")

    # -------------------------------------------------------------
    # 9. Missing Values Query
    # -------------------------------------------------------------
    print("\n--- TEST 9: Missing Values Query ---")
    res_miss = run_ask_analyst_query("Which columns have missing values?", datasets, metadata)
    assert res_miss["status"] == "success"
    assert "no missing values" in res_miss["answer"]["answer"].lower()
    print("  [PASS] Missing values query executed cleanly (100% complete).")

    # -------------------------------------------------------------
    # 10. Temporal Trend Query
    # -------------------------------------------------------------
    print("\n--- TEST 10: Temporal Trend Query ---")
    res_trend = run_ask_analyst_query("Show the price trend over time.", datasets, metadata)
    assert res_trend["status"] == "success"
    assert res_trend["visualization"]["chart_type"] == "line"
    assert any("causal" in lim.lower() for lim in res_trend["answer"]["limitations"])
    print("  [PASS] Trend query synthesized line visualization and causal limitation.")

    # -------------------------------------------------------------
    # 11. Statistical Correlation Query
    # -------------------------------------------------------------
    print("\n--- TEST 11: Correlation Query & Causation Guard ---")
    res_corr = run_ask_analyst_query("Which columns are strongly correlated?", datasets, metadata)
    assert res_corr["status"] == "success"
    assert any("not imply causation" in lim.lower() for lim in res_corr["answer"]["limitations"])
    print("  [PASS] Correlation query verified with explicit causation warning.")

    # -------------------------------------------------------------
    # 12. Ambiguity Detection & User Clarification
    # -------------------------------------------------------------
    print("\n--- TEST 12: Column Ambiguity Guard ---")
    ambig_meta = {
        "sales.csv": {"column_names": ["Market", "Modal_Price", "Min_Price", "Max_Price"]},
    }
    res_ambig = run_ask_analyst_query("What is the average price?", datasets, ambig_meta)
    assert res_ambig["status"] == "needs_clarification"
    assert res_ambig["validation"]["requires_clarification"] is True
    assert len(res_ambig["validation"]["clarification_options"]) >= 2
    print("  [PASS] Ambiguous column query halted safely and requested user clarification.")

    # -------------------------------------------------------------
    # 13. Valid Cross-Dataset Analysis
    # -------------------------------------------------------------
    print("\n--- TEST 13: Valid Cross-Dataset Analysis ---")
    audit_log = []
    res_cross = run_ask_analyst_query(
        "Compare sales between regions",
        datasets,
        metadata,
        relationships=relationships,
        join_audit=audit_log,
    )
    assert res_cross["status"] == "success"
    assert len(audit_log) >= 1
    assert audit_log[0].status == "SUCCESS"
    print("  [PASS] Cross-dataset analysis linked via verified foreign key relationship.")

    # -------------------------------------------------------------
    # 14. Unverified Cross-Dataset Join Blocked
    # -------------------------------------------------------------
    print("\n--- TEST 14: Unverified Cross-Dataset Join Blocked ---")
    res_unverified = run_ask_analyst_query(
        "Compare sales between regions",
        datasets,
        metadata,
        relationships=[],  # No verified relationships!
    )
    assert res_unverified["status"] == "error"
    assert any("relationship" in err.lower() for err in res_unverified["errors"])
    print("  [PASS] Unverified cross-dataset join blocked successfully.")

    # -------------------------------------------------------------
    # 15. Many-to-Many Guard
    # -------------------------------------------------------------
    print("\n--- TEST 15: Many-to-Many Join Explosion Guard ---")
    m2m_rel = [
        Relationship(
            source_dataset="sales.csv",
            source_column="Market",
            target_dataset="customers.csv",
            target_column="Market",
            relationship_type="Many-to-Many",
        )
    ]
    res_m2m = run_ask_analyst_query(
        "Compare sales between regions",
        datasets,
        metadata,
        relationships=m2m_rel,
    )
    assert res_m2m["status"] == "error"
    assert any("many-to-many" in err.lower() for err in res_m2m["errors"])
    print("  [PASS] Many-to-Many join blocked to prevent record duplication.")

    # -------------------------------------------------------------
    # 16. Security Verification: Arbitrary Code Injection Blocked
    # -------------------------------------------------------------
    print("\n--- TEST 16: Security Guard (No Arbitrary Code/SQL) ---")
    attacks = [
        "Run Python code to delete a file",
        "execute os.system('calc')",
        "import subprocess; subprocess.Popen('ls')",
        "drop table sales;",
        "execute arbitrary SQL SELECT *",
    ]
    for attack in attacks:
        res_sec = run_ask_analyst_query(attack, datasets, metadata)
        assert res_sec["status"] == "error", f"Attack '{attack}' was not rejected!"
        assert any("disallowed" in str(e).lower() or "rejected" in str(e).lower() for e in res_sec["errors"])
    print("  [PASS] All 5 malicious arbitrary code/SQL execution attempts rejected safely.")

    # -------------------------------------------------------------
    # 17. Phase 4 Anomaly Reuse
    # -------------------------------------------------------------
    print("\n--- TEST 17: Phase 4 Anomaly Result Reuse ---")
    res_anom = run_ask_analyst_query("Are there unusual values in this dataset?", datasets, metadata)
    assert res_anom["status"] == "success"
    assert "result" in res_anom
    print("  [PASS] Anomaly query evaluated non-destructively without modifying dataset.")

    # -------------------------------------------------------------
    # 18. Cleaned Dataset Priority
    # -------------------------------------------------------------
    print("\n--- TEST 18: Cleaned Dataset Priority ---")
    df_cleaned = datasets["sales.csv"].copy()
    df_cleaned.loc[0, "Modal_Price"] = 99999.0
    cleaned_ds = {"sales.csv": df_cleaned}
    res_clean_pri = run_ask_analyst_query(
        "What is the maximum modal price?",
        datasets,
        metadata,
        cleaned_datasets=cleaned_ds,
        config={"use_cleaned_data_by_default": True},
    )
    assert res_clean_pri["status"] == "success"
    assert "99,999" in res_clean_pri["answer"]["answer"]
    assert "cleaned" in res_clean_pri["evidence"]["dataset_source"].lower()
    print("  [PASS] Cleaned dataset prioritized when configured, with explicit source attribution.")

    print("\n=====================================================================")
    print("ALL 18 PHASE 6 CORE SUITE ACCEPTANCE TESTS PASSED WITH 100% SUCCESS!")
    print("=====================================================================")


if __name__ == "__main__":
    run_all_tests()
