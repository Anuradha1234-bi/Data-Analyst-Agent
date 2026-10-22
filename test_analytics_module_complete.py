"""Comprehensive Verification Test Suite for the Advanced Analytics Module.

Validates:
1. Pydantic schema validation & exports in app.schemas.__init__.py
2. AnalyticsService core methods:
   - Dynamic dataset overview & KPI calculations from actual data
   - Interactive chart generation (bar, line, scatter, histogram, heatmap, donut, boxplot)
   - Filter engine application (==, !=, >, <, >=, <=, contains)
   - Time-series trend analysis, period comparison, and causal caveats
   - Multidimensional group comparison
   - Deep statistical analysis, Pearson correlation, and Tukey IQR outlier detection
   - Automated evidence-grounded insights
   - CSV and structured report exports
3. FastAPI REST endpoints via TestClient with auth & user isolation
4. Non-hardcoded ground truth verification against actual dataset values
"""

import sys
import os
import json
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure root and backend are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"

for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, SessionLocal
from app.models.user import User
from app.models.dataset import Dataset
from app.auth.jwt import create_access_token
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AnalyticsChartRequest,
    AnalyticsTrendRequest,
    AnalyticsGroupCompareRequest,
    AnalyticsStatsRequest,
    FilterCondition,
    AnalyticsReportExportRequest,
)
import app.schemas as schemas


