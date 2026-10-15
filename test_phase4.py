"""Comprehensive Phase 4 Anomaly Detection Verification Suite.

Tests all 7 required scenarios:
1. One numeric dataset
2. One mixed numeric/categorical dataset
3. Multiple datasets (independent state & preservation)
4. Dataset with missing values
5. Dataset with obvious extreme values
6. Dataset with no numeric columns
7. Dataset containing ID/index columns
"""

import sys
import numpy as np
import pandas as pd

from tools.anomaly_tool import AnomalyTool
from services.anomaly_service import AnomalyService
from core.session_manager import SessionManager
from services.analyst import AnalystService
from services.report_generator import ReportGeneratorService


def test_1_numeric_dataset():
    print("\n--- Test 1: One Numeric Dataset ---")
    np.random.seed(42)
    df = pd.DataFrame({
        "revenue": np.concatenate([np.random.normal(1000, 100, 95), [5000, 6000, 50, 40, 7000]]),
        "units_sold": np.concatenate([np.random.normal(50, 5, 95), [200, 250, 2, 1, 300]]),
        "profit_margin": np.concatenate([np.random.normal(0.2, 0.02, 95), [0.8, 0.9, -0.2, -0.3, 0.95]]),
    })

    # Test IQR
    iqr_res = AnomalyTool.detect_iqr_outliers(df, multiplier=1.5, dataset_name="numeric_test.csv")
    assert iqr_res.total_outlier_rows > 0, "IQR should detect outliers"
    print(f"  [PASS] IQR detected {iqr_res.total_outlier_rows} outlier rows ({iqr_res.outlier_rate}%)")
    for col, r in iqr_res.column_results.items():
        assert r.lower_bound < r.upper_bound, f"Bounds invalid for {col}"
        assert r.total_outliers == (r.lower_outliers_count + r.upper_outliers_count)
        print(f"         {col}: Bounds [{r.lower_bound:.2f}, {r.upper_bound:.2f}], Outliers: {r.total_outliers}")

    # Test Isolation Forest
    if_res = AnomalyTool.detect_isolation_forest(df, contamination=0.05, dataset_name="numeric_test.csv")
    assert if_res.anomaly_count > 0, "Isolation Forest should detect anomalies"
    assert len(if_res.features_used) == 3, "All 3 numeric features should be modeled"
    print(f"  [PASS] Isolation Forest flagged {if_res.anomaly_count} anomalies ({if_res.anomaly_pct}%)")

    # Test Deep Statistics
    ds_res = AnomalyTool.compute_deep_statistics(df, dataset_name="numeric_test.csv")
    assert len(ds_res.column_metrics) == 3, "All 3 columns should have statistics"
    print(f"  [PASS] Deep Statistics evaluated {len(ds_res.column_metrics)} columns, {ds_res.unusual_columns_count} statistically unusual")

    # Test Multivariate
    mv_res = AnomalyTool.compute_multivariate_anomalies(df, columns=["revenue", "units_sold"], contamination=0.05)
    assert mv_res.anomaly_count > 0, "Multivariate should detect anomalies"
    print(f"  [PASS] Multivariate detected {mv_res.anomaly_count} anomalies across 2 features")
    for anom in mv_res.anomalies[:2]:
        assert len(anom.signals) > 0, "Anomaly record must have calculated signals"
        print(f"         Row {anom.row_index} signals: {anom.signals[0]}")


def test_2_mixed_dataset():
    print("\n--- Test 2: Mixed Numeric/Categorical Dataset ---")
    df = pd.DataFrame({
        "product_name": ["Widget A", "Widget B", "Gadget C", "Tool D", "Ultra Device"] * 20,
        "region": ["North", "South", "East", "West", "Central"] * 20,
        "price": np.concatenate([np.random.normal(50, 5, 95), [500, 600, 2, 1, 700]]),
        "quantity": np.concatenate([np.random.normal(20, 3, 95), [150, 180, 0, 1, 200]]),
    })

    suitable, excluded_ids, excluded_other = AnomalyTool.identify_suitable_features(df)
    assert "price" in suitable and "quantity" in suitable, "Numeric features must be suitable"
    assert any("product_name" in s for s in excluded_other), "Categorical product_name must be excluded"
    assert any("region" in s for s in excluded_other), "Categorical region must be excluded"
    print(f"  [PASS] Suitable features: {suitable}")
    print(f"  [PASS] Excluded non-numeric: {[s.split(' ')[0] for s in excluded_other]}")

    # Isolation Forest on mixed dataset (should auto-filter categoricals)
    if_res = AnomalyTool.detect_isolation_forest(df, dataset_name="mixed_test.csv")
    assert set(if_res.features_used) == {"price", "quantity"}
    print(f"  [PASS] Isolation Forest ran safely on mixed data: {if_res.anomaly_count} anomalies")


