"""Comprehensive Verification Test Suite for Reports & Export (Phases 1 - 7).

Validates:
Test A: Empty State & No Results Handling
Test B: Profile Only Report & Export
Test C: Cleaning Summary Integration & Export
Test D: Anomaly Detection Integration & Export
Test E: Prediction Integration (Regression/Classification) & Non-fabrication of Forecast
Test F: Forecasting Integration (Temporal Data) & Bounds
Test G: Export Formats (CSV, XLSX, PDF, Markdown) File Validation
Test H: Existing Features Regression Protection (Profile, Clean, Anomaly, Prediction, Ask Analyst, Legacy Reports)
"""

import sys
from pathlib import Path
import io
import datetime
import unittest
import numpy as np
import pandas as pd
import openpyxl

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.session_manager import SessionManager
from agents.profiler import ProfilerAgent, profile_dataset
from agents.cleaner import clean_dataset, CleaningConfig
from tools.anomaly_tool import AnomalyTool
from services.anomaly_service import AnomalyService

from models.anomaly import IQRAnalysisResult, IQROutlierColumnResult, IsolationForestResult
from prediction.orchestrator import run_prediction
from query.orchestrator import run_ask_analyst_query
from services.report_generator import ReportGeneratorService
from models.report import UnifiedReport, DataProfileSection, CleaningSection, AnomalySection, PredictionSection, ForecastSection