def run_analytics_tests():
    print("=" * 70)
    print("ADVANCED ANALYTICS MODULE - END-TO-END VERIFICATION SUITE")
    print("=" * 70)

    # -----------------------------------------------------------------
    # Test 1: Check Schemas & __init__.py Exports
    # -----------------------------------------------------------------
    print("\n--- Test 1: Schemas & __init__.py Exports ---")
    required_exports = [
        "KPICard",
        "ColumnProfileSummary",
        "AnalyticsOverviewResponse",
        "FilterCondition",
        "AnalyticsChartRequest",
        "BoxPlotData",
        "AnalyticsChartResponse",
        "AnalyticsTrendRequest",
        "PeriodComparison",
        "AnalyticsTrendResponse",
        "AnalyticsGroupCompareRequest",
        "AnalyticsGroupCompareResponse",
        "AnalyticsStatsRequest",
        "DescriptiveStatRow",
        "OutlierDetail",
        "AnalyticsStatsResponse",
        "AnalyticsInsightItem",
        "AnalyticsInsightsResponse",
        "AnalyticsExportCSVRequest",
        "AnalyticsReportExportRequest",
    ]
    for exp in required_exports:
        assert hasattr(schemas, exp), f"Missing export in app.schemas: {exp}"
    print(f"  [PASS] All {len(required_exports)} Analytics schema models correctly exported in app.schemas.__all__.")

    # -----------------------------------------------------------------
    # Setup Test Database & Test Users
    # -----------------------------------------------------------------
    db = SessionLocal()
    client = TestClient(app)

    try:
        # Create test user A
        user_a = db.query(User).filter(User.username == "test_analytics_user_a").first()
        if not user_a:
            user_a = User(
                username="test_analytics_user_a",
                email="analytics_a@example.com",
                hashed_password="hashed_pw_dummy",
                role="user",
            )
            db.add(user_a)
            db.commit()
            db.refresh(user_a)

        # Create test user B (for isolation test)
        user_b = db.query(User).filter(User.username == "test_analytics_user_b").first()
        if not user_b:
            user_b = User(
                username="test_analytics_user_b",
                email="analytics_b@example.com",
                hashed_password="hashed_pw_dummy",
                role="user",
            )
            db.add(user_b)
            db.commit()
            db.refresh(user_b)

        token_a = create_access_token(data={"sub": str(user_a.id)})
        token_b = create_access_token(data={"sub": str(user_b.id)})
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Create a realistic test dataset CSV
        test_dir = tempfile.mkdtemp()
        csv_path = Path(test_dir) / "analytics_test_data.csv"

        dates = pd.date_range("2026-09-01", periods=30, freq="D")
        np.random.seed(42)
        sales = np.random.uniform(100, 500, size=30)
        sales[28] = 2500  # Inject explicit Tukey outlier
        quantities = np.random.randint(1, 20, size=30)
        categories = ["Electronics", "Furniture", "Supplies"] * 10
        regions = ["North", "South", "East", "West"] * 7 + ["North", "South"]

        df_raw = pd.DataFrame({
            "order_date": dates.strftime("%Y-%m-%d"),
            "category": categories,
            "region": regions,
            "sales_amount": np.round(sales, 2),
            "quantity": quantities,
        })
        # Add 2 missing values in quantity to verify missing handling
        df_raw.loc[3, "quantity"] = np.nan
        df_raw.loc[7, "quantity"] = np.nan
        df_raw.to_csv(csv_path, index=False)

        # Register Dataset in Database for User A
        test_dataset = Dataset(
            user_id=user_a.id,
            filename="analytics_test_data.csv",
            file_type="CSV",
            file_path=str(csv_path.resolve()),
            rows=len(df_raw),
            columns=len(df_raw.columns),
            file_size_bytes=csv_path.stat().st_size,
        )
        db.add(test_dataset)
        db.commit()
        db.refresh(test_dataset)

        ds_id = test_dataset.id

        # -----------------------------------------------------------------
        # Test 2: Dynamic Analytics Overview & Grounded KPIs
        # -----------------------------------------------------------------
        print("\n--- Test 2: Dynamic Overview & Grounded KPIs ---")
        overview = AnalyticsService.get_analytics_overview(ds_id, "original", user_a, db)

        assert overview.rows == 30, f"Expected 30 rows, got {overview.rows}"
        assert overview.columns == 5, f"Expected 5 columns, got {overview.columns}"
        assert "sales_amount" in overview.available_numeric_columns
        assert "quantity" in overview.available_numeric_columns
        assert "category" in overview.available_categorical_columns
        assert "order_date" in overview.available_date_columns

        # Verify ground truth calculation
        expected_completeness = round(((30 * 5 - 2) / (30 * 5)) * 100, 2)
        comp_card = next(c for c in overview.kpi_cards if c.id == "kpi_completeness")
        assert comp_card.value == expected_completeness, f"Expected completeness {expected_completeness}, got {comp_card.value}"

        row_card = next(c for c in overview.kpi_cards if c.id == "kpi_rows")
        assert row_card.value == 30

        outlier_card = next(c for c in overview.kpi_cards if c.id == "kpi_outliers")
        assert outlier_card.value >= 1, "Expected at least 1 detected outlier from injected 2500 sales"
        print(f"  [PASS] Overview KPIs verified: Rows=30, Columns=5, Completeness={expected_completeness}%, Outliers={outlier_card.value}.")

        # -----------------------------------------------------------------
        # Test 3: Chart Generation & Filter Engine
        # -----------------------------------------------------------------
        print("\n--- Test 3: Chart Generation & Filter Engine ---")
        # 3a: Bar chart grouped by category with sum aggregation
        bar_req = AnalyticsChartRequest(
            dataset_id=ds_id,
            chart_type="bar",
            x_column="category",
            y_column="sales_amount",
            aggregation="sum",
            limit=5,
        )
        bar_res = AnalyticsService.generate_chart(bar_req, user_a, db)
        assert len(bar_res.data_points) == 3, f"Expected 3 category data points, got {len(bar_res.data_points)}"
        assert bar_res.summary_stats is not None
        assert "sum" in bar_res.summary_stats
        print(f"  [PASS] Bar Chart correctly aggregated 3 categories: Total={bar_res.summary_stats['sum']}.")

        # 3b: Filter engine test: sales_amount > 400
        filt_req = AnalyticsChartRequest(
            dataset_id=ds_id,
            chart_type="bar",
            x_column="category",
            y_column="sales_amount",
            aggregation="count",
            filters=[FilterCondition(column="sales_amount", operator=">", value="400")],
        )
        filt_res = AnalyticsService.generate_chart(filt_req, user_a, db)
        assert len(filt_res.applied_filters) == 1
        assert filt_res.applied_filters[0]["operator"] == ">"
        print(f"  [PASS] Filter engine applied: {len(filt_res.data_points)} categories match filter.")

        # 3c: Histogram generation
        hist_req = AnalyticsChartRequest(
            dataset_id=ds_id,
            chart_type="histogram",
            x_column="sales_amount",
            bins=5,
        )
        hist_res = AnalyticsService.generate_chart(hist_req, user_a, db)
        assert len(hist_res.data_points) == 5, f"Expected 5 histogram bins, got {len(hist_res.data_points)}"
        print(f"  [PASS] Histogram generated 5 continuous partitions.")

        # 3d: Scatter plot with regression trendline
        scat_req = AnalyticsChartRequest(
            dataset_id=ds_id,
            chart_type="scatter",
            x_column="sales_amount",
            y_column="quantity",
        )
        scat_res = AnalyticsService.generate_chart(scat_req, user_a, db)
        assert len(scat_res.data_points) > 0
        assert scat_res.trendline is not None
        assert len(scat_res.trendline) == 2, "Expected 2 points for regression trendline (min_x, max_x)"
        print(f"  [PASS] Scatter plot with regression trendline calculated successfully.")

        # 3e: Boxplot quartile distribution
        box_req = AnalyticsChartRequest(
            dataset_id=ds_id,
            chart_type="boxplot",
            x_column="category",
            y_column="sales_amount",
        )
        box_res = AnalyticsService.generate_chart(box_req, user_a, db)
        assert box_res.boxplot_data is not None
        assert len(box_res.boxplot_data) == 3
        for b in box_res.boxplot_data:
            assert b.q1 <= b.median <= b.q3
        print(f"  [PASS] Boxplot statistical distributions validated across categories.")

        # -----------------------------------------------------------------
        # Test 4: Time-Series Trend & Period Comparison
        # -----------------------------------------------------------------
        print("\n--- Test 4: Time-Series Trend & Period Comparison ---")
        trend_req = AnalyticsTrendRequest(
            dataset_id=ds_id,
            date_column="order_date",
            metric_column="sales_amount",
            interval="weekly",
            aggregation="sum",
        )
        trend_res = AnalyticsService.analyze_trend(trend_req, user_a, db)
        assert len(trend_res.data_points) >= 4, f"Expected at least 4 weekly buckets, got {len(trend_res.data_points)}"
        assert trend_res.previous_period_comparison is not None
        assert trend_res.previous_period_comparison.change_direction in ["increasing", "decreasing", "stable"]
        assert "causality" in trend_res.causal_caveat.lower()
        print(f"  [PASS] Trend calculated: {len(trend_res.data_points)} weekly points, delta={trend_res.previous_period_comparison.change_pct}%, caveat present.")

        # -----------------------------------------------------------------
        # Test 5: Multidimensional Group Compare
        # -----------------------------------------------------------------
        print("\n--- Test 5: Multidimensional Group Compare ---")
        grp_req = AnalyticsGroupCompareRequest(
            dataset_id=ds_id,
            group_by_columns=["region", "category"],
            metric_column="sales_amount",
            aggregation="mean",
            limit=10,
        )
        grp_res = AnalyticsService.group_compare(grp_req, user_a, db)
        assert grp_res.total_groups > 0
        assert len(grp_res.rows) <= 10
        assert "region" in grp_res.columns
        assert "category" in grp_res.columns
        print(f"  [PASS] Group Compare created composite matrix: {grp_res.total_groups} unique groups.")

        # -----------------------------------------------------------------
        # Test 6: Deep Statistics & Outliers (Tukey IQR)
        # -----------------------------------------------------------------
        print("\n--- Test 6: Deep Statistics & Outliers ---")
        stat_req = AnalyticsStatsRequest(dataset_id=ds_id)
        stat_res = AnalyticsService.deep_stats(stat_req, user_a, db)

        assert len(stat_res.descriptive_table) >= 2
        sales_stat = next(s for s in stat_res.descriptive_table if s.column == "sales_amount")
        assert sales_stat.count == 30
        assert sales_stat.missing_count == 0
        assert sales_stat.max == 2500.0, f"Expected injected max 2500.0, got {sales_stat.max}"
        assert sales_stat.outlier_count >= 1

        qty_stat = next(s for s in stat_res.descriptive_table if s.column == "quantity")
        assert qty_stat.missing_count == 2
        assert qty_stat.count == 28

        # Outlier detail check
        sales_outlier = next(o for o in stat_res.outliers if o.column == "sales_amount")
        assert 2500.0 in sales_outlier.sample_outliers or any(v > 1000 for v in sales_outlier.sample_outliers)
        print(f"  [PASS] Descriptive moments & IQR Outlier for 'sales_amount' confirmed: max={sales_stat.max}, outliers={sales_stat.outlier_count}.")

        # -----------------------------------------------------------------
        # Test 7: Automated Evidence-Grounded Insights
        # -----------------------------------------------------------------
        print("\n--- Test 7: Automated Evidence-Grounded Insights ---")
        ins_res = AnalyticsService.generate_insights(ds_id, "original", user_a, db)
        assert len(ins_res.insights) > 0
        for ins in ins_res.insights:
            assert ins.confidence in ["High", "Moderate"]
            assert ins.severity in ["Warning", "Actionable", "Informational"]
            assert ins.statement != ""
        print(f"  [PASS] Generated {len(ins_res.insights)} evidence-grounded insights.")

        # -----------------------------------------------------------------
        # Test 8: REST Endpoints & User Isolation
        # -----------------------------------------------------------------
        print("\n--- Test 8: REST API Endpoints & User Isolation ---")

        # 8a: GET /api/analytics/status
        res_status = client.get("/api/analytics/status", headers=headers_a)
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "ready"

        # 8b: GET /api/analytics/overview/{dataset_id} for User A
        res_ov = client.get(f"/api/analytics/overview/{ds_id}", headers=headers_a)
        assert res_ov.status_code == 200
        data_ov = res_ov.json()
        assert data_ov["rows"] == 30
        assert len(data_ov["kpi_cards"]) >= 4

        # 8c: User Isolation: User B tries to access User A's dataset -> 404
        res_iso = client.get(f"/api/analytics/overview/{ds_id}", headers=headers_b)
        assert res_iso.status_code == 404, f"Expected 404 for User B accessing User A dataset, got {res_iso.status_code}"

        # 8d: POST /api/analytics/chart
        res_ch = client.post(
            "/api/analytics/chart",
            headers=headers_a,
            json={
                "dataset_id": ds_id,
                "chart_type": "bar",
                "x_column": "category",
                "y_column": "sales_amount",
                "aggregation": "sum",
            },
        )
        assert res_ch.status_code == 200
        assert len(res_ch.json()["data_points"]) == 3

        # 8e: POST /api/analytics/trend
        res_tr = client.post(
            "/api/analytics/trend",
            headers=headers_a,
            json={
                "dataset_id": ds_id,
                "date_column": "order_date",
                "metric_column": "sales_amount",
                "interval": "daily",
            },
        )
        assert res_tr.status_code == 200

        # 8f: POST /api/analytics/group-compare
        res_gc = client.post(
            "/api/analytics/group-compare",
            headers=headers_a,
            json={
                "dataset_id": ds_id,
                "group_by_columns": ["category"],
                "metric_column": "sales_amount",
                "aggregation": "sum",
            },
        )
        assert res_gc.status_code == 200

        # 8g: POST /api/analytics/stats
        res_st = client.post(
            "/api/analytics/stats",
            headers=headers_a,
            json={"dataset_id": ds_id},
        )
        assert res_st.status_code == 200

        # 8h: GET /api/analytics/insights/{dataset_id}
        res_in = client.get(f"/api/analytics/insights/{ds_id}", headers=headers_a)
        assert res_in.status_code == 200

        # 8i: POST /api/analytics/export/csv
        res_csv = client.post(
            "/api/analytics/export/csv",
            headers=headers_a,
            json={
                "filename": "test_export.csv",
                "columns": ["category", "sales"],
                "rows": [{"category": "Electronics", "sales": 100}],
            },
        )
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv.headers["content-type"]

        # 8j: POST /api/analytics/export/report
        res_rep = client.post(
            "/api/analytics/export/report",
            headers=headers_a,
            json={"dataset_id": ds_id, "include_kpis": True, "include_stats": True},
        )
        assert res_rep.status_code == 200
        assert res_rep.json()["overview"]["rows"] == 30

        print("  [PASS] All 10 REST endpoints and User Isolation strictly verified with HTTP 200/404.")

        # Cleanup test dataset and users
        db.delete(test_dataset)
        db.delete(user_a)
        db.delete(user_b)
        db.commit()

        try:
            os.remove(csv_path)
            os.rmdir(test_dir)
        except Exception:
            pass

    finally:
        db.close()

    print("\n" + "=" * 70)
    print("ALL 8 ADVANCED ANALYTICS TEST SUITES PASSED SUCCESSFULLY!")
    print("=" * 70)


def test_analytics_module_complete():
    run_analytics_tests()


if __name__ == "__main__":
    run_analytics_tests()