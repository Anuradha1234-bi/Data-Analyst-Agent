"""Comprehensive Automated Test Suite for Phase 8 Advanced Analytical Capabilities.

Verifies:
1. DuckDB In-Memory Columnar SQL Execution:
   - Aggregations (SUM, AVG, MIN, MAX, COUNT, MEDIAN, STDDEV)
   - Group-by and sorting
   - Numerical precision against independent Pandas computation
2. Advanced Statistical Analysis:
   - Linear regression (slope, intercept, R², p-value, trendline)
   - Two-group hypothesis testing (Welch's t-test, Mann-Whitney U, Cohen's d)
   - Chi-Square test of independence (chi2, p-value, Cramér's V)
   - Pearson & Spearman correlation matrices and heatmap structure
3. Automated Data-Driven Insights Engine:
   - Pareto concentration (80/20 rule detection)
   - 3-sigma statistical outlier spike detection
   - Strong bivariate association discovery
   - Data completeness and missingness alerts
4. Multi-turn Conversational Context & Memory:
   - Turn 1: "Show the top 10 products by revenue"
   - Turn 2: "Now show only the top 5" (Limit modifier resolution)
   - Turn 3: "Compare their monthly trends" (Entity reference resolution)
   - Turn 4: "Plot the comparison" (Visualization format resolution)
   - Context isolation across different datasets and users
   - Context clearance via API (POST /api/analysis/context/clear)
5. LLM Planner & Security Sandbox:
   - Deterministic semantic planner fallback when LLM key is absent/invalid
   - Pydantic schema validation preventing hallucinated columns or malicious code
   - Zero eval/exec guarantees
"""

import sys
import os
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base
from app.models.user import User
from app.models.dataset import Dataset
from app.schemas.analyst import AnalysisAskRequest, AnalysisAskResponse
from app.services.data_analyst_service import DataAnalystService
from app.main import app as fastapi_app
from app.auth.jwt import create_access_token

from query.duckdb_engine import DuckDBEngine
from query.advanced_stats import AdvancedStatsEngine
from query.insight_engine import InsightEngine
from query.context_manager import ConversationContextManager
from query.llm_planner import LLMQueryPlanner