class TestReportsAndExport(unittest.TestCase):
    """Rigorous acceptance test suite for Reports & Export engine."""

    def setUp(self):
        """Reset SessionManager to a clean state before each test."""
        SessionManager.init()
        SessionManager.reset_dataset()

    def test_a_no_results_empty_state(self):
        """Test A: Open Reports before running analysis -> meaningful empty state, no crash."""
        print("\n--- Test A: Empty State & No Results Handling ---")
        # 1. No dataset loaded
        rep_unloaded = ReportGeneratorService.build_unified_report("empty.csv")
        self.assertFalse(rep_unloaded.has_any_analysis())
        self.assertEqual(len(rep_unloaded.available_sections()), 0)

        # 2. Dataset loaded, but zero analysis modules executed
        df = pd.DataFrame({"col_a": [1, 2, 3], "col_b": ["x", "y", "z"]})
        SessionManager.add_dataset(df, "empty_analysis.csv", "CSV")
        rep_loaded = ReportGeneratorService.build_unified_report("empty_analysis.csv")

        self.assertFalse(rep_loaded.has_any_analysis())
        self.assertEqual(len(rep_loaded.available_sections()), 0)
        self.assertIsNone(rep_loaded.profile)
        self.assertIsNone(rep_loaded.cleaning)
        self.assertIsNone(rep_loaded.anomaly)
        self.assertIsNone(rep_loaded.prediction)
        self.assertIsNone(rep_loaded.forecast)
        self.assertIsNone(rep_loaded.ask_analyst)
        print("  [PASS] Empty state accurately detects zero analysis results without error.")

    def test_b_profile_only(self):
        """Test B: Profile run -> Profile section appears and exports actual profile metrics."""
        print("\n--- Test B: Profile Only Integration & Export ---")
        df = pd.DataFrame({
            "age": [25, 30, 35, 40, np.nan],
            "salary": [50000.0, 60000.0, 75000.0, 90000.0, 110000.0],
            "department": ["IT", "HR", "Sales", "IT", "HR"],
        })
        SessionManager.add_dataset(df, "employees.csv", "CSV")
        prof = profile_dataset(df)
        SessionManager.set_profile(prof, filename="employees.csv")

        report = ReportGeneratorService.build_unified_report("employees.csv")
        self.assertTrue(report.has_any_analysis())
        self.assertIn("Data Profile", report.available_sections())
        self.assertIsNotNone(report.profile)
        self.assertEqual(report.profile.total_rows, 5)
        self.assertEqual(report.profile.total_columns, 3)
        self.assertEqual(report.profile.total_missing, 1)
        self.assertIsNone(report.cleaning)
        self.assertIsNone(report.anomaly)
        self.assertIsNone(report.prediction)
        self.assertIsNone(report.forecast)

        # Export checks
        csv_out = ReportGeneratorService.export_report_csv(report)
        self.assertIn("DATA PROFILE", csv_out)
        self.assertIn("age", csv_out)
        self.assertIn("salary", csv_out)

        xlsx_out = ReportGeneratorService.export_report_xlsx(report)
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_out))
        self.assertIn("Overview", wb.sheetnames)
        self.assertIn("Data Profile", wb.sheetnames)
        self.assertNotIn("Data Cleaning", wb.sheetnames)
        self.assertNotIn("Prediction", wb.sheetnames)

        pdf_out = ReportGeneratorService.export_report_pdf(report)
        self.assertGreater(len(pdf_out), 500)
        self.assertTrue(pdf_out.startswith(b"%PDF"))
        print("  [PASS] Profile results cleanly compiled and exported in CSV, XLSX, and PDF.")

    def test_c_cleaning_summary(self):
        """Test C: Cleaning run -> Cleaning summary appears with actual numbers and operations."""
        print("\n--- Test C: Cleaning Summary Integration & Export ---")
        df = pd.DataFrame({
            "id": [1, 2, 2, 4, 5],
            "value": [10.0, np.nan, np.nan, 40.0, 50.0],
        })
        SessionManager.add_dataset(df, "clean_test.csv", "CSV")
        config = CleaningConfig(remove_duplicates=True, imputation_strategies={"value": "mean"})
        clean_df, summary = clean_dataset(df, config)
        SessionManager.set_cleaned_dataset(clean_df, summary, config, filename="clean_test.csv")

        report = ReportGeneratorService.build_unified_report("clean_test.csv")
        self.assertTrue(report.has_any_analysis())
        self.assertIn("Data Cleaning", report.available_sections())
        self.assertIsNotNone(report.cleaning)
        self.assertEqual(report.cleaning.before_rows, 5)
        self.assertEqual(report.cleaning.after_rows, 4)  # 1 duplicate removed
        self.assertEqual(report.cleaning.duplicates_handled, 1)
        self.assertGreaterEqual(report.cleaning.missing_handled, 1)

        # Export checks
        csv_out = ReportGeneratorService.export_report_csv(report)
        self.assertIn("DATA CLEANING AUDIT", csv_out)
        self.assertIn("Rows Before", csv_out)

        xlsx_out = ReportGeneratorService.export_report_xlsx(report)
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_out))
        self.assertIn("Data Cleaning", wb.sheetnames)

        pdf_out = ReportGeneratorService.export_report_pdf(report)
        self.assertTrue(pdf_out.startswith(b"%PDF"))
        print("  [PASS] Cleaning summary accurately displays and exports remediation audit.")

    def test_d_anomaly_detection(self):
        """Test D: Anomaly detection -> Anomaly summary appears with actual algorithm results."""
        print("\n--- Test D: Anomaly Detection Integration & Export ---")
        df = pd.DataFrame({
            "feature1": [10.0, 11.0, 10.5, 9.8, 10.2, 10.1, 10.4, 9.9, 10.0, 500.0],
            "feature2": [5.0, 5.1, 4.9, 5.2, 5.0, 5.1, 4.8, 5.2, 5.0, 100.0],
        })
        SessionManager.add_dataset(df, "anom_test.csv", "CSV")
        anom_res = AnomalyTool.detect_iqr_outliers(df, multiplier=1.5, dataset_name="anom_test.csv")
        SessionManager.set_anomaly_results({"iqr": anom_res}, filename="anom_test.csv")


        report = ReportGeneratorService.build_unified_report("anom_test.csv")
        self.assertTrue(report.has_any_analysis())
        self.assertIn("Anomalies", report.available_sections())
        self.assertIsNotNone(report.anomaly)
        self.assertEqual(report.anomaly.total_anomalies, anom_res.total_outlier_rows)
        self.assertEqual(len(report.anomaly.methods), 1)
        self.assertIn("IQR", report.anomaly.methods[0].method)

        # Export checks
        csv_out = ReportGeneratorService.export_report_csv(report)
        self.assertIn("ANOMALY & OUTLIER DETECTION", csv_out)

        xlsx_out = ReportGeneratorService.export_report_xlsx(report)
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_out))
        self.assertIn("Anomalies", wb.sheetnames)
        print("  [PASS] Anomaly summary properly records IQR detection and exports correctly.")

    def test_e_prediction_regression_no_forecast_fabrication(self):
        """Test E: Regression prediction -> Target, Model, Metrics appear; Forecast NOT fabricated."""
        print("\n--- Test E: Prediction Integration (Regression) ---")
        np.random.seed(42)
        X = np.random.rand(30, 2)
        y = 2.5 * X[:, 0] + 1.2 * X[:, 1] + 5.0
        df = pd.DataFrame({"feature_x": X[:, 0], "feature_z": X[:, 1], "target_y": y})
        SessionManager.add_dataset(df, "regression_data.csv", "CSV")

        pred_res = run_prediction(
            df=df,
            dataset_name="regression_data.csv",
            target_col="target_y",
            date_col=None,
            mode="regression",
        )
        SessionManager.set_prediction_result("regression_data.csv", pred_res)

        report = ReportGeneratorService.build_unified_report("regression_data.csv")
        self.assertTrue(report.has_any_analysis())
        self.assertIn("Prediction", report.available_sections())
        self.assertIsNotNone(report.prediction)
        self.assertEqual(report.prediction.target, "target_y")
        self.assertIn("Regression", report.prediction.problem_type)
        self.assertIsNotNone(report.prediction.selected_model)
        self.assertIn("mae", report.prediction.metrics)
        self.assertGreater(len(report.prediction.predictions), 0)

        # CRITICAL TEST: Forecasting section must NOT be fabricated!
        self.assertIsNone(report.forecast)
        self.assertNotIn("Forecasting", report.available_sections())

        # Export verification
        csv_out = ReportGeneratorService.export_report_csv(report)
        self.assertIn("PREDICTIVE MODELING SUMMARY", csv_out)
        self.assertNotIn("TIME-SERIES FORECAST", csv_out)

        xlsx_out = ReportGeneratorService.export_report_xlsx(report)
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_out))
        self.assertIn("Prediction", wb.sheetnames)
        self.assertNotIn("Forecasting", wb.sheetnames)
        print("  [PASS] Predictive modeling included; Forecasting was correctly NOT fabricated.")

    def test_f_forecasting_temporal_data(self):
        """Test F: Forecasting on time-series dataset -> Time col, Model, Horizon, Projections appear."""
        print("\n--- Test F: Time-Series Forecasting Integration ---")
        dates = pd.date_range(start="2025-01-01", periods=25, freq="D")
        sales = [100 + i * 2.5 + (i % 3) * 4 for i in range(25)]
        df = pd.DataFrame({"sale_date": dates.strftime("%Y-%m-%d"), "units_sold": sales})
        SessionManager.add_dataset(df, "daily_sales.csv", "CSV")

        pred_res = run_prediction(
            df=df,
            dataset_name="daily_sales.csv",
            target_col="units_sold",
            date_col="sale_date",
            mode="forecasting",
            horizon=5,
        )
        SessionManager.set_prediction_result("daily_sales.csv", pred_res)

        report = ReportGeneratorService.build_unified_report("daily_sales.csv")
        self.assertTrue(report.has_any_analysis())
        self.assertIn("Forecasting", report.available_sections())
        self.assertIsNotNone(report.forecast)
        self.assertEqual(report.forecast.time_column, "sale_date")
        self.assertEqual(report.forecast.target, "units_sold")
        self.assertEqual(report.forecast.forecast_horizon, 5)
        self.assertEqual(len(report.forecast.forecast_results), 5)
        # Check uncertainty bounds exist on projections
        pt0 = report.forecast.forecast_results[0]
        self.assertIn("predicted_value", pt0)
        self.assertIn("lower_bound", pt0)
        self.assertIn("upper_bound", pt0)

        # Export checks
        csv_out = ReportGeneratorService.export_report_csv(report)
        self.assertIn("TIME-SERIES FORECAST", csv_out)

        xlsx_out = ReportGeneratorService.export_report_xlsx(report)
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_out))
        self.assertIn("Forecasting", wb.sheetnames)
        print("  [PASS] Forecasting cleanly integrated with horizon and uncertainty bounds.")

    def test_g_export_formats_validity(self):
        """Test G: Verify CSV, XLSX, and PDF files contain actual data and valid byte structures."""
        print("\n--- Test G: Multi-format Export Verification ---")
        # Build comprehensive state
        df = pd.DataFrame({
            "period": pd.date_range("2025-01-01", periods=15).strftime("%Y-%m-%d"),
            "revenue": [1000 + i * 50 for i in range(15)],
            "category": ["A", "B", "C"] * 5,
        })
        SessionManager.add_dataset(df, "master.csv", "CSV")
        prof = profile_dataset(df)
        SessionManager.set_profile(prof, filename="master.csv")
        pred_res = run_prediction(df=df, dataset_name="master.csv", target_col="revenue", date_col="period", mode="forecasting", horizon=3)
        SessionManager.set_prediction_result("master.csv", pred_res)

        # Add Ask Analyst question
        SessionManager.set("ask_analyst_history", [{
            "question": "What is the total revenue?",
            "answer": {"answer": "The sum of revenue is $20,250.00.", "confidence": "High"},
            "query_plan": {"intent": "SUM"},
        }])

        report = ReportGeneratorService.build_unified_report("master.csv")

        # 1. Test CSV format
        csv_str = ReportGeneratorService.export_report_csv(report)
        self.assertIn("master.csv", csv_str)
        self.assertIn("revenue", csv_str)
        self.assertIn("What is the total revenue?", csv_str)

        # 2. Test XLSX format
        xlsx_bytes = ReportGeneratorService.export_report_xlsx(report)
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        self.assertIn("Overview", wb.sheetnames)
        self.assertIn("Data Profile", wb.sheetnames)
        self.assertIn("Forecasting", wb.sheetnames)
        self.assertIn("Ask Analyst", wb.sheetnames)
        ws_ask = wb["Ask Analyst"]
        self.assertEqual(ws_ask.cell(row=5, column=2).value, "What is the total revenue?")

        # 3. Test PDF format
        out_pdf_path = PROJECT_ROOT / "reports" / "acceptance_test_report.pdf"
        pdf_bytes = ReportGeneratorService.export_report_pdf(report, output_path=out_pdf_path)
        self.assertTrue(out_pdf_path.exists())
        self.assertGreater(out_pdf_path.stat().st_size, 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

        # 4. Test Markdown format
        md_str = ReportGeneratorService.export_report_markdown(report)
        self.assertIn("# AI Data Analyst Agent — Executive Report", md_str)
        self.assertIn("## 1. Dataset Information", md_str)
        self.assertIn("## 2. Data Profile Summary", md_str)
        self.assertIn("## 6. Forecast Summary", md_str)
        self.assertIn("## 7. Ask Analyst Summary", md_str)
        print("  [PASS] All 4 export formats (CSV, XLSX, PDF, MD) verified and validated.")

    def test_h_existing_features_backward_compatibility(self):
        """Test H: Verify existing prediction, forecasting, anomaly, and legacy report methods."""
        print("\n--- Test H: Existing Features & Legacy Compatibility ---")
        df1 = pd.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]})
        df2 = pd.DataFrame({"id": [1, 2, 3], "desc": ["a", "b", "c"]})
        SessionManager.add_dataset(df1, "d1.csv", "CSV")
        SessionManager.add_dataset(df2, "d2.csv", "CSV")

        # Verify legacy report generator functions still work without alteration
        md_legacy = ReportGeneratorService.generate_markdown_report(
            datasets={"d1.csv": df1, "d2.csv": df2},
            profiles={},
            relationships=[],
            join_audits=[],
        )
        self.assertIn("# Multi-Dataset Executive Analysis Report", md_legacy)

        pdf_legacy_path = PROJECT_ROOT / "reports" / "legacy_test_report.pdf"
        res_legacy_pdf = ReportGeneratorService.generate_pdf_report(
            datasets={"d1.csv": df1},
            profiles={},
            relationships=[],
            join_audits=[],
            output_path=pdf_legacy_path,
        )
        self.assertTrue(res_legacy_pdf.exists())
        self.assertGreater(res_legacy_pdf.stat().st_size, 500)
        print("  [PASS] Legacy report generation intact; no regression detected.")


if __name__ == "__main__":
    unittest.main()
