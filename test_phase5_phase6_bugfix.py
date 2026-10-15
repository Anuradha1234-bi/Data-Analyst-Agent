"""End-to-End Verification Test for Bug 1 and Bug 2 Stabilization.

Validates:
Test A - Fresh App: No prediction executed -> SessionManager.get_prediction_results() returns empty dict, no AttributeError.
Test B - Integer Dataset: Integer columns -> TargetDetector works, no float.is_integer TypeError.
Test C - Float Dataset: Float columns (including integer-like floats and fractional floats) handled correctly.
Test D - CGPA Dataset: Target recommendations appear (CGPA/regression), no forced forecasting.
Test E - Prediction Pipeline: Target -> Model -> Metrics -> Prediction works end-to-end.
Test F - Ask Analyst After Prediction: Stored results retrieved, Ask Analyst generates grounded forecast/prediction response.
Test G - No Results: Empty prediction state -> Ask Analyst generates meaningful 'no prediction results yet' message.
Test H - Existing Ask Analyst features: Count, average, trend, etc. continue working without regression.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.session_manager import SessionManager
from models.prediction import ProblemType, PredictionResult
from prediction.target_detector import TargetDetector
from prediction.problem_detector import ProblemDetector
from prediction.orchestrator import run_prediction
from query.orchestrator import run_ask_analyst_query
from query.query_executor import execute_query
from query.answer_generator import generate_query_answer


class TestBugFixAndStabilization(unittest.TestCase):
    """Test suite for targeted bug fixes and end-to-end flow."""

    def test_a_fresh_app_no_attribute_error(self):
        """Test A: Fresh app with no predictions executed returns empty dict, no AttributeError."""
        # Ensure SessionManager has get_prediction_results
        self.assertTrue(hasattr(SessionManager, "get_prediction_results"))
        res = SessionManager.get_prediction_results()
        self.assertIsInstance(res, dict)
        self.assertEqual(len(res), 0)

        # Asking a forecast question when no prediction exists
        df = pd.DataFrame({"sales": [100.0, 150.0, 200.0]})
        plan = {"intent": "forecast", "dataset": "test.csv", "column": "sales", "confidence": 0.9}
        exec_res = execute_query(query_plan=plan, datasets={"test.csv": df}, phase5_results=res)
        ans = generate_query_answer("What is the sales forecast?", plan, exec_res, exec_res["evidence"])
        self.assertIn("no prediction results are available yet", ans["answer"].lower())

    def test_b_integer_dataset(self):
        """Test B: TargetDetector executes on integer columns without float.is_integer TypeError."""
        df = pd.DataFrame({
            "col_int1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "col_int2": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            "category_int": [1, 2, 3, 1, 2, 3, 1, 2, 3, 1],
        })
        # Must execute cleanly without TypeError
        recs = TargetDetector.detect_targets(df)
        self.assertGreater(len(recs), 0)
        rec_map = {r.column: r for r in recs}
        self.assertIn("category_int", rec_map)
        self.assertEqual(rec_map["category_int"].problem_type, ProblemType.MULTICLASS_CLASSIFICATION)

    def test_c_float_dataset_and_integer_like(self):
        """Test C: TargetDetector handles integer-like floats and fractional floats correctly."""
        df = pd.DataFrame({
            "float_int": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0],
            "float_fractional": [1.25, 2.50, 3.75, 4.10, 5.85, 6.20, 7.45, 8.90, 9.15, 10.30],
            "price_measure": [100.5, 102.3, 101.8, 105.0, 108.2, 107.1, 110.4, 112.0, 115.3, 118.7],
        })
        recs = TargetDetector.detect_targets(df)
        rec_map = {r.column: r for r in recs}
        # float_int has 3 discrete classes and is integer-like
        self.assertEqual(rec_map["float_int"].problem_type, ProblemType.MULTICLASS_CLASSIFICATION)
        # float_fractional has decimals -> regression
        self.assertEqual(rec_map["float_fractional"].problem_type, ProblemType.REGRESSION)
        # price_measure is regression
        self.assertEqual(rec_map["price_measure"].problem_type, ProblemType.REGRESSION)

    @staticmethod
    def _get_cgpa_test_df():
        return pd.DataFrame({
            "Name": ["Amit", "Sneha", "Rahul", "Priya", "Karan", "Neha", "Arjun", "Pooja", "Vikas", "Anjali"],
            "CGPA": [5.0, 5.5, 6.0, 6.2, 6.5, 6.8, 7.0, 7.2, 7.5, 7.8],
            "Package": [3.0, 3.2, 3.5, 3.7, 4.0, 4.2, 4.5, 4.8, 5.2, 5.5],
        })

    def test_d_cgpa_dataset(self):
        """Test D: cgpa.csv loads without error, detects regression, no forced forecasting."""
        df = self._get_cgpa_test_df()
        self.assertEqual(len(df), 10)
        self.assertIn("CGPA", df.columns)

        # Detect targets
        recs = TargetDetector.detect_targets(df)
        self.assertGreater(len(recs), 0)
        rec_map = {r.column: r for r in recs}
        self.assertIn("CGPA", rec_map)
        self.assertEqual(rec_map["CGPA"].problem_type, ProblemType.REGRESSION)
        self.assertEqual(rec_map["CGPA"].score, 1.0)

        # Problem type detector with auto mode and no date column
        prob_type = ProblemDetector.detect_problem_type(df, target_col="CGPA", date_col=None, requested_mode="auto")
        self.assertEqual(prob_type, ProblemType.REGRESSION)

        # Date detector returns empty (no temporal structure)
        date_cols = TargetDetector.detect_date_columns(df)
        self.assertEqual(len(date_cols), 0)

    def test_e_prediction_pipeline_on_cgpa(self):
        """Test E: Prediction pipeline on cgpa dataset produces valid regression model and metrics."""
        df = self._get_cgpa_test_df()

        pred_result = run_prediction(
            df=df,
            dataset_name="cgpa_dataset.csv",
            target_col="CGPA",
            date_col=None,
            mode="regression",
            horizon=7,
        )

        self.assertEqual(pred_result.status, "success")
        self.assertEqual(pred_result.mode, "regression")
        self.assertEqual(pred_result.problem_type, "regression")
        self.assertIsNotNone(pred_result.selected_model_name)
        self.assertIsNotNone(pred_result.best_metrics.mae)
        self.assertGreater(len(pred_result.predictions), 0)

        # Verify lower and upper bounds exist
        pt0 = pred_result.predictions[0]
        self.assertIsNotNone(pt0.predicted_value)
        self.assertIsNotNone(pt0.lower_bound)
        self.assertIsNotNone(pt0.upper_bound)

    def test_f_ask_analyst_after_prediction(self):
        """Test F: Ask Analyst consumes PredictionResult and produces grounded response."""
        df = self._get_cgpa_test_df()

        pred_result = run_prediction(
            df=df,
            dataset_name="cgpa_dataset.csv",
            target_col="CGPA",
            date_col=None,
            mode="regression",
            horizon=7,
        )

        p5_results = {"cgpa_dataset.csv": pred_result}

        # Query forecast/prediction for CGPA
        plan = {
            "intent": "prediction",
            "dataset": "cgpa_dataset.csv",
            "column": "CGPA",
            "confidence": 0.95,
        }
        exec_res = execute_query(query_plan=plan, datasets={"cgpa_dataset.csv": df}, phase5_results=p5_results)
        self.assertEqual(exec_res["status"], "success")
        self.assertEqual(exec_res["result_type"], "table")

        # Verify evidence contains all required fields (AC-1.4)
        ev = exec_res["evidence"]
        self.assertEqual(ev["dataset"], "cgpa_dataset.csv")
        self.assertEqual(ev["target_column"], "CGPA")
        self.assertEqual(ev["problem_type"], "regression")
        self.assertEqual(ev["selected_model"], pred_result.selected_model_name)
        self.assertIn("mae", ev["metrics"])
        self.assertGreater(len(exec_res["data"]), 0)

        ans = generate_query_answer("Predict CGPA", plan, exec_res, ev)
        self.assertIn("CGPA", ans["answer"])
        self.assertIn(pred_result.selected_model_name, ans["answer"])

    def test_g_empty_results_meaningful_message(self):
        """Test G: When no prediction has been executed, Ask Analyst provides meaningful empty message."""
        df = pd.DataFrame({"CGPA": [7.0, 8.0, 9.0], "Study_Hours": [5, 7, 9]})
        plan = {"intent": "prediction", "dataset": "cgpa_dataset.csv", "column": "CGPA", "confidence": 0.9}
        exec_res = execute_query(query_plan=plan, datasets={"cgpa_dataset.csv": df}, phase5_results={})
        ans = generate_query_answer("Predict CGPA", plan, exec_res, exec_res["evidence"])
        self.assertIn("No prediction results are available yet", ans["answer"])
        self.assertIn("Run a prediction or forecasting analysis first", ans["answer"])

    def test_h_existing_features_unaffected(self):
        """Test H: Existing Ask Analyst queries (count, average) continue working cleanly."""
        df = pd.DataFrame({
            "Market": ["Pune", "Mumbai", "Pune", "Nashik"],
            "Price": [100.0, 150.0, 120.0, 130.0],
            "Quantity": [10, 20, 15, 25],
        })
        metadata = {"sales.csv": {"column_names": list(df.columns)}}

        # Count query
        res_cnt = run_ask_analyst_query("How many records are there?", {"sales.csv": df}, metadata)
        self.assertEqual(res_cnt["status"], "success")
        self.assertIn("4", res_cnt["answer"]["answer"])

        # Average query
        res_avg = run_ask_analyst_query("What is the average price?", {"sales.csv": df}, metadata)
        self.assertEqual(res_avg["status"], "success")
        self.assertIn("125.00", res_avg["answer"]["answer"])


if __name__ == "__main__":
    unittest.main()