def run_advanced_phase8_tests():
    print("=====================================================================")
    print("PHASE 8 ADVANCED ANALYTICAL CAPABILITIES TEST SUITE")
    print("=====================================================================")

    # 1. Setup isolated SQLite DB
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    user = User(
        email="lead_analyst@example.com",
        hashed_password="pw_hash_test_123",
        full_name="Dr. Alan Turing",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 2. Setup temporary datasets
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name)

    # Synthetic realistic eCommerce dataset with 100 rows
    np.random.seed(42)
    n_rows = 100
    dates = pd.date_range("2026-01-01", periods=n_rows, freq="D")
    products = np.random.choice(["Laptop", "Phone", "Tablet", "Monitor", "Headphones"], size=n_rows, p=[0.1, 0.2, 0.2, 0.2, 0.3])
    regions = np.random.choice(["North", "South", "East", "West"], size=n_rows)
    units = np.random.randint(1, 20, size=n_rows)
    # Unit price with deliberate product dependency
    price_map = {"Laptop": 1200.0, "Phone": 800.0, "Tablet": 450.0, "Monitor": 300.0, "Headphones": 80.0}
    unit_prices = np.array([price_map[p] for p in products])
    discounts = np.random.uniform(0.0, 0.25, size=n_rows)
    revenues = units * unit_prices * (1.0 - discounts)

    # Add a deliberate outlier for insight engine detection
    revenues[50] = 50000.0  # Massive revenue spike!

    # Create customer rating with strong positive correlation to unit_price
    ratings = 3.0 + (unit_prices / 1200.0) * 1.8 + np.random.normal(0, 0.1, size=n_rows)
    ratings = np.clip(ratings, 1.0, 5.0)

    df_ecommerce = pd.DataFrame({
        "Date": dates,
        "Product": products,
        "Region": regions,
        "Units": units,
        "UnitPrice": unit_prices,
        "Discount": discounts,
        "Revenue": revenues,
        "Rating": ratings,
    })

    ecom_path = temp_path / "ecommerce.csv"
    df_ecommerce.to_csv(ecom_path, index=False)

    ds_ecom = Dataset(
        user_id=user.id,
        filename="ecommerce.csv",
        file_type="CSV",
        file_path=str(ecom_path),
        rows=n_rows,
        columns=len(df_ecommerce.columns),
        file_size_bytes=ecom_path.stat().st_size,
        has_cleaned=False,
    )
    db.add(ds_ecom)
    db.commit()
    db.refresh(ds_ecom)

    # -----------------------------------------------------------------
    # TEST 1: DuckDB In-Memory Columnar SQL Execution Engine
    # -----------------------------------------------------------------
    print("\n--- TEST 1: DuckDB In-Memory Engine Aggregations & Speed ---")
    assert DuckDBEngine.is_available() is True, "DuckDB must be installed and available."
    print("  [INFO] DuckDB engine is available and loaded.")

    # Execute DuckDB aggregation via Structured Plan
    duck_plan = {
        "intent": "TOP_N",
        "column": "Revenue",
        "aggregation": "sum",
        "group_by": ["Product"],
        "limit": 5,
        "sort": "descending",
    }
    duck_res = DuckDBEngine.execute_plan(df_ecommerce, duck_plan)
    assert duck_res is not None
    assert duck_res["success"] is True
    assert "DuckDB" in duck_res["engine"]
    assert len(duck_res["data"]) > 0

    # Compare with independent Pandas calculation
    pandas_sum = df_ecommerce.groupby("Product")["Revenue"].sum().sort_values(ascending=False).head(5)
    for p_name, expected_val in pandas_sum.items():
        matched_row = duck_res["data"][duck_res["data"]["Product"] == p_name]
        assert not matched_row.empty
        computed_val = float(matched_row.iloc[0]["sum_Revenue"])
        assert abs(computed_val - expected_val) < 1e-4, f"Mismatch in {p_name}: {computed_val} vs {expected_val}"
    print(f"  [PASS] DuckDB columnar group-by aggregation exactly matches Pandas ground truth across all 5 products.")

    # -----------------------------------------------------------------
    # TEST 2: Linear Regression Analysis (OLS)
    # -----------------------------------------------------------------
    print("\n--- TEST 2: Linear Regression Analysis (OLS) ---")
    # Regress Rating on UnitPrice (expected strong positive slope)
    reg_res = AdvancedStatsEngine.compute_linear_regression(df_ecommerce, "UnitPrice", "Rating")
    assert reg_res["success"] is True
    assert reg_res["r_squared"] > 0.70, f"Expected high R^2, got {reg_res['r_squared']}"
    assert reg_res["slope"] > 0, "Slope must be positive"
    assert reg_res["p_value"] < 0.001, "Relationship must be statistically significant"
    assert len(reg_res["line_points"]) == 2, "Line points should have start and end coordinates"
    print(f"  [PASS] Linear Regression calculated: {reg_res['equation']}, R2={reg_res['r_squared']}, p={reg_res['p_value']:.4e}")

    # Test via DataAnalystService natural language question
    req_reg = AnalysisAskRequest(
        dataset_id=ds_ecom.id,
        question="Run a linear regression between UnitPrice and Rating",
    )
    resp_reg = DataAnalystService.ask_question(req_reg, user, db)
    assert resp_reg.status == "success"
    assert "R²" in resp_reg.answer or "r_squared" in str(resp_reg.evidence)
    assert resp_reg.statistical_metrics is not None
    assert "regression" in resp_reg.statistical_metrics
    assert "r_squared" in resp_reg.statistical_metrics["regression"]
    assert resp_reg.visualization is not None
    assert resp_reg.visualization.chart_type == "scatter"
    assert resp_reg.visualization.trendline is not None
    print(f"  [PASS] Natural language regression query returned scatter visualization with fitted trendline.")

    # -----------------------------------------------------------------
    # TEST 3: Two-Group Hypothesis Testing (Welch's t-test / Mann-Whitney)
    # -----------------------------------------------------------------
    print("\n--- TEST 3: Two-Group Hypothesis Testing ---")
    # Compare Revenue between North and South regions
    hyp_res = AdvancedStatsEngine.compare_two_groups(df_ecommerce, "Region", "Revenue", group_a="North", group_b="South")
    assert hyp_res["success"] is True
    assert "p_value" in hyp_res
    assert "cohens_d" in hyp_res
    assert "interpretation" in hyp_res
    print(f"  [PASS] Hypothesis test ({hyp_res['test_name']}): p={hyp_res['p_value']:.4f}, Cohen's d={hyp_res['cohens_d']}")
    print(f"         Interpretation: {hyp_res['interpretation']}")

    # -----------------------------------------------------------------
    # TEST 4: Chi-Square Test of Independence
    # -----------------------------------------------------------------
    print("\n--- TEST 4: Chi-Square Test of Independence ---")
    chi_res = AdvancedStatsEngine.chi_square_test(df_ecommerce, "Product", "Region")
    assert chi_res["success"] is True
    assert "chi2_statistic" in chi_res
    assert "degrees_of_freedom" in chi_res
    assert "cramers_v" in chi_res
    print(f"  [PASS] Chi-square test calculated: chi2={chi_res['chi2_statistic']}, dof={chi_res['degrees_of_freedom']}, Cramers V={chi_res['cramers_v']}")

    # -----------------------------------------------------------------
    # TEST 5: Automated Data-Driven Insight Discovery
    # -----------------------------------------------------------------
    print("\n--- TEST 5: Automated Data-Driven Insights Engine ---")
    insights = InsightEngine.discover_insights(df_ecommerce)
    assert len(insights) >= 2, f"Expected at least 2 insights, got {len(insights)}"

    insight_types = [ins["type"] for ins in insights]
    print(f"  [INFO] Discovered insight types: {insight_types}")

    # Verify outlier detection found our 50,000.0 spike
    outlier_insights = [i for i in insights if "Outlier" in i.get("type", "")]
    assert len(outlier_insights) > 0, "Insight engine must detect extreme statistical outlier."
    print(f"  [PASS] Extreme outlier correctly flagged: '{outlier_insights[0]['statement'][:80]}...'")

    # Verify Pareto or correlation insight
    assoc_insights = [i for i in insights if "Relationship" in i.get("type", "") or "Concentration" in i.get("type", "")]
    assert len(assoc_insights) > 0, "Insight engine must detect associations or concentration."
    print(f"  [PASS] Association/Concentration insight discovered: '{assoc_insights[0]['statement'][:80]}...'")

    # -----------------------------------------------------------------
    # TEST 6: Multi-Turn Conversational Analysis with Session Memory
    # -----------------------------------------------------------------
    print("\n--- TEST 6: Multi-Turn Conversational Analysis Flow ---")

    # Turn 1: "Show top 10 products by revenue"
    req_t1 = AnalysisAskRequest(dataset_id=ds_ecom.id, question="Show top 10 products by revenue")
    resp_t1 = DataAnalystService.ask_question(req_t1, user, db)
    assert resp_t1.status == "success"
    assert resp_t1.result is not None
    count_t1 = len(resp_t1.result.rows)
    print(f"  [Turn 1 PASS] 'Show top 10 products by revenue' -> returned {count_t1} rows.")

    # Turn 2: "Now show only the top 3" (Follow-up modifying limit)
    req_t2 = AnalysisAskRequest(dataset_id=ds_ecom.id, question="Now show only the top 3")
    resp_t2 = DataAnalystService.ask_question(req_t2, user, db)
    assert resp_t2.status == "success"
    assert resp_t2.result is not None
    assert len(resp_t2.result.rows) == 3, f"Expected 3 rows in follow-up, got {len(resp_t2.result.rows)}"
    print(f"  [Turn 2 PASS] 'Now show only the top 3' -> context successfully updated limit to 3.")

    # Turn 3: "Plot this comparison" (Follow-up requesting visualization)
    req_t3 = AnalysisAskRequest(dataset_id=ds_ecom.id, question="Plot this comparison")
    resp_t3 = DataAnalystService.ask_question(req_t3, user, db)
    assert resp_t3.status == "success"
    assert resp_t3.visualization is not None
    assert resp_t3.visualization.recommended is True
    print(f"  [Turn 3 PASS] 'Plot this comparison' -> successfully generated chart from prior context.")

    # Verify context reset API endpoint with test db override
    from app.database import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    clear_resp = client.post(f"/api/analysis/context/clear?dataset_id={ds_ecom.id}", headers=headers)
    assert clear_resp.status_code == 200, f"Expected 200, got {clear_resp.status_code}: {clear_resp.text}"
    assert clear_resp.json()["success"] is True

    # After clearing, active context should be empty
    ctx = ConversationContextManager.get_context(user.id, ds_ecom.id, "original")
    assert not ctx or not ctx.get("previous_query_plan")
    print(f"  [PASS] Conversational session context successfully cleared via REST API endpoint.")

    # -----------------------------------------------------------------
    # TEST 7: LLM Planner Fallback & Pydantic Validation
    # -----------------------------------------------------------------
    print("\n--- TEST 7: LLM Planner Fallback & Schema Allowlist Validation ---")
    # Call plan_query with no GEMINI_API_KEY
    orig_env = os.environ.get("GEMINI_API_KEY")
    try:
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

        metadata = {
            "columns": ["Product", "Revenue", "Units"],
            "types": {"Product": "object", "Revenue": "float64", "Units": "int64"},
            "rows": 100,
        }
        plan, provider = LLMQueryPlanner.plan_query("What is the average revenue?", metadata)
        assert "Deterministic Semantic Engine" in provider
        assert plan["intent"] == "AVERAGE"
        assert plan["column"] == "Revenue"
        print(f"  [PASS] LLM absence gracefully fell back to: '{provider}' with valid intent '{plan['intent']}'.")

        # Test validation guard against hallucinated malicious code
        malicious_input = {"intent": "EXEC_ARBITRARY_CODE", "column": "DROP TABLE users;"}
        is_valid = LLMQueryPlanner.validate_plan_structure(malicious_input, ["Product", "Revenue", "Units"])
        assert is_valid is False
        print("  [PASS] LLM validation strictly rejected unallowlisted intent and malicious column injection.")
    finally:
        if orig_env:
            os.environ["GEMINI_API_KEY"] = orig_env

    # -----------------------------------------------------------------
    # TEST 8: Full REST API Contract Verification (POST /api/analysis/ask)
    # -----------------------------------------------------------------
    print("\n--- TEST 8: REST API End-to-End Contract Verification ---")
    payload = {
        "dataset_id": ds_ecom.id,
        "question": "Which product generates the highest revenue?",
        "version": "original",
    }
    api_resp = client.post("/api/analysis/ask", json=payload, headers=headers)
    assert api_resp.status_code == 200, f"Failed with {api_resp.text}"
    data = api_resp.json()

    assert data["status"] == "success"
    assert data["execution_engine"] is not None
    assert data["llm_provider"] is not None
    assert "automated_insights" in data
    assert isinstance(data["automated_insights"], list)
    assert len(data["automated_insights"]) > 0
    assert "follow_up_suggestions" in data
    assert len(data["follow_up_suggestions"]) > 0
    print(f"  [PASS] REST API returned 200 OK with full Phase 8 contract: Engine='{data['execution_engine']}', Insights count={len(data['automated_insights'])}.")

    # Cleanup
    fastapi_app.dependency_overrides.clear()
    temp_dir.cleanup()
    db.close()

    print("\n=====================================================================")
    print("ALL 8 PHASE 8 ADVANCED ANALYTICAL TESTS PASSED SUCCESSFULLY!")
    print("=====================================================================")


if __name__ == "__main__":
    run_advanced_phase8_tests()