def test_3_multiple_datasets():
    print("\n--- Test 3: Multiple Datasets (Independence & Safety) ---")
    sales_df = pd.DataFrame({
        "order_id": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        "amount": [100, 110, 105, 120, 115, 108, 112, 118, 107, 5000],
    })
    customers_df = pd.DataFrame({
        "cust_id": [1, 2, 3, 4, 5],
        "score": [80, 85, 90, 88, 92],
    })

    # Register in SessionManager
    SessionManager.init()
    SessionManager.add_dataset(sales_df, "sales.csv", "CSV")
    SessionManager.add_dataset(customers_df, "customers.csv", "CSV")

    orig_customers = SessionManager.get_original_df("customers.csv")
    orig_customers_rows = len(orig_customers)

    # Run detection on sales.csv
    sales_iqr = AnomalyService.run_iqr_detection(sales_df, "sales.csv", columns=["amount"])
    assert sales_iqr.total_outlier_rows == 1, "Should detect 1 outlier in sales amount (5000)"

    # Verify customers.csv is completely unmodified
    curr_customers = SessionManager.get_dataset_by_name("customers.csv", view="active")
    assert len(curr_customers) == orig_customers_rows, "customers.csv must not be modified"
    assert "score" in curr_customers.columns and len(curr_customers.columns) == 2

    # Check anomaly results are separated
    sales_res = SessionManager.get_anomaly_results("sales.csv")
    cust_res = SessionManager.get_anomaly_results("customers.csv")
    assert sales_res is not None and "iqr" in sales_res
    assert cust_res is None or "iqr" not in cust_res, "Customers results must not be contaminated"
    print("  [PASS] Running detection on sales.csv did not affect customers.csv")
    print(f"  [PASS] sales.csv results independent: {sales_res['iqr'].total_outlier_rows} outliers detected")


def test_4_dataset_with_missing_values():
    print("\n--- Test 4: Dataset With Missing Values ---")
    df = pd.DataFrame({
        "metric_a": [10.0, np.nan, 12.0, 11.0, 13.0, np.nan, 11.0, 12.0, 14.0, 500.0],
        "metric_b": [20.0, 22.0, np.nan, 21.0, 23.0, 20.0, 22.0, np.nan, 24.0, 800.0],
    })

    # IQR test with NaNs
    iqr_res = AnomalyTool.detect_iqr_outliers(df, multiplier=1.5, dataset_name="missing_test.csv")
    assert iqr_res.total_outlier_rows > 0
    print(f"  [PASS] IQR handled NaNs safely: {iqr_res.total_outlier_rows} outlier rows")

    # Isolation Forest test with NaNs (must impute safely without altering input df)
    nan_count_before = int(df.isna().sum().sum())
    if_res = AnomalyTool.detect_isolation_forest(df, dataset_name="missing_test.csv")
    nan_count_after = int(df.isna().sum().sum())
    assert nan_count_before == nan_count_after, "Underlying DataFrame must not have NaNs altered"
    assert any("Imputed" in note for note in if_res.preprocessing_notes), "Notes must record imputation"
    print(f"  [PASS] Isolation Forest safely imputed NaNs during training (Input NaNs preserved: {nan_count_after})")


def test_5_dataset_with_extreme_values():
    print("\n--- Test 5: Dataset With Obvious Extreme Values ---")
    base_vals = [100.0] * 30 + [102.0] * 30 + [98.0] * 30
    extreme_vals = [-9999.0, 99999.0]
    df = pd.DataFrame({"cost": base_vals + extreme_vals})

    iqr_res = AnomalyTool.detect_iqr_outliers(df, columns=["cost"], multiplier=1.5)
    cost_res = iqr_res.column_results["cost"]
    assert cost_res.lower_outliers_count == 1, "Must detect -9999 as lower outlier"
    assert cost_res.upper_outliers_count == 1, "Must detect 99999 as upper outlier"
    print(f"  [PASS] IQR correctly split outliers: {cost_res.lower_outliers_count} lower, {cost_res.upper_outliers_count} upper")

    # Test Winsorization / Capping
    treated_df, summary = AnomalyTool.apply_treatment(
        df=df,
        treatment_type="cap_values",
        outlier_indices=iqr_res.all_outlier_indices,
        columns=["cost"],
        dataset_name="extreme.csv",
    )
    assert treated_df["cost"].min() >= cost_res.lower_bound, "Min must be capped to lower bound"
    assert treated_df["cost"].max() <= cost_res.upper_bound, "Max must be capped to upper bound"
    assert summary.affected_rows == 2, "2 extreme cells must be capped"
    print(f"  [PASS] Winsorization capped cost to [{cost_res.lower_bound:.2f}, {cost_res.upper_bound:.2f}]")


