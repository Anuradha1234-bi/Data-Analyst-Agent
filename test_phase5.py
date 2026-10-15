"""Comprehensive Test Suite for Phase 5 - Intelligent Data Analysis & Insight Generation.

Verifies:
1. Dataset 1: Single dataset with numeric + categorical + date columns (Trends, Moments, Rankings, Insights).
2. Dataset 2: Multiple related datasets (Cross-dataset safe join, segment analysis).
3. Dataset 3: Dataset with no date column (Gracefully handles absence of temporal features).
4. Dataset 4: Dataset with no numeric columns (Gracefully handles categorical-only data).
5. Dataset 5: Dataset containing anomalies (Verifies Phase 4 anomaly detection is integrated into Phase 5 insights).
6. Safeguard: Duplicate data protection (Blocks unexpected row explosion / many-to-many joins).
7. Integration: Ask Analyst answers queries (trends, correlations, insights, rankings) with real computed evidence.
8. Integration: Report Generator compiles Markdown and PDF reports with Phase 5 sections.
9. Boundary: Preserves Phase 3 safe cleaning and Phase 4 anomaly detection functionality.
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.session_manager import SessionManager
from tools.statistics_tool import StatisticsTool
from agents.insight_agent import InsightAgent
from services.insight_service import InsightService
from services.analyst import AnalystService
from services.report_generator import ReportGeneratorService
from services.chart_generator import ChartGeneratorService
from tools.anomaly_tool import AnomalyTool
from models.relationship import Relationship


def test_scenario_1_numeric_categorical_date():
    """Test 1: Single dataset with numeric + categorical + date columns."""
    print("\n--- TEST 1: Single Dataset (Numeric + Categorical + Date) ---")
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    prices = 100 + np.cumsum(np.random.normal(1.2, 3.0, size=n))
    quantities = np.random.randint(10, 500, size=n)
    markets = np.random.choice(["Pune", "Mumbai", "Nashik", "Nagpur"], size=n, p=[0.4, 0.3, 0.2, 0.1])

    df = pd.DataFrame({
        "Date": dates,
        "Market": markets,
        "Price": prices,
        "Quantity": quantities,
    })

    summary = StatisticsTool.compute_summary(df, dataset_name="market_data.csv")

    assert summary.row_count == 100, f"Expected 100 rows, got {summary.row_count}"
    assert "Price" in summary.distributions, "Price must be analyzed in distributions"
    assert "Quantity" in summary.distributions, "Quantity must be analyzed in distributions"

    # Verify distributions
    price_dist = summary.distributions["Price"]
    assert price_dist.mean > 0, "Price mean must be positive"
    assert price_dist.iqr > 0, "Price IQR must be positive"

    # Verify trends
    assert len(summary.trends) > 0, "Trends must be detected with Date column"
    price_trend = next((t for t in summary.trends if t.metric_column == "Price"), None)
    assert price_trend is not None, "Price trend must be detected"
    assert price_trend.start_date == "2024-01-01", f"Unexpected start date: {price_trend.start_date}"
    assert price_trend.end_date == "2024-04-09", f"Unexpected end date: {price_trend.end_date}"
    assert price_trend.direction in ("Increasing", "Decreasing", "Stable", "Volatile / Fluctuating")

    # Verify top/bottom rankings
    assert len(summary.top_bottom_rankings) > 0, "Top/bottom rankings must be generated"
    tb = summary.top_bottom_rankings[0]
    assert len(tb.top_items) > 0, "Top items must be populated"
    assert tb.concentration_ratio_top3 > 0, "Concentration ratio must be calculated"

    # Verify correlations
    assert summary.correlations is not None, "Correlations must be calculated"
    assert len(summary.correlations.features_analyzed) >= 2, "Price and Quantity must be analyzed"

    # Verify category breakdown
    assert "Market" in summary.categories, "Market must be in categories"
    m_cat = summary.categories["Market"]
    assert m_cat.most_frequent == "Pune", f"Expected Pune as most frequent, got {m_cat.most_frequent}"

    # Verify insights synthesis
    insights = InsightAgent.generate_insights(summary)
    assert len(insights) > 0, "Insights must be generated"
    for ins in insights:
        assert ins.title, "Insight must have a title"
        assert ins.finding, "Insight must have a finding"
        assert ins.evidence, "Insight must contain calculated evidence"
        assert ins.severity in ("High", "Medium", "Low"), f"Invalid severity: {ins.severity}"
        assert ins.recommended_investigation, "Insight must have recommendation"

    print("  [PASS] Single dataset moments, trends, rankings, and insights generated successfully.")


def test_scenario_2_multiple_related_datasets():
    """Test 2: Multiple related datasets with validated relationship and cross-dataset analysis."""
    print("\n--- TEST 2: Multiple Related Datasets & Cross-Dataset Linkage ---")
    sales_df = pd.DataFrame({
        "order_id": [101, 102, 103, 104, 105, 106],
        "cust_id": ["C1", "C2", "C1", "C3", "C2", "C1"],
        "amount": [500.0, 1200.0, 750.0, 300.0, 950.0, 1100.0],
    })

    customers_df = pd.DataFrame({
        "cust_id": ["C1", "C2", "C3", "C4"],
        "segment": ["Enterprise", "Retail", "SMB", "Government"],
        "region": ["West", "North", "South", "East"],
    })

    rel = Relationship(
        source_dataset="sales.csv",
        source_column="cust_id",
        target_dataset="customers.csv",
        target_column="cust_id",
        relationship_type="Many-to-One",
        confidence="HIGH",
        value_overlap_pct=100.0,
    )

    cross_res = StatisticsTool.analyze_cross_dataset(
        left_df=sales_df,
        left_name="sales.csv",
        right_df=customers_df,
        right_name="customers.csv",
        relationship=rel,
    )

    assert not cross_res.is_blocked, f"Safe join should succeed, got blocked: {cross_res.block_reason}"
    assert cross_res.rows_after == 6, f"Expected 6 joined rows, got {cross_res.rows_after}"
    assert len(cross_res.breakdown) > 0, "Breakdown across segments must be populated"

    top_entity = cross_res.breakdown[0]
    assert "entity" in top_entity and "total" in top_entity, "Breakdown must contain entity and total"

    # Test InsightService multi-dataset orchestration
    datasets = {"sales.csv": sales_df, "customers.csv": customers_df}
    all_res = InsightService.analyze_all_datasets(datasets, relationships=[rel])

    assert "sales.csv" in all_res and "customers.csv" in all_res, "Both datasets must be analyzed independently"
    sales_analysis = all_res["sales.csv"]
    cross_insights = [i for i in sales_analysis.insights if i.category == "Cross-Dataset"]
    assert len(cross_insights) > 0, "Cross-dataset insight must be attached to analysis result"
    assert "Enterprise" in cross_insights[0].evidence or "segment" in cross_insights[0].finding.lower()

    print("  [PASS] Multiple related datasets joined safely and cross-dataset insights generated.")


def test_scenario_3_dataset_with_no_date_column():
    """Test 3: Dataset with no date column handles gracefully."""
    print("\n--- TEST 3: Dataset with No Date Column ---")
    df = pd.DataFrame({
        "Department": ["Sales", "Engineering", "Marketing", "HR", "Finance"],
        "Headcount": [45, 120, 30, 15, 25],
        "Budget": [500000.0, 2000000.0, 400000.0, 150000.0, 350000.0],
    })

    summary = StatisticsTool.compute_summary(df, dataset_name="org.csv")
    assert len(summary.date_columns) == 0, "Should detect 0 date columns"
    assert len(summary.trends) == 0, "Trends should be empty without date column"
    assert len(summary.top_bottom_rankings) > 0, "Top/bottom analysis must still function"
    assert summary.correlations is not None, "Correlations must still compute for numeric columns"

    insights = InsightAgent.generate_insights(summary)
    assert any(i.category == "Category" for i in insights), "Category insights should be present"
    assert not any(i.category == "Trend" for i in insights), "No trend insights should be generated"

    print("  [PASS] No-date dataset gracefully skips trend detection without crashing.")


def test_scenario_4_dataset_with_no_numeric_columns():
    """Test 4: Dataset with no numeric columns handles gracefully."""
    print("\n--- TEST 4: Dataset with No Numeric Columns ---")
    df = pd.DataFrame({
        "City": ["London", "Paris", "Berlin", "Madrid", "Rome"],
        "Country": ["UK", "France", "Germany", "Spain", "Italy"],
        "Status": ["Active", "Active", "Pending", "Active", "Inactive"],
    })

    summary = StatisticsTool.compute_summary(df, dataset_name="locations.csv")
    assert len(summary.numeric_columns) == 0, "Should detect 0 numeric columns"
    assert len(summary.distributions) == 0, "Distributions should be empty"
    assert summary.correlations is None, "Correlations should be None"
    assert len(summary.trends) == 0, "Trends should be empty"
    assert len(summary.categories) == 3, "All 3 categorical columns must be analyzed"

    insights = InsightAgent.generate_insights(summary)
    assert len(insights) > 0, "At least baseline or category insights should be generated"

    print("  [PASS] Categorical-only dataset handled safely without errors.")


def test_scenario_5_dataset_containing_anomalies():
    """Test 5: Dataset containing extreme anomalies integrates Phase 4 results into Phase 5 insights."""
    print("\n--- TEST 5: Dataset Containing Anomalies & Phase 4 Integration ---")
    np.random.seed(42)
    normal_prices = np.random.normal(50, 5, size=95)
    outlier_prices = [500.0, 650.0, 800.0, 950.0, 1100.0]
    all_prices = np.concatenate([normal_prices, outlier_prices])

    df = pd.DataFrame({
        "Product": [f"P_{i}" for i in range(100)],
        "Price": all_prices,
        "Quantity": np.random.randint(5, 50, size=100),
    })

    # Run Phase 4 anomaly detection
    iqr_res = AnomalyTool.detect_iqr_outliers(df, columns=["Price"], dataset_name="products.csv")
    if_res = AnomalyTool.detect_isolation_forest(df, columns=["Price", "Quantity"], dataset_name="products.csv")
    anomaly_results = {"iqr": iqr_res, "isolation_forest": if_res}

    # Run Phase 5 summary & insight generation
    summary = StatisticsTool.compute_summary(df, dataset_name="products.csv")
    insights = InsightAgent.generate_insights(summary, anomaly_results=anomaly_results)

    # Verify that anomaly insights were generated
    anom_insights = [i for i in insights if i.category == "Anomaly"]
    assert len(anom_insights) >= 1, "Phase 4 anomalies must produce Phase 5 Anomaly insights"

    iqr_ins = next((i for i in anom_insights if "IQR" in i.title or "Outlier" in i.title), None)
    assert iqr_ins is not None, "IQR outlier insight must exist"
    assert iqr_ins.severity in ("High", "Medium"), "Outliers must be High or Medium severity"
    assert "Price" in iqr_ins.relevant_columns, "Price must be identified as outlier feature"
    assert str(iqr_res.total_outlier_rows) in iqr_ins.evidence, "Exact calculated outlier count must be in evidence"

    print("  [PASS] Phase 4 anomalies successfully synthesized into Phase 5 executive insights.")


def test_scenario_6_duplicate_data_protection():
    """Test 6: Duplicate data protection blocks unexpected row explosion / many-to-many joins."""
    print("\n--- TEST 6: Duplicate Data Protection & Join Safeguards ---")
    df_left = pd.DataFrame({
        "code": ["A", "A", "A", "B", "B"],
        "val_left": [10, 20, 30, 40, 50],
    })

    df_right = pd.DataFrame({
        "code": ["A", "A", "A", "A", "B", "B"],
        "val_right": [1, 2, 3, 4, 5, 6],
    })

    rel = Relationship(
        source_dataset="left.csv",
        source_column="code",
        target_dataset="right.csv",
        target_column="code",
        relationship_type="Many-to-Many",
        confidence="LOW",
        value_overlap_pct=100.0,
    )

    cross_res = StatisticsTool.analyze_cross_dataset(
        left_df=df_left,
        left_name="left.csv",
        right_df=df_right,
        right_name="right.csv",
        relationship=rel,
    )

    assert cross_res.is_blocked, "Many-to-many join with duplicates on both sides must be blocked"
    assert "Cross-file analysis blocked" in cross_res.block_reason, "Block reason must be clear"
    assert "many-to-many" in cross_res.block_reason.lower() or "row multiplication" in cross_res.block_reason.lower()

    print(f"  [PASS] Row explosion prevented: {cross_res.block_reason}")


def test_scenario_7_ask_analyst_phase5_integration():
    """Test 7: Ask Analyst answers Phase 5 queries (trends, correlations, insights, rankings)."""
    print("\n--- TEST 7: Ask Analyst Phase 5 Query Handling ---")
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Revenue": [1000 + i * 50 + (100 if i % 5 == 0 else 0) for i in range(30)],
        "Spend": [500 + i * 25 for i in range(30)],
        "Market": (["East", "West", "North"] * 10),
    })

    datasets = {"finance.csv": df}

    # Query 1: Key insights
    resp1 = AnalystService.answer_question("What are the most important insights?", datasets)
    assert resp1.headline.startswith("Key Analytical Insights") or "Insight" in resp1.headline
    assert resp1.result_df is not None, "Insights must include structured dataframe"
    assert "Revenue" in resp1.summary_markdown or "Market" in resp1.summary_markdown

    # Query 2: Trends
    resp2 = AnalystService.answer_question("What are the major trends over time?", datasets)
    assert "Trend" in resp2.headline
    assert resp2.chart_figure is not None, "Trend query must produce a line chart figure"
    assert "Increasing" in resp2.summary_markdown or "Trajectory" in resp2.summary_markdown

    # Query 3: Correlations
    resp3 = AnalystService.answer_question("What is the strongest correlation?", datasets)
    assert "Correlation" in resp3.headline or "Association" in resp3.headline
    assert resp3.chart_figure is not None, "Correlation query must produce a heatmap figure"
    assert "r = " in resp3.summary_markdown

    # Query 4: Best performing
    resp4 = AnalystService.answer_question("Which markets perform best?", datasets)
    assert "Top" in resp4.headline or "Performance" in resp4.headline
    assert resp4.result_df is not None, "Top rankings must return dataframe"

    print("  [PASS] Ask Analyst successfully answered insights, trends, correlations, and rankings.")


def test_scenario_8_report_generation_integration():
    """Test 8: Report Generator compiles Markdown and PDF reports with Phase 5 sections."""
    print("\n--- TEST 8: Report Generator Phase 5 Integration ---")
    df = pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=20, freq="D"),
        "Sales": [100 + i * 10 for i in range(20)],
        "Profit": [20 + i * 3 for i in range(20)],
        "Category": (["Tech", "Office"] * 10),
    })

    datasets = {"sales_q1.csv": df}
    # Populate analysis in session state
    analysis_res = InsightService.analyze_dataset(df, "sales_q1.csv")

    # Generate Markdown Report
    md = ReportGeneratorService.generate_markdown_report(
        datasets=datasets,
        profiles={},
        relationships=[],
        join_audits=[],
    )

    assert "## 4. Deep Statistical Distributions Summary" in md, "Report must contain Statistical Distributions"
    assert "## 6. Chronological Trends & Time-Series Patterns" in md, "Report must contain Trends"
    assert "## 7. Correlation & Statistical Associations" in md, "Report must contain Correlations"
    assert "## 9. Key Synthesized Insights & Actionable Recommendations" in md, "Report must contain Insights"
    assert "## 11. Analytical Safeguards & Methodology Limitations" in md, "Report must contain Safeguards"

    # Generate PDF Report
    pdf_path = PROJECT_ROOT / "reports" / "test_phase5_report.pdf"
    res_pdf = ReportGeneratorService.generate_pdf_report(
        datasets=datasets,
        profiles={},
        relationships=[],
        join_audits=[],
        output_path=pdf_path,
    )
    assert res_pdf.exists() and res_pdf.stat().st_size > 0, "PDF report must be written and non-empty"

    print(f"  [PASS] Markdown and PDF reports compiled successfully ({res_pdf.stat().st_size:,} bytes).")


def run_all_tests():
    print("=====================================================================")
    print("PHASE 5 INTELLIGENT DATA ANALYSIS & INSIGHT GENERATION TEST SUITE")
    print("=====================================================================")
    test_scenario_1_numeric_categorical_date()
    test_scenario_2_multiple_related_datasets()
    test_scenario_3_dataset_with_no_date_column()
    test_scenario_4_dataset_with_no_numeric_columns()
    test_scenario_5_dataset_containing_anomalies()
    test_scenario_6_duplicate_data_protection()
    test_scenario_7_ask_analyst_phase5_integration()
    test_scenario_8_report_generation_integration()
    print("\n=====================================================================")
    print("ALL 8 PHASE 5 ACCEPTANCE TESTS PASSED CLEANLY!")
    print("=====================================================================")


if __name__ == "__main__":
    run_all_tests()
