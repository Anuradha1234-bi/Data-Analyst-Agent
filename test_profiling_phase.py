"""Comprehensive Verification Suite for Phase: Data Profiling & Data Quality."""

import sys
import unittest
import json
import urllib.request
import urllib.error
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure backend and root paths are available
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
# Ensure backend directory takes absolute priority for app package
if "app" in sys.modules:
    del sys.modules["app"]
if str(BACKEND_DIR) in sys.path:
    sys.path.remove(str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.auth.jwt import create_access_token
from app.database import SessionLocal
from app.models.dataset import Dataset
from app.models.user import User
from app.services.profiling_service import ProfilingService
from app.schemas.profiling import DatasetProfileResponse
from agents.profiler import ProfilerAgent, profile_dataset

import io
import os
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8002/api")


class TestDataProfilingPhase(unittest.TestCase):
    """Test suite covering Tests A through G, API endpoints, error handling, and regressions."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)
        cls.token_user_4 = create_access_token(data={"sub": "11"})
        cls.token_user_11 = cls.token_user_4
        cls.headers = {"Authorization": f"Bearer {cls.token_user_4}"}
        cls.created_ids = []

        # 1. CGPA CSV (18 rows matching exact moments)
        cgpa_csv = (
            "Name,Year,CGPA,Package\n"
            "Amit,2020,5.0,3.0\nSneha,2020,5.5,3.2\nRahul,2021,6.0,3.5\nPriya,2021,6.2,3.7\n"
            "Karan,2022,6.5,4.0\nNeha,2022,6.8,4.2\nArjun,2023,7.0,4.5\nPooja,2023,7.2,4.8\n"
            "Vikas,2020,7.5,5.2\nAnjali,2021,7.8,5.5\nRohit,2022,8.0,6.0\nMeena,2023,8.2,6.3\n"
            "Sahil,2020,8.5,6.8\nKavya,2021,8.8,7.2\nNikhil,2022,9.0,7.8\nRiya,2023,9.2,8.2\n"
            "Aditya,2021,9.5,9.0\nShreya,2022,9.8,9.5\n"
        ).encode("utf-8")

        # 2. Missing values CSV (30 rows, 6 cols, 24 missing cells)
        missing_rows = ["ID,Age,Gender,Education,Experience,Salary\n"]
        for i in range(30):
            age = "" if i < 6 else str(22 + i)
            salary = "" if i < 6 else str(40000 + i * 1500)
            gender = "" if i < 4 else ("Male" if i % 2 == 0 else "Female")
            edu = "" if i < 4 else ("Bachelors" if i % 2 == 0 else "Masters")
            exp = "" if i < 4 else str(1 + (i % 8))
            missing_rows.append(f"{i+1},{age},{gender},{edu},{exp},{salary}\n")
        missing_csv = "".join(missing_rows).encode("utf-8")

        # 3. Experience Salary Outliers CSV (20 rows, 2 cols)
        outliers_csv = ("Experience,Salary\n" + "".join([f"{i+1},{30000 + i*3000}\n" for i in range(20)])).encode("utf-8")

        # 4. Big ML Practice Dataset (30 rows, 6 cols)
        big_ml_csv = ("A,B,C,D,E,F\n" + "".join([f"{i},{i*2},{i*3},{i*4},{i*5},{i*6}\n" for i in range(30)])).encode("utf-8")

        res1 = cls.client.post("/api/datasets/upload", files=[("files", ("cgpa.csv", io.BytesIO(cgpa_csv), "text/csv"))], headers=cls.headers)
        cls.cgpa_id = res1.json()["uploaded"][0]["id"]
        cls.created_ids.append(cls.cgpa_id)

        res2 = cls.client.post("/api/datasets/upload", files=[("files", ("ml_dataset_with_missing_values.csv", io.BytesIO(missing_csv), "text/csv"))], headers=cls.headers)
        cls.missing_id = res2.json()["uploaded"][0]["id"]
        cls.created_ids.append(cls.missing_id)

        res3 = cls.client.post("/api/datasets/upload", files=[("files", ("experience_salary_outliers.csv", io.BytesIO(outliers_csv), "text/csv"))], headers=cls.headers)
        cls.outliers_id = res3.json()["uploaded"][0]["id"]
        cls.created_ids.append(cls.outliers_id)

        res4 = cls.client.post("/api/datasets/upload", files=[("files", ("big_ml_practice_dataset.csv", io.BytesIO(big_ml_csv), "text/csv"))], headers=cls.headers)
        cls.big_ml_id = res4.json()["uploaded"][0]["id"]
        cls.created_ids.append(cls.big_ml_id)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "created_ids"):
            for did in cls.created_ids:
                try:
                    cls.client.delete(f"/api/datasets/{did}", headers=cls.headers)
                except Exception:
                    pass

    def make_api_request(self, path: str, token: str):
        """Helper to execute authenticated HTTP GET request to FastAPI."""
        url = f"/api{path}" if not path.startswith("/api") else path
        resp = self.client.get(url, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    # =========================================================================
    # Test A: Normal Dataset
    # =========================================================================
    def test_a_normal_dataset(self):
        """Test A: Normal Dataset (cgpa.csv).
        Expected: dataset loads, profiling succeeds, rows/columns correct, column info correct.
        """
        print("\n--- Test A: Normal Dataset Profiling ---")
        

        data = self.make_api_request(f"/datasets/{self.cgpa_id}/profile", self.token_user_4)

        # 1. Dataset overview
        info = data["dataset_info"]
        self.assertEqual(info["id"], self.cgpa_id)
        self.assertEqual(info["name"], "cgpa.csv")
        self.assertEqual(info["rows"], 18)
        self.assertEqual(info["columns"], 4)
        self.assertEqual(info["total_cells"], 72)
        self.assertGreater(info["file_size_bytes"], 0)

        # 2. Columns count & metadata
        cols = data["columns"]
        self.assertEqual(len(cols), 4)
        col_names = [c["name"] for c in cols]
        self.assertIn("Name", col_names)
        self.assertIn("CGPA", col_names)
        self.assertIn("Package", col_names)
        self.assertIn("Year", col_names)

        # 3. Column info details
        name_col = next(c for c in cols if c["name"] == "Name")
        self.assertEqual(name_col["semantic_type"], "CATEGORICAL")
        self.assertEqual(name_col["missing_count"], 0)
        self.assertEqual(name_col["non_null_count"], 18)

        cgpa_col = next(c for c in cols if c["name"] == "CGPA")
        self.assertEqual(cgpa_col["semantic_type"], "NUMERIC")
        self.assertEqual(cgpa_col["missing_count"], 0)
        self.assertEqual(cgpa_col["non_null_count"], 18)

        # 4. Quality status
        quality = data["quality_summary"]
        self.assertEqual(quality["health_status"], "Excellent")
        self.assertEqual(quality["health_score"], 100)
        self.assertEqual(quality["total_missing_cells"], 0)
        self.assertEqual(quality["duplicate_rows"], 0)
        print("  [PASS] Normal dataset profiled with 18 rows, 4 cols, 100% health score.")

    # =========================================================================
    # Test B: Missing Values
    # =========================================================================
    def test_b_missing_values(self):
        """Test B: Missing Values (ml_dataset_with_missing_values.csv).
        Expected: missing count correct, missing percentage correct, no crash.
        """
        print("\n--- Test B: Missing Values Diagnostic ---")
        

        data = self.make_api_request(f"/datasets/{self.missing_id}/profile", self.token_user_11)

        quality = data["quality_summary"]
        self.assertEqual(quality["total_missing_cells"], 24)
        self.assertEqual(quality["missing_percentage"], 13.33)
        self.assertEqual(quality["columns_with_missing_count"], 5)

        # Check column-level missing details
        missing_map = {mc["column"]: mc for mc in quality["missing_columns"]}
        self.assertEqual(missing_map["Age"]["missing_count"], 6)
        self.assertEqual(missing_map["Age"]["missing_percentage"], 20.0)
        self.assertEqual(missing_map["Salary"]["missing_count"], 6)
        self.assertEqual(missing_map["Salary"]["missing_percentage"], 20.0)
        self.assertEqual(missing_map["Gender"]["missing_count"], 4)

        # Highest missing columns correctly ordered
        highest = quality["highest_missing_columns"]
        self.assertGreaterEqual(len(highest), 1)
        self.assertGreaterEqual(highest[0]["missing_percentage"], highest[-1]["missing_percentage"])
        print("  [PASS] Missing values correctly diagnosed: 24 missing cells (13.33%) across 5 columns.")

    # =========================================================================
    # Test C: Numerical Columns Statistics
    # =========================================================================
    def test_c_numerical_statistics(self):
        """Test C: Numerical Columns (CGPA, Package in cgpa.csv).
        Expected: count, mean, median, min, max, std, quartiles, iqr are correct.
        """
        print("\n--- Test C: Numerical Columns Statistics ---")
        data = self.make_api_request(f"/datasets/{self.cgpa_id}/profile", self.token_user_4)

        cgpa_col = next(c for c in data["columns"] if c["name"] == "CGPA")
        ns = cgpa_col["numeric_stats"]
        self.assertIsNotNone(ns, "CGPA column must have numeric_stats")

        # Ground truth values verified
        self.assertEqual(ns["count"], 18)
        self.assertAlmostEqual(ns["mean"], 7.58, places=1)
        self.assertAlmostEqual(ns["median"], 7.65, places=1)
        self.assertEqual(ns["min"], 5.0)
        self.assertEqual(ns["max"], 9.8)
        self.assertAlmostEqual(ns["std"], 1.41, places=1)
        self.assertAlmostEqual(ns["q1"], 6.58, places=1)
        self.assertAlmostEqual(ns["q3"], 8.73, places=1)
        self.assertAlmostEqual(ns["iqr"], 2.15, places=1)

        # Verify Q3 - Q1 == IQR
        self.assertAlmostEqual(ns["q3"] - ns["q1"], ns["iqr"], places=2)
        print("  [PASS] Numerical moments verified: mean=7.58, median=7.65, min=5.0, max=9.8, IQR=2.15.")

    # =========================================================================
    # Test D: Text / Categorical Columns
    # =========================================================================
    def test_d_categorical_text_columns(self):
        """Test D: Text/Categorical Columns (Name in cgpa.csv).
        Expected: unique count, top value, frequency are correct.
        """
        print("\n--- Test D: Text & Categorical Distribution ---")
        data = self.make_api_request(f"/datasets/{self.cgpa_id}/profile", self.token_user_4)

        name_col = next(c for c in data["columns"] if c["name"] == "Name")
        cs = name_col["categorical_stats"]
        self.assertIsNotNone(cs, "Name column must have categorical_stats")

        self.assertEqual(cs["unique_count"], 18)
        self.assertIsNotNone(cs["most_frequent"])
        self.assertGreater(cs["frequency"], 0)
        self.assertIsInstance(cs["top_values"], list)
        self.assertGreater(len(cs["top_values"]), 0)

        first_top = cs["top_values"][0]
        self.assertIn("value", first_top)
        self.assertIn("count", first_top)
        self.assertIn("percentage", first_top)
        print(f"  [PASS] Categorical distribution verified: 18 unique names, top value '{cs['most_frequent']}'.")

    # =========================================================================
    # Test E: Duplicate Rows
    # =========================================================================
    def test_e_duplicate_rows(self):
        """Test E: Duplicate Rows calculation.
        Expected: duplicate count and percentage are accurately evaluated.
        """
        print("\n--- Test E: Duplicate Rows Hygiene ---")
        # Direct dataframe test with controlled duplicates
        df_dup = pd.DataFrame({
            "id": [1, 2, 2, 3, 3, 3],
            "val": ["a", "b", "b", "c", "c", "c"],
        })
        prof = profile_dataset(df_dup)
        self.assertEqual(prof.duplicate_rows, 3)
        self.assertEqual(prof.duplicate_percentage, 50.0)

        # Zero duplicates test on cgpa.csv
        data = self.make_api_request(f"/datasets/{self.cgpa_id}/profile", self.token_user_4)
        self.assertEqual(data["quality_summary"]["duplicate_rows"], 0)
        self.assertEqual(data["quality_summary"]["duplicate_percentage"], 0.0)
        print("  [PASS] Duplicate rows calculated accurately (3 duplicates = 50.0% on synthetic, 0 on cgpa.csv).")

    # =========================================================================
    # Test F: Empty / Invalid Dataset Handling
    # =========================================================================
    def test_f_empty_invalid_dataset(self):
        """Test F: Empty/Invalid Dataset.
        Expected: graceful error and informative message without unhandled crashes.
        """
        print("\n--- Test F: Empty & Invalid Dataset Handling ---")
        # 1. Non-existent dataset ID -> 404
        resp = self.client.get(f"/api/datasets/99999/profile", headers={"Authorization": f"Bearer {self.token_user_4}"})
        self.assertEqual(resp.status_code, 404)

        # 2. Empty DataFrame -> raises clean HTTPException(400)
        empty_df = pd.DataFrame()
        with self.assertRaises(ValueError):
            profile_dataset(empty_df)

        # 3. User isolation check -> unauthorized user returns 401
        resp_unauth = self.client.get(
            f"/api/datasets/{self.missing_id}/profile",
            headers={"Authorization": f"Bearer {create_access_token(data={'sub': '9999'})}"}
        )
        self.assertEqual(resp_unauth.status_code, 401)
        print("  [PASS] Invalid dataset correctly raises 404; empty dataframe raises clean ValueError/400.")

    # =========================================================================
    # Test G: Dataset Switching
    # =========================================================================
    def test_g_dataset_switching(self):
        """Test G: Dataset Switching.
        Select Dataset A -> Profile. Then select Dataset B -> Profile.
        Verify that Dataset A's profile does NOT appear for Dataset B.
        """
        print("\n--- Test G: Dataset Switching Verification ---")
        # Select Dataset A (experience_salary_outliers.csv) for user 11
        data_a = self.make_api_request(f"/datasets/{self.outliers_id}/profile", self.token_user_11)
        self.assertEqual(data_a["dataset_info"]["id"], self.outliers_id)
        self.assertEqual(data_a["dataset_info"]["name"], "experience_salary_outliers.csv")
        self.assertEqual(data_a["dataset_info"]["rows"], 20)
        self.assertEqual(data_a["dataset_info"]["columns"], 2)

        # Select Dataset B (big_ml_practice_dataset.csv) for user 11
        data_b = self.make_api_request(f"/datasets/{self.big_ml_id}/profile", self.token_user_11)
        self.assertEqual(data_b["dataset_info"]["id"], self.big_ml_id)
        self.assertEqual(data_b["dataset_info"]["name"], "big_ml_practice_dataset.csv")
        self.assertEqual(data_b["dataset_info"]["rows"], 30)
        self.assertEqual(data_b["dataset_info"]["columns"], 6)

        # Strict non-overlap verification
        self.assertNotEqual(data_a["dataset_info"]["id"], data_b["dataset_info"]["id"])
        self.assertNotEqual(data_a["dataset_info"]["name"], data_b["dataset_info"]["name"])
        self.assertNotEqual(data_a["dataset_info"]["rows"], data_b["dataset_info"]["rows"])
        self.assertNotEqual(data_a["dataset_info"]["columns"], data_b["dataset_info"]["columns"])
        print("  [PASS] Dataset switching verified: Dataset A and Dataset B isolated cleanly.")

    # =========================================================================
    # Regression & Health Checks
    # =========================================================================
    def test_h_regression_checks(self):
        """Test H: Existing functionality regression check.
        Verify /api/health, /api/datasets listing, /api/profiling/{id} routing.
        """
        print("\n--- Test H: System Regressions & API Routing ---")
        # 1. Health endpoint
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data["status"], ("ok", "healthy"))

        # 2. Datasets listing endpoint
        datasets = self.make_api_request("/datasets", self.token_user_4)
        self.assertIsInstance(datasets, list)
        self.assertGreater(len(datasets), 0)

        # 3. Profiling router alias /api/profiling/{dataset_id}
        profile_alias = self.make_api_request(f"/profiling/{self.cgpa_id}", self.token_user_4)
        self.assertEqual(profile_alias["dataset_info"]["id"], self.cgpa_id)
        self.assertEqual(profile_alias["dataset_info"]["name"], "cgpa.csv")
        print("  [PASS] Regression checks passed: Health, Datasets listing, and Profiling router operational.")
        print("  [PASS] Regression checks passed: Health, Datasets listing, and Profiling router operational.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
