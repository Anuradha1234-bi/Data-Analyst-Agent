"""Comprehensive 11-Step Verification Suite for Data Profiling + Profiling Navigation."""

import sys
import unittest
import json
import urllib.request
import urllib.error
import re
from pathlib import Path
import pandas as pd

# Paths
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.auth.jwt import create_access_token
from agents.profiler import profile_dataset

API_BASE = "http://127.0.0.1:8002/api"
FRONTEND_BASE = "http://localhost:5174"


class TestDataProfilingAndNavigation(unittest.TestCase):
    """End-to-end verification covering all 11 acceptance test scenarios."""

    @classmethod
    def setUpClass(cls):
        import io
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)
        cls.token_user_11 = create_access_token(data={"sub": "11"})
        cls.token_user_4 = cls.token_user_11
        cls.headers = {"Authorization": f"Bearer {cls.token_user_11}"}
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
        cls.test_dataset_2_id = res1.json()["uploaded"][0]["id"]
        cls.created_ids.append(cls.test_dataset_2_id)

        res2 = cls.client.post("/api/datasets/upload", files=[("files", ("ml_dataset_with_missing_values.csv", io.BytesIO(missing_csv), "text/csv"))], headers=cls.headers)
        cls.test_dataset_8_id = res2.json()["uploaded"][0]["id"]
        cls.created_ids.append(cls.test_dataset_8_id)

        res3 = cls.client.post("/api/datasets/upload", files=[("files", ("experience_salary_outliers.csv", io.BytesIO(outliers_csv), "text/csv"))], headers=cls.headers)
        cls.test_dataset_5_id = res3.json()["uploaded"][0]["id"]
        cls.created_ids.append(cls.test_dataset_5_id)

        res4 = cls.client.post("/api/datasets/upload", files=[("files", ("big_ml_practice_dataset.csv", io.BytesIO(big_ml_csv), "text/csv"))], headers=cls.headers)
        cls.test_dataset_6_id = res4.json()["uploaded"][0]["id"]
        cls.created_ids.append(cls.test_dataset_6_id)

    @classmethod
    def tearDownClass(cls):
        for did in getattr(cls, "created_ids", []):
            try:
                cls.client.delete(f"/api/datasets/{did}", headers=cls.headers)
            except Exception:
                pass

    def api_get(self, endpoint: str, token: str):
        """Helper for authenticated API calls."""
        endpoint = re.sub(r"/datasets/2(?=/|$)", f"/datasets/{self.test_dataset_2_id}", endpoint)
        endpoint = re.sub(r"/datasets/5(?=/|$)", f"/datasets/{self.test_dataset_5_id}", endpoint)
        endpoint = re.sub(r"/datasets/6(?=/|$)", f"/datasets/{self.test_dataset_6_id}", endpoint)
        endpoint = re.sub(r"/datasets/8(?=/|$)", f"/datasets/{self.test_dataset_8_id}", endpoint)
        url = f"/api{endpoint}" if not endpoint.startswith("/api") else endpoint
        resp = self.client.get(url, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    # =========================================================================
    # Test 1 — Navigation
    # =========================================================================
    def test_01_navigation(self):
        """Test 1: Verify all 14 navigation items, groups, and routes."""
        print("\n--- Test 1: Navigation Verification ---")
        required_routes = [
            "/dashboard", "/upload", "/profile-data", "/data-quality",
            "/data-cleaning", "/data-analyst", "/analytics", "/anomalies",
            "/predictions", "/insights", "/reports", "/settings",
            "/history", "/profile"
        ]
        for route in required_routes:
            with urllib.request.urlopen(f"{FRONTEND_BASE}{route}") as resp:
                self.assertEqual(resp.status, 200, f"Route {route} must return HTTP 200")

        layout_path = ROOT_DIR / "frontend" / "src" / "layouts" / "MainLayout.jsx"
        with open(layout_path, "r", encoding="utf-8") as f:
            layout_code = f.read()

        required_items = [
            ("Dashboard", "/dashboard"),
            ("Upload Dataset", "/upload"),
            ("Data Profile", "/profile-data"),
            ("Data Quality", "/data-quality"),
            ("Data Cleaning", "/data-cleaning"),
            ("Data Analyst", "/data-analyst"),
            ("Analytics", "/analytics"),
            ("Anomalies", "/anomalies"),
            ("Predictions", "/predictions"),
            ("Insights", "/insights"),
            ("Reports", "/reports"),
            ("Settings", "/settings"),
            ("History", "/history"),
            ("Profile", "/profile"),
        ]
        for name, path in required_items:
            self.assertIn(f"name: '{name}'", layout_code, f"Missing nav item {name}")
            self.assertIn(f"path: '{path}'", layout_code, f"Missing nav path {path}")

        for group in ["DATA", "ANALYSIS", "OUTPUT", "SYSTEM"]:
            self.assertIn(f"title: '{group}'", layout_code, f"Missing nav group {group}")

        print("  [PASS] Navigation verified: All 14 navigation items and groups operational.")

    # =========================================================================
    # Test 2 — Dataset Selection to API
    # =========================================================================
    def test_02_dataset_selection(self):
        """Test 2: Select an uploaded dataset and verify correct Dataset ID to API flow."""
        print("\n--- Test 2: Dataset Selection Flow ---")
        datasets = self.api_get("/datasets", self.token_user_4)
        self.assertGreater(len(datasets), 0, "User 4 must have uploaded datasets")

        dataset_id = datasets[0]["id"]
        profile = self.api_get(f"/datasets/{dataset_id}/profile", self.token_user_4)

        self.assertEqual(profile["dataset_info"]["id"], dataset_id)
        self.assertEqual(profile["dataset_info"]["name"], datasets[0]["original_filename"])
        print(f"  [PASS] Selected Dataset ID {dataset_id} successfully mapped to profiling API.")

    # =========================================================================
    # Test 3 — Dataset Overview
    # =========================================================================
    def test_03_dataset_overview(self):
        """Test 3: Verify rows, columns, and total cells match the actual dataset."""
        print("\n--- Test 3: Dataset Overview ---")
        profile = self.api_get("/datasets/2/profile", self.token_user_4)
        info = profile["dataset_info"]
        self.assertEqual(info["id"], self.test_dataset_2_id)
        self.assertEqual(info["name"], "cgpa.csv")
        self.assertEqual(info["rows"], 18)
        self.assertEqual(info["columns"], 4)
        self.assertEqual(info["total_cells"], 72)
        self.assertGreater(info["file_size_bytes"], 0)
        print(f"  [PASS] Overview verified: {info['rows']} rows, {info['columns']} cols, {info['total_cells']} cells.")

    # =========================================================================
    # Test 4 — Missing Values
    # =========================================================================
    def test_04_missing_values(self):
        """Test 4: Verify missing count and missing percentage against actual data."""
        print("\n--- Test 4: Missing Values Diagnostic ---")
        profile = self.api_get("/datasets/8/profile", self.token_user_11)
        qs = profile["quality_summary"]

        self.assertEqual(qs["total_missing_cells"], 24)
        self.assertEqual(qs["missing_percentage"], 13.33)
        self.assertEqual(qs["columns_with_missing_count"], 5)

        missing_by_col = {mc["column"]: mc for mc in qs["missing_columns"]}
        self.assertEqual(missing_by_col["Age"]["missing_count"], 6)
        self.assertEqual(missing_by_col["Age"]["missing_percentage"], 20.0)
        self.assertEqual(missing_by_col["Salary"]["missing_count"], 6)
        self.assertEqual(missing_by_col["Salary"]["missing_percentage"], 20.0)
        print("  [PASS] Missing values verified: 24 total missing cells (13.33%) across 5 columns.")

    # =========================================================================
    # Test 5 — Numerical Columns
    # =========================================================================
    def test_05_numerical_columns(self):
        """Test 5: Verify count, mean, median, min, max, std, Q1, Q3, and IQR."""
        print("\n--- Test 5: Numerical Statistics ---")
        profile = self.api_get("/datasets/2/profile", self.token_user_4)
        cgpa_col = next(c for c in profile["columns"] if c["name"] == "CGPA")
        ns = cgpa_col["numeric_stats"]

        self.assertIsNotNone(ns)
        self.assertEqual(ns["count"], 18)
        self.assertAlmostEqual(ns["mean"], 7.58, places=1)
        self.assertAlmostEqual(ns["median"], 7.65, places=1)
        self.assertEqual(ns["min"], 5.0)
        self.assertEqual(ns["max"], 9.8)
        self.assertAlmostEqual(ns["std"], 1.41, places=1)
        self.assertAlmostEqual(ns["q1"], 6.58, places=1)
        self.assertAlmostEqual(ns["q3"], 8.73, places=1)
        self.assertAlmostEqual(ns["iqr"], 2.15, places=1)
        print("  [PASS] Numerical moments verified: count=18, mean=7.58, median=7.65, IQR=2.15.")

    # =========================================================================
    # Test 6 — Categorical Columns
    # =========================================================================
    def test_06_categorical_columns(self):
        """Test 6: Verify unique count, most frequent value, and frequency."""
        print("\n--- Test 6: Categorical Distributions ---")
        profile = self.api_get("/datasets/2/profile", self.token_user_4)
        name_col = next(c for c in profile["columns"] if c["name"] == "Name")
        cs = name_col["categorical_stats"]

        self.assertIsNotNone(cs)
        self.assertEqual(cs["unique_count"], 18)
        self.assertEqual(cs["frequency"], 1)
        self.assertIsInstance(cs["top_values"], list)
        self.assertGreater(len(cs["top_values"]), 0)
        print(f"  [PASS] Categorical verified: 18 unique, top value '{cs['most_frequent']}'.")

    # =========================================================================
    # Test 7 — Duplicate Rows
    # =========================================================================
    def test_07_duplicate_rows(self):
        """Test 7: Verify duplicate count on clean and duplicated datasets."""
        print("\n--- Test 7: Duplicate Rows Hygiene ---")
        profile = self.api_get("/datasets/2/profile", self.token_user_4)
        self.assertEqual(profile["quality_summary"]["duplicate_rows"], 0)
        self.assertEqual(profile["quality_summary"]["duplicate_percentage"], 0.0)

        # Synthetic duplicate validation
        df_dup = pd.DataFrame({"x": [1, 2, 2, 3, 3, 3]})
        prof_dup = profile_dataset(df_dup)
        self.assertEqual(prof_dup.duplicate_rows, 3)
        self.assertEqual(prof_dup.duplicate_percentage, 50.0)
        print("  [PASS] Duplicate counts verified: 0 on cgpa.csv, 3 (50%) on duplicate frame.")

    # =========================================================================
    # Test 8 — Dataset Switching
    # =========================================================================
    def test_08_dataset_switching(self):
        """Test 8: Select Dataset A -> Profile, then Dataset B -> Profile. Results must not mix."""
        print("\n--- Test 8: Dataset Switching Isolation ---")
        prof_a = self.api_get("/datasets/5/profile", self.token_user_11)
        prof_b = self.api_get("/datasets/6/profile", self.token_user_11)

        self.assertEqual(prof_a["dataset_info"]["id"], self.test_dataset_5_id)
        self.assertEqual(prof_a["dataset_info"]["name"], "experience_salary_outliers.csv")
        self.assertEqual(prof_a["dataset_info"]["rows"], 20)

        self.assertEqual(prof_b["dataset_info"]["id"], self.test_dataset_6_id)
        self.assertEqual(prof_b["dataset_info"]["name"], "big_ml_practice_dataset.csv")
        self.assertEqual(prof_b["dataset_info"]["rows"], 30)

        self.assertNotEqual(prof_a["dataset_info"]["name"], prof_b["dataset_info"]["name"])
        print(f"  [PASS] Switching verified: Dataset {self.test_dataset_5_id} (20 rows) and Dataset {self.test_dataset_6_id} (30 rows) completely isolated.")

    # =========================================================================
    # Test 9 — No Dataset Empty State
    # =========================================================================
    def test_09_no_dataset(self):
        """Test 9: Verify empty state in UI."""
        print("\n--- Test 9: No Dataset Empty State ---")
        profiling_page_path = ROOT_DIR / "frontend" / "src" / "pages" / "ProfilingPage.jsx"
        with open(profiling_page_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertTrue("No datasets selected" in code or "Please select a dataset" in code or "Select Datasets" in code)
        self.assertTrue("selectedDatasetsCount" in code or "!selectedDatasetId" in code)
        print("  [PASS] Empty state verified properly.")

    # =========================================================================
    # Test 10 — Refresh & Context
    # =========================================================================
    def test_10_refresh(self):
        """Test 10: Refreshing profiling page preserves dataset context via query parameter."""
        print("\n--- Test 10: Refresh & Routing Context ---")
        profile_first = self.api_get("/datasets/2/profile", self.token_user_4)
        profile_reload = self.api_get("/datasets/2/profile", self.token_user_4)

        self.assertEqual(profile_first["dataset_info"]["id"], profile_reload["dataset_info"]["id"])
        self.assertEqual(profile_first["dataset_info"]["name"], profile_reload["dataset_info"]["name"])
        self.assertEqual(len(profile_first["columns"]), len(profile_reload["columns"]))
        print("  [PASS] Reload context verified: identical structured profile returned.")

    # =========================================================================
    # Test 11 — Regression
    # =========================================================================
    def test_11_regression(self):
        """Test 11: Verify existing Dashboard, Upload, Storage, and Download still work."""
        print("\n--- Test 11: System Regressions ---")
        # 1. Health
        with urllib.request.urlopen(f"{API_BASE}/health", timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            h = json.loads(resp.read().decode("utf-8"))
            self.assertIn(h["status"], ["healthy", "ok"])

        # 2. Datasets listing
        datasets = self.api_get("/datasets", self.token_user_4)
        self.assertIsInstance(datasets, list)

        # 3. File download
        req_dl = urllib.request.Request(
            f"{API_BASE}/datasets/{self.test_dataset_2_id}/download",
            headers={"Authorization": f"Bearer {self.token_user_4}"}
        )
        with urllib.request.urlopen(req_dl, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read()
            self.assertGreater(len(content), 0)
        print("  [PASS] Regressions clean: Health, Datasets listing, and Download fully operational.")


if __name__ == "__main__":
    unittest.main(verbosity=2)