def test_6_no_numeric_columns():
    print("\n--- Test 6: Dataset With No Numeric Columns ---")
    df = pd.DataFrame({
        "color": ["Red", "Green", "Blue", "Yellow"],
        "category": ["Clothing", "Footwear", "Accessories", "Electronics"],
        "city": ["New York", "London", "Tokyo", "Paris"],
    })

    suitable, excluded_ids, excluded_other = AnomalyTool.identify_suitable_features(df)
    assert len(suitable) == 0, "No suitable numeric features should be found"
    assert len(excluded_other) == 3, "All 3 columns should be categorized as non-numeric"
    print(f"  [PASS] Correctly detected 0 numeric features and excluded {len(excluded_other)} non-numeric features")

    # IQR on non-numeric returns 0 analyzed without crash
    iqr_res = AnomalyTool.detect_iqr_outliers(df)
    assert iqr_res.total_outlier_rows == 0
    print("  [PASS] IQR handled categorical-only dataframe gracefully (0 outliers)")

    # Isolation Forest raises clear, informative ValueError
    try:
        AnomalyTool.detect_isolation_forest(df)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "No suitable numeric features" in str(e)
        print(f"  [PASS] Isolation Forest raised informative error: {str(e)[:60]}...")


def test_7_dataset_with_id_index_columns():
    print("\n--- Test 7: Dataset With ID / Index Columns ---")
    df = pd.DataFrame({
        "Unnamed: 0": list(range(50)),
        "order_id": [1000 + i for i in range(50)],
        "transaction_code": [f"TXN_{i}" for i in range(50)],
        "customer_id": list(range(1, 51)),
        "index": list(range(50)),
        "price": np.concatenate([np.random.normal(100, 10, 48), [1500, 2000]]),
        "quantity": np.concatenate([np.random.normal(5, 1, 48), [50, 75]]),
    })

    suitable, excluded_ids, excluded_other = AnomalyTool.identify_suitable_features(df)
    assert "price" in suitable and "quantity" in suitable, "Price and Quantity must be suitable"
    assert len(suitable) == 2, f"Only price and quantity should be suitable, got {suitable}"

    excluded_names = [e[:e.rfind(" (")] if " (" in e else e for e in excluded_ids]
    assert "Unnamed: 0" in excluded_names, "Unnamed: 0 must be excluded"
    assert "order_id" in excluded_names, "order_id must be excluded"
    assert "customer_id" in excluded_names, "customer_id must be excluded"
    assert "index" in excluded_names, "index must be excluded"
    print(f"  [PASS] ID columns successfully identified and excluded: {excluded_names}")
    print(f"  [PASS] Only true domain metrics selected: {suitable}")


def test_analyst_and_report_integration():
    print("\n--- Integration Test: Ask Analyst & Report Generator ---")
    df = pd.DataFrame({
        "product": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"] * 10,
        "price": np.concatenate([np.random.normal(50, 5, 48), [500.0, 750.0]]),
        "quantity": np.concatenate([np.random.normal(10, 2, 48), [80.0, 100.0]]),
    })

    # Test Ask Analyst anomaly query
    resp1 = AnalystService.answer_question("Which products have unusual prices?", {"inventory.csv": df})
    assert resp1.result_df is not None and not resp1.result_df.empty, "Analyst should return result dataframe"
    assert "unusual" in resp1.headline.lower() or "price" in resp1.headline.lower()
    assert resp1.chart_figure is not None, "Analyst should generate box plot"
    print(f"  [PASS] Ask Analyst handled 'Which products have unusual prices?': {resp1.headline}")

    resp2 = AnalystService.answer_question("Which columns contain the most outliers?", {"inventory.csv": df})
    assert resp2.result_df is not None and not resp2.result_df.empty
    print(f"  [PASS] Ask Analyst handled 'Which columns contain the most outliers?': {resp2.headline}")

    resp3 = AnalystService.answer_question("Show me unusual price and quantity combinations", {"inventory.csv": df})
    assert resp3.result_df is not None
    print(f"  [PASS] Ask Analyst handled multivariate combinations query: {resp3.headline}")

    # Test Report Generator markdown includes anomaly section
    SessionManager.set_anomaly_results({"iqr": AnomalyTool.detect_iqr_outliers(df)}, "inventory.csv")
    md_report = ReportGeneratorService.generate_markdown_report(
        datasets={"inventory.csv": df},
        profiles={},
        relationships=[],
        join_audits=[],
    )
    assert "Statistical Anomaly & Outlier Analysis" in md_report, "Report must include anomaly section"
    assert "IQR Outlier Detection" in md_report
    print("  [PASS] Markdown report successfully incorporates Statistical Anomaly & Outlier Analysis section")


if __name__ == "__main__":
    test_1_numeric_dataset()
    test_2_mixed_dataset()
    test_3_multiple_datasets()
    test_4_dataset_with_missing_values()
    test_5_dataset_with_extreme_values()
    test_6_no_numeric_columns()
    test_7_dataset_with_id_index_columns()
    test_analyst_and_report_integration()
    print("\n==========================================")
    print("ALL 7 PHASE 4 SCENARIOS & INTEGRATION TESTS PASSED!")
    print("==========================================")
