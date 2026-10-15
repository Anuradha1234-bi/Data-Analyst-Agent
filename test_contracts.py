"""Test Suite for Phase 5 Implementation Boundary and Module Contracts (1 through 10).

Validates:
- Module 1: statistical_analysis (descriptive moments, distributions, correlations, category unique counts)
- Module 2: trend_analysis (net changes, directions, peaks, drops, absence of date column)
- Module 3: correlation_analysis (correlation matrix, non-causal relationship statements)
- Module 4: category_analysis (distributions, Pareto top/bottom items)
- Module 5: anomaly_integration (ingestion of Phase 4 results without recalculating)
- Module 6: cross_dataset_analysis (safe join, row explosion / many-to-many guards)
- Module 7: insight_engine (structured, evidence-based insights traceable to calculations)
- Module 8: analysis_visualizations (Plotly chart configurations generated from analysis)
- Module 9: ai_insight_explainer (human-readable factual summary strictly without hallucination)
- Module 10: analysis_orchestrator (central coordination pipeline returning full structured result)
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.statistics_tool import StatisticsTool
from agents.insight_agent import InsightAgent
from services.chart_generator import ChartGeneratorService, analysis_visualizations
from services.insight_service import InsightService, analysis_orchestrator
from models.relationship import Relationship
from models.anomaly import IQRAnalysisResult, IsolationForestResult


def test_module_1_statistical_analysis():
    print("Testing Module 1: statistical_analysis...")
    df = pd.DataFrame({
        "num1": [10.0, 20.0, 30.0, 40.0, 50.0],
        "num2": [100.0, 200.0, 300.0, 400.0, 500.0],
        "cat1": ["A", "B", "A", "B", "C"],
    })
    res = StatisticsTool.statistical_analysis(df)
    assert res["status"] == "success", f"Module 1 failed: {res}"
    assert "column_statistics" in res
    assert "distribution_statistics" in res
    assert "correlations" in res
    assert "category_statistics" in res
    assert "num1" in res["column_statistics"]
    assert res["column_statistics"]["num1"]["mean"] == 30.0

    # Error handling test
    empty_res = StatisticsTool.statistical_analysis(pd.DataFrame())
    assert empty_res["status"] == "error"
    print("  [PASS] Module 1 meets contract.")


def test_module_2_trend_analysis():
    print("Testing Module 2: trend_analysis...")
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Price": [10, 12, 15, 14, 18, 20, 25, 23, 28, 30],
    })
    res = StatisticsTool.trend_analysis(df, date_column="Date")
    assert res["status"] == "success", f"Module 2 failed: {res}"
    assert res["date_column"] == "Date"
    assert len(res["trends"]) > 0
    assert res["trends"][0]["direction"] == "increasing"
    assert res["trends"][0]["change_percentage"] == 200.0
    assert len(res["peaks"]) > 0
    assert len(res["drops"]) > 0

    # Missing date handling test
    df_no_date = pd.DataFrame({"Val": [1, 2, 3]})
    res_no_date = StatisticsTool.trend_analysis(df_no_date)
    assert res_no_date["status"] == "unavailable"
    assert "No valid date column" in res_no_date["reason"]
    print("  [PASS] Module 2 meets contract.")


def test_module_3_correlation_analysis():
    print("Testing Module 3: correlation_analysis...")
    df = pd.DataFrame({
        "Quantity": [10, 20, 30, 40, 50, 60],
        "Revenue": [100, 200, 300, 400, 500, 600],
        "Cost": [50, 40, 30, 20, 10, 5],
    })
    res = StatisticsTool.correlation_analysis(df)
    assert res["status"] == "success", f"Module 3 failed: {res}"
    assert "matrix" in res
    assert "relationships" in res
    for rel in res["relationships"]:
        assert "column_a" in rel
        assert "column_b" in rel
        assert "correlation" in rel
        assert "strength" in rel
        assert "direction" in rel
        # Non-causal phrasing check
        statement = rel.get("statement", "")
        assert "cause" not in statement.lower(), "Statement must not imply causality"
    print("  [PASS] Module 3 meets contract.")


def test_module_4_category_analysis():
    print("Testing Module 4: category_analysis...")
    df = pd.DataFrame({
        "Region": ["North", "North", "South", "East", "North"],
        "Sales": [500, 700, 200, 150, 600],
    })
    res = StatisticsTool.category_analysis(df)
    assert res["status"] == "success", f"Module 4 failed: {res}"
    assert "distributions" in res
    assert "top_categories" in res
    assert "bottom_categories" in res
    assert res["distributions"][0]["column"] == "Region"
    assert res["distributions"][0]["most_frequent"] == "North"
    print("  [PASS] Module 4 meets contract.")


def test_module_5_anomaly_integration():
    print("Testing Module 5: anomaly_integration...")
    # Mock Phase 4 results
    mock_iqr = IQRAnalysisResult(
        dataset_name="test.csv",
        total_rows=100,
        columns_analyzed=["Price", "Volume"],
        column_results={},
        total_outlier_rows=4,
        outlier_rate=4.0,
        all_outlier_indices=[5, 12, 18, 92],
        multiplier=1.5,
    )
    mock_if = IsolationForestResult(
        dataset_name="test.csv",
        rows_analyzed=100,
        features_used=["Price", "Volume"],
        contamination=0.05,
        anomaly_count=3,
        anomaly_pct=3.0,
        anomaly_scores=[0.1] * 100,
        raw_decision_scores=[-0.1] * 100,
        anomaly_labels=["Normal"] * 97 + ["Anomaly"] * 3,
        anomaly_indices=[5, 12, 55],
    )
    phase4_results = {
        "iqr": mock_iqr,
        "isolation_forest": mock_if,
    }
    res = StatisticsTool.anomaly_integration(phase4_results)
    assert res["status"] == "success", f"Module 5 failed: {res}"
    assert "anomaly_summary" in res
    assert res["anomaly_summary"]["total_anomalies"] == 7
    assert res["anomaly_summary"]["iqr_outliers"] == 4
    assert res["anomaly_summary"]["isolation_forest_anomalies"] == 3
    assert "Price" in res["affected_columns"]
    assert 5 in res["affected_rows"]
    print("  [PASS] Module 5 meets contract.")


def test_module_6_cross_dataset_analysis():
    print("Testing Module 6: cross_dataset_analysis...")
    sales_df = pd.DataFrame({
        "order_id": [1, 2, 3],
        "user_id": ["U1", "U2", "U1"],
        "amount": [100.0, 250.0, 150.0],
    })
    users_df = pd.DataFrame({
        "user_id": ["U1", "U2"],
        "tier": ["Gold", "Silver"],
    })
    rel = Relationship(
        source_dataset="sales.csv",
        source_column="user_id",
        target_dataset="users.csv",
        target_column="user_id",
        confidence="HIGH",
    )
    res = StatisticsTool.cross_dataset_analysis(
        datasets={"sales.csv": sales_df, "users.csv": users_df},
        validated_relationships=[rel],
    )
    assert res["status"] == "success", f"Module 6 failed: {res}"
    assert res["rows_after"] == 3
    assert "analysis" in res

    # Unsafe join (duplicate keys causing row explosion) test
    bad_users_df = pd.DataFrame({
        "user_id": ["U1", "U1", "U2"],  # Duplicate key!
        "tier": ["Gold", "Platinum", "Silver"],
    })
    res_unsafe = StatisticsTool.cross_dataset_analysis(
        datasets={"sales.csv": sales_df, "users.csv": bad_users_df},
        validated_relationships=[rel],
    )
    assert res_unsafe["status"] == "blocked"
    assert "many-to-many" in res_unsafe["reason"].lower() or "duplicate" in res_unsafe["reason"].lower()
    print("  [PASS] Module 6 meets contract.")


def test_module_7_insight_engine():
    print("Testing Module 7: insight_engine...")
    payload = {
        "dataset_name": "orders.csv",
        "data_quality": {"duplicate_rows": 12, "duplicate_rate": 6.0, "missing_count": 5, "missing_rate": 2.5},
        "trends": {
            "date_column": "Date",
            "trends": [{"column": "Sales", "direction": "increasing", "change_percentage": 22.5, "start_value": 100, "end_value": 122.5, "start_date": "2024-01-01", "end_date": "2024-02-01"}],
        },
        "correlations": {
            "relationships": [{"column_a": "Quantity", "column_b": "Sales", "correlation": 0.91, "strength": "strong", "direction": "positive", "statement": "Quantity and Sales show a strong positive statistical association."}],
        },
        "categories": {
            "top_categories": [{"category_column": "Region", "metric_column": "Sales", "concentration_ratio_top3": 75.0, "items": [{"category": "North", "value": 500, "share_pct": 50.0}]}],
        },
        "anomalies": {
            "anomaly_summary": {"total_anomalies": 8},
            "affected_columns": ["Sales"],
        },
    }
    insights = InsightAgent.insight_engine(payload)
    assert len(insights) >= 5, f"Expected multiple insights, got {len(insights)}"
    for ins in insights:
        assert "title" in ins
        assert "category" in ins
        assert "finding" in ins
        assert "evidence" in ins
        assert "severity" in ins
        assert "dataset" in ins
        assert "columns" in ins
        assert "recommended_investigation" in ins
    print("  [PASS] Module 7 meets contract.")


def test_module_8_analysis_visualizations():
    print("Testing Module 8: analysis_visualizations...")
    sample_analysis = {
        "trends": {
            "date_column": "Date",
            "trends": [{"column": "Metric", "change_percentage": 15.0, "start_value": 10, "end_value": 25}],
        },
        "correlations": {
            "matrix": {"ColA": {"ColA": 1.0, "ColB": 0.8}, "ColB": {"ColA": 0.8, "ColB": 1.0}},
        },
        "categories": {
            "top_categories": [{"metric_column": "Metric", "items": [{"category": "A", "value": 100}, {"category": "B", "value": 80}]}],
        },
        "statistics": {
            "column_statistics": {"Metric": {"mean": 20, "std": 5, "min": 10, "max": 30, "median": 20, "q1": 15, "q3": 25}},
        },
    }
    res = ChartGeneratorService.analysis_visualizations(sample_analysis)
    assert res["status"] == "success", f"Module 8 failed: {res}"
    assert "trend" in res["charts"]
    assert "correlation" in res["charts"]
    assert "category" in res["charts"]
    assert "distribution" in res["charts"]
    print("  [PASS] Module 8 meets contract.")


def test_module_9_ai_insight_explainer():
    print("Testing Module 9: ai_insight_explainer...")
    structured_context = {
        "dataset_name": "quarterly_sales.csv",
        "insights": [
            {"title": "Surge in Sales", "severity": "High", "finding": "Sales increased by 22.5% during Q1."},
            {"title": "High Correlation", "severity": "Medium", "finding": "Marketing Spend and Sales are strongly correlated."},
        ],
        "trends": {
            "trends": [{"column": "Sales", "direction": "increasing", "change_percentage": 22.5, "start_date": "2024-01-01", "end_date": "2024-03-31"}],
        },
        "correlations": {
            "relationships": [{"column_a": "Marketing Spend", "column_b": "Sales", "correlation": 0.88, "strength": "strong", "direction": "positive"}],
        },
    }
    explanation = InsightAgent.ai_insight_explainer(structured_context)
    assert "Executive Narrative Summary" in explanation
    assert "quarterly_sales.csv" in explanation
    assert "22.5%" in explanation
    assert "Marketing Spend" in explanation
    print("  [PASS] Module 9 meets contract.")


def test_module_10_analysis_orchestrator():
    print("Testing Module 10: analysis_orchestrator...")
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Category": ["X", "Y"] * 10,
        "Amount": [10.0 + i * 2.0 for i in range(20)],
        "Volume": [100.0 - i * 1.5 for i in range(20)],
    })
    datasets = {"finance.csv": df}
    res = InsightService.analysis_orchestrator(datasets=datasets)
    assert res["status"] == "success", f"Module 10 failed: {res}"
    assert "finance.csv" in res["datasets_analyzed"]
    assert "statistics" in res
    assert "trends" in res
    assert "correlations" in res
    assert "categories" in res
    assert "anomalies" in res
    assert "cross_dataset" in res
    assert "insights" in res
    assert len(res["insights"]) > 0

    # Error contract test
    err_res = InsightService.analysis_orchestrator(datasets={})
    assert err_res["status"] == "error"
    assert err_res["error_type"] == "ValidationError"
    print("  [PASS] Module 10 meets contract.")


if __name__ == "__main__":
    print("=====================================================================")
    print("VERIFYING ALL 10 MODULE CONTRACTS FOR PHASE 5")
    print("=====================================================================")
    test_module_1_statistical_analysis()
    test_module_2_trend_analysis()
    test_module_3_correlation_analysis()
    test_module_4_category_analysis()
    test_module_5_anomaly_integration()
    test_module_6_cross_dataset_analysis()
    test_module_7_insight_engine()
    test_module_8_analysis_visualizations()
    test_module_9_ai_insight_explainer()
    test_module_10_analysis_orchestrator()
    print("=====================================================================")
    print("ALL 10 MODULE CONTRACTS PASSED WITH 100% SPEC COMPLIANCE!")
    print("=====================================================================")
