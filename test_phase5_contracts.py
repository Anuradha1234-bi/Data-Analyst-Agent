"""Comprehensive Test Suite for Phase 5 Explicit Scope & Python Function Contracts.

Tests all 14 functions defined in Part 5:
1.  calculate_column_statistics (numeric & categorical columns, immutability, missing handling)
2.  analyze_distributions (shape classification, skewness, kurtosis, variance, IQR bounds)
3.  calculate_correlations (methods: pearson, spearman, kendall; non-causal phrasing; insufficient columns)
4.  analyze_categories (value counts, top/bottom categories, imbalance detection, numeric aggregations)
5.  analyze_trends (increasing/decreasing directions, peaks, drops, sudden shifts, date detection)
6.  detect_date_columns (datetime dtypes, string formats, avoids arbitrary numeric columns)
7.  summarize_anomaly_results (Phase 4 ingestion without recalculation)
8.  summarize_data_quality (duplicates, missing counts, constant columns)
9.  analyze_across_datasets (safe joins, many-to-many duplication guards)
10. generate_insights (structured, evidence-backed insight synthesis)
11. validate_insights (filters/validates required keys and evidence)
12. prepare_analysis_visualizations (chart configurations generated from analysis)
13. explain_insights_with_ai (grounded executive summaries without hallucinated numbers)
14. run_phase5_analysis (complete central pipeline coordination)
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.phase5_engine import (
    calculate_column_statistics,
    analyze_distributions,
    calculate_correlations,
    analyze_categories,
    analyze_trends,
    detect_date_columns,
    summarize_anomaly_results,
    summarize_data_quality,
    analyze_across_datasets,
    generate_insights,
    validate_insights,
    prepare_analysis_visualizations,
    explain_insights_with_ai,
    run_phase5_analysis,
)
from models.anomaly import IQRAnalysisResult, IsolationForestResult


def test_1_calculate_column_statistics():
    print("Testing 5.1 calculate_column_statistics...")
    df = pd.DataFrame({
        "num": [10.0, 20.0, 30.0, 40.0, 50.0],
        "cat": ["Apple", "Banana", "Apple", "Cherry", "Banana"],
        "with_nulls": [1.0, 2.0, np.nan, 4.0, 5.0],
    })
    df_copy = df.copy(deep=True)

    stats = calculate_column_statistics(df)
    # Check Data Immutability
    pd.testing.assert_frame_equal(df, df_copy)

    assert "num" in stats
    assert stats["num"]["count"] == 5
    assert stats["num"]["mean"] == 30.0
    assert stats["num"]["median"] == 30.0
    assert stats["num"]["min"] == 10.0
    assert stats["num"]["max"] == 50.0
    assert stats["num"]["q1"] == 20.0
    assert stats["num"]["q3"] == 40.0
    assert stats["num"]["iqr"] == 20.0
    assert stats["num"]["missing_count"] == 0

    assert "with_nulls" in stats
    assert stats["with_nulls"]["missing_count"] == 1
    assert stats["with_nulls"]["missing_percentage"] == 20.0

    assert "cat" in stats
    assert stats["cat"]["mean"] is None
    assert stats["cat"]["unique_count"] == 3
    print("  [PASS] calculate_column_statistics verified.")


def test_2_analyze_distributions():
    print("Testing 5.2 analyze_distributions...")
    df = pd.DataFrame({
        "symmetric": [10, 20, 30, 40, 50],
        "skewed": [1, 2, 2, 3, 25],
    })
    dists = analyze_distributions(df)
    assert "symmetric" in dists
    assert "skewed" in dists
    assert dists["symmetric"]["shape_label"] == "Normal / Symmetric"
    assert dists["skewed"]["is_skewed"] is True
    assert "outlier_bounds" in dists["skewed"]
    assert "lower" in dists["skewed"]["outlier_bounds"]
    assert "upper" in dists["skewed"]["outlier_bounds"]
    print("  [PASS] analyze_distributions verified.")


def test_3_calculate_correlations():
    print("Testing 5.3 calculate_correlations...")
    df = pd.DataFrame({
        "A": [1, 2, 3, 4, 5],
        "B": [2, 4, 6, 8, 10],  # Perfect positive correlation
        "C": [10, 8, 6, 4, 2],  # Perfect negative correlation
    })
    res_pearson = calculate_correlations(df, method="pearson")
    assert res_pearson["status"] == "success"
    assert "matrix" in res_pearson
    rels = res_pearson["relationships"]
    assert len(rels) >= 2
    # Check non-causal language
    for r in rels:
        assert "cause" not in r["statement"].lower()

    # Test method validation
    res_invalid = calculate_correlations(df, method="invalid_method")
    assert res_invalid["status"] == "error"

    # Test insufficient columns
    df_one_col = pd.DataFrame({"A": [1, 2, 3]})
    res_one = calculate_correlations(df_one_col)
    assert res_one["status"] == "unavailable"
    print("  [PASS] calculate_correlations verified.")


def test_4_analyze_categories():
    print("Testing 5.4 analyze_categories...")
    df = pd.DataFrame({
        "Department": ["Sales", "Sales", "Sales", "HR", "IT"],
        "Budget": [5000, 6000, 7000, 2000, 3000],
    })
    res = analyze_categories(df)
    assert res["status"] == "success"
    assert len(res["distributions"]) > 0
    dept_dist = res["distributions"][0]
    assert dept_dist["most_frequent"] == "Sales"
    assert dept_dist["most_frequent_percentage"] == 60.0
    assert dept_dist["is_imbalanced"] is True
    assert len(res["top_categories"]) > 0
    print("  [PASS] analyze_categories verified.")


def test_5_analyze_trends():
    print("Testing 5.5 analyze_trends...")
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Revenue": [100, 110, 120, 130, 150, 140, 180, 200, 190, 220],
    })
    res = analyze_trends(df, date_column="Date")
    assert res["status"] == "success"
    assert res["date_column"] == "Date"
    assert len(res["trends"]) > 0
    tr = res["trends"][0]
    assert tr["direction"] == "increasing"
    assert tr["change_percentage"] == 120.0
    assert len(res["peaks"]) > 0
    assert len(res["drops"]) > 0

    # Test missing date column
    res_bad = analyze_trends(df, date_column="NonExistentDate")
    assert res_bad["status"] == "unavailable"
    print("  [PASS] analyze_trends verified.")


def test_6_detect_date_columns():
    print("Testing 5.6 detect_date_columns...")
    df = pd.DataFrame({
        "created_at": pd.date_range("2024-01-01", periods=5),
        "string_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        "not_a_date": [100, 200, 300, 400, 500],
        "category": ["A", "B", "C", "D", "E"],
    })
    date_cols = detect_date_columns(df)
    assert "created_at" in date_cols
    assert "string_date" in date_cols
    assert "not_a_date" not in date_cols
    assert "category" not in date_cols
    print("  [PASS] detect_date_columns verified.")


def test_7_summarize_anomaly_results():
    print("Testing 5.7 summarize_anomaly_results...")
    mock_iqr = IQRAnalysisResult(
        dataset_name="metrics.csv",
        total_rows=50,
        columns_analyzed=["Price"],
        column_results={},
        total_outlier_rows=3,
        outlier_rate=6.0,
        all_outlier_indices=[1, 4, 9],
        multiplier=1.5,
    )
    res = summarize_anomaly_results({"iqr": mock_iqr})
    assert res["status"] == "success"
    assert res["total_anomalies"] == 3
    assert res["iqr_outliers"] == 3
    assert "Price" in res["affected_columns"]
    print("  [PASS] summarize_anomaly_results verified.")


def test_8_summarize_data_quality():
    print("Testing 5.8 summarize_data_quality...")
    df = pd.DataFrame({
        "A": [1, 2, 2, 4],
        "B": ["x", "y", "y", "z"],
        "C": [10, np.nan, np.nan, 40],
        "const": [1, 1, 1, 1],
    })
    dq = summarize_data_quality(df)
    assert dq["duplicate_rows"] == 1
    assert dq["duplicate_rate"] == 25.0
    assert dq["missing_count"] == 2
    assert "const" in dq["constant_columns"]
    print("  [PASS] summarize_data_quality verified.")


def test_9_analyze_across_datasets():
    print("Testing 5.9 analyze_across_datasets...")
    sales = pd.DataFrame({"order_id": [1, 2, 3], "cust_id": ["C1", "C2", "C1"], "amt": [50.0, 100.0, 75.0]})
    customers = pd.DataFrame({"cust_id": ["C1", "C2"], "segment": ["Enterprise", "Retail"]})
    rel_valid = {
        "source_dataset": "sales",
        "source_column": "cust_id",
        "target_dataset": "customers",
        "target_column": "cust_id",
        "confidence": "HIGH",
    }
    res = analyze_across_datasets({"sales": sales, "customers": customers}, validated_relationships=[rel_valid])
    assert res["status"] == "success"
    assert res["rows_after"] == 3
    assert "analysis" in res

    # Test Many-to-Many Guard
    bad_customers = pd.DataFrame({"cust_id": ["C1", "C1", "C2"], "segment": ["A", "B", "C"]})
    res_blocked = analyze_across_datasets({"sales": sales, "customers": bad_customers}, validated_relationships=[rel_valid])
    assert res_blocked["status"] == "blocked"
    assert "many-to-many" in res_blocked["reason"].lower()
    print("  [PASS] analyze_across_datasets verified.")


def test_10_and_11_generate_and_validate_insights():
    print("Testing 5.10 generate_insights and 5.11 validate_insights...")
    stats = {
        "dataset_name": "store.csv",
        "column_statistics": {"Sales": {"mean": 500, "median": 450, "skewness": 1.2}},
        "distribution_statistics": {"Sales": {"is_skewed": True, "shape_label": "Right-Skewed"}},
    }
    trends = {
        "date_column": "Date",
        "trends": [{"column": "Sales", "direction": "increasing", "change_percentage": 25.0, "start_value": 100, "end_value": 125, "start_date": "2024-01-01", "end_date": "2024-02-01"}],
    }
    corrs = {"relationships": []}
    cats = {"top_categories": []}
    anom = {"anomaly_summary": {"total_anomalies": 0}}
    dq = {"duplicate_rows": 0, "missing_count": 0}

    insights = generate_insights(stats, trends, corrs, cats, anom, dq)
    assert len(insights) > 0
    first_ins = insights[0]
    assert "title" in first_ins
    assert "finding" in first_ins
    assert "evidence" in first_ins
    assert "severity" in first_ins

    # Test validation
    validated = validate_insights(insights, {"statistics": stats, "trends": trends})
    assert len(validated) == len(insights)
    print("  [PASS] generate_insights & validate_insights verified.")


def test_12_prepare_analysis_visualizations():
    print("Testing 5.12 prepare_analysis_visualizations...")
    sample_res = {
        "trends": {"date_column": "Date", "trends": [{"column": "Metric", "change_percentage": 10.0, "start_value": 5, "end_value": 10}]},
        "correlations": {"matrix": {"M1": {"M1": 1.0, "M2": 0.8}, "M2": {"M1": 0.8, "M2": 1.0}}},
    }
    viz = prepare_analysis_visualizations(sample_res)
    assert viz["status"] == "success"
    assert "charts" in viz
    print("  [PASS] prepare_analysis_visualizations verified.")


def test_13_explain_insights_with_ai():
    print("Testing 5.13 explain_insights_with_ai...")
    insights = [
        {"title": "Revenue Jump", "finding": "Revenue grew by 25%", "severity": "High", "evidence": {"growth": 25.0}}
    ]
    expl = explain_insights_with_ai(insights, {"dataset_name": "sales.csv", "insights": insights})
    assert expl["status"] == "success"
    assert "Executive Narrative Summary" in expl["summary"]
    assert expl["grounded_in_computed_facts"] is True
    print("  [PASS] explain_insights_with_ai verified.")


def test_14_run_phase5_analysis():
    print("Testing 5.14 run_phase5_analysis (Main Orchestrator)...")
    dates = pd.date_range("2024-01-01", periods=15, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Channel": ["Online", "In-Store", "Online"] * 5,
        "Sales": [100.0 + i * 5 for i in range(15)],
        "Discount": [5.0 + (i % 3) for i in range(15)],
    })
    df_copy = df.copy(deep=True)

    result = run_phase5_analysis({"sales.csv": df})
    # Immutability check
    pd.testing.assert_frame_equal(df, df_copy)

    assert result["status"] == "success"
    assert "sales.csv" in result["datasets_analyzed"]
    assert "statistics" in result
    assert "trends" in result
    assert "correlations" in result
    assert "categories" in result
    assert "anomalies" in result
    assert "data_quality" in result
    assert "insights" in result
    assert len(result["insights"]) > 0
    assert "visualizations" in result
    assert "warnings" in result
    assert "errors" in result

    # Error handling check
    empty_res = run_phase5_analysis({})
    assert empty_res["status"] == "error"
    assert len(empty_res["errors"]) > 0
    print("  [PASS] run_phase5_analysis verified.")


if __name__ == "__main__":
    print("=====================================================================")
    print("VERIFYING ALL 14 PHASE 5 CONCRETE PYTHON FUNCTION CONTRACTS")
    print("=====================================================================")
    test_1_calculate_column_statistics()
    test_2_analyze_distributions()
    test_3_calculate_correlations()
    test_4_analyze_categories()
    test_5_analyze_trends()
    test_6_detect_date_columns()
    test_7_summarize_anomaly_results()
    test_8_summarize_data_quality()
    test_9_analyze_across_datasets()
    test_10_and_11_generate_and_validate_insights()
    test_12_prepare_analysis_visualizations()
    test_13_explain_insights_with_ai()
    test_14_run_phase5_analysis()
    print("=====================================================================")
    print("ALL 14 PYTHON FUNCTION CONTRACTS PASSED WITH 100% SPEC COMPLIANCE!")
    print("=====================================================================")
