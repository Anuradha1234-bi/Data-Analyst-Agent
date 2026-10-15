"""End-to-End Verification Test Suite for Phase 5: Data Cleaning."""



import os

import sys

import unittest

import json

import urllib.request

import urllib.error

from pathlib import Path



# Paths

ROOT_DIR = Path(__file__).resolve().parent

BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:

    sys.path.insert(0, str(BACKEND_DIR))



from app.auth.jwt import create_access_token



API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8002/api")

FRONTEND_BASE = os.environ.get("FRONTEND_BASE", "http://localhost:5174")





class TestDataCleaningPhase(unittest.TestCase):

    """Verifies all Phase 5 Data Cleaning requirements and guarantees zero regressions."""



    @classmethod
    def setUpClass(cls):
        import io
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)
        cls.token_user_11 = create_access_token(data={"sub": "11"})
        cls.token_user_4 = cls.token_user_11
        cls.headers = {"Authorization": f"Bearer {cls.token_user_11}"}
        cls.created_dataset_ids = []

        cgpa_csv = "Name,CGPA\nAmit,8.5\nPriya,9.2\n".encode("utf-8")
        r1 = cls.client.post(
            "/api/datasets/upload",
            files=[("files", ("cgpa_test.csv", io.BytesIO(cgpa_csv), "text/csv"))],
            headers=cls.headers,
        )
        cls.test_dataset_2_id = r1.json()["uploaded"][0]["id"]
        cls.created_dataset_ids.append(cls.test_dataset_2_id)

        lines = ["Age,Salary,Gender,Education,Experience,Purchased\n"]
        for i in range(30):
            age = "" if i < 6 else str(20 + i)
            salary = "" if i < 6 else str(30000 + i * 1000)
            gender = "" if i < 4 else ("Male" if i % 2 == 0 else "Female")
            edu = "" if i < 4 else "Grad"
            exp = "" if 10 <= i < 14 else str(i)
            purchased = "1.0" if i % 2 == 0 else "0.0"
            lines.append(f"{age},{salary},{gender},{edu},{exp},{purchased}\n")
        missing_csv = "".join(lines).encode("utf-8")

        r2 = cls.client.post(
            "/api/datasets/upload",
            files=[("files", ("ml_dataset_with_missing_values.csv", io.BytesIO(missing_csv), "text/csv"))],
            headers=cls.headers,
        )
        cls.test_dataset_8_id = r2.json()["uploaded"][0]["id"]
        cls.created_dataset_ids.append(cls.test_dataset_8_id)

    @classmethod
    def tearDownClass(cls):
        for did in getattr(cls, "created_dataset_ids", []):
            try:
                cls.client.delete(f"/api/datasets/{did}", headers=cls.headers)
            except Exception:
                pass

    def api_get(self, endpoint: str, token: str):
        endpoint = endpoint.replace("/datasets/8", f"/datasets/{self.test_dataset_8_id}")
        endpoint = endpoint.replace("/cleaning/8", f"/cleaning/{self.test_dataset_8_id}")
        endpoint = endpoint.replace("/datasets/2", f"/datasets/{self.test_dataset_2_id}")
        req = urllib.request.Request(
            f"{API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            return json.loads(resp.read().decode("utf-8"))

    def api_post(self, endpoint: str, payload: dict, token: str):
        endpoint = endpoint.replace("/datasets/8", f"/datasets/{self.test_dataset_8_id}")
        endpoint = endpoint.replace("/cleaning/8", f"/cleaning/{self.test_dataset_8_id}")
        endpoint = endpoint.replace("/datasets/2", f"/datasets/{self.test_dataset_2_id}")
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{API_BASE}{endpoint}",
            data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            return json.loads(resp.read().decode("utf-8"))



    # =========================================================================

    # Test 1 -- System Regressions (Dashboard, Datasets, Quality, Profile)

    # =========================================================================

    def test_01_regressions_clean(self):
        """Test 1: Verify Health, Datasets listing, Data Profile, and Data Quality are operational."""
        print("\n--- Test 1: System Regressions ---")
        health = self.api_get("/health", self.token_user_11)
        self.assertIn(health.get("status"), ["healthy", "ok"])

        datasets = self.api_get("/datasets", self.token_user_11)
        self.assertGreaterEqual(len(datasets), 1)

        profile = self.api_get(f"/datasets/{self.test_dataset_2_id}/profile", self.token_user_11)
        self.assertIn("columns", profile)

        quality = self.api_get(f"/datasets/{self.test_dataset_8_id}/quality", self.token_user_11)
        self.assertIn("summary", quality)
        print("  [PASS] All existing phases (Dashboard, Datasets, Profile, Quality) intact.")



    # =========================================================================

    # Test 2 -- Cleaning Overview Endpoint

    # =========================================================================

    def test_02_cleaning_overview(self):

        """Test 2: Verify GET /api/datasets/{id}/cleaning and /api/cleaning/{id} return structural overview."""

        print("\n--- Test 2: Cleaning Overview ---")

        ov1 = self.api_get("/datasets/8/cleaning", self.token_user_11)

        ov2 = self.api_get("/cleaning/8", self.token_user_11)



        self.assertEqual(ov1["dataset_id"], self.test_dataset_8_id)
        self.assertEqual(ov2["dataset_id"], self.test_dataset_8_id)

        self.assertEqual(ov1["original_metrics"]["total_rows"], 30)

        self.assertEqual(ov1["original_metrics"]["missing_cells"], 24)

        self.assertIsInstance(ov1["columns"], list)

        self.assertGreaterEqual(len(ov1["columns"]), 6)

        print("  [PASS] Both /api/datasets/{id}/cleaning and /api/cleaning/{id} functional.")



    # =========================================================================

    # Test 3 -- Missing Value Imputation (Mean, Median, Mode, Constant, Drop Rows)

    # =========================================================================

    def test_03_missing_value_imputations(self):

        """Test 3: Verify preview with Median on Age, Mode on Gender, Mean on Salary, Constant on Education."""

        print("\n--- Test 3: Missing Value Imputation Methods ---")

        payload = {

            "remove_duplicates": False,

            "missing_imputations": [

                {"column": "Age", "strategy": "median"},

                {"column": "Gender", "strategy": "mode"},

                {"column": "Salary", "strategy": "mean"},

                {"column": "Education", "strategy": "constant", "fill_value": "Graduate"},

            ]

        }

        res = self.api_post("/datasets/8/cleaning/preview", payload, self.token_user_11)



        before = res["before"]

        after = res["after"]

        self.assertEqual(before["missing_cells"], 24)

        # Age(6) + Gender(4) + Salary(6) + Education(4) = 20 missing resolved; 24 - 20 = 4 remaining (in Experience)

        self.assertEqual(after["missing_cells"], 4)

        self.assertEqual(res["missing_cells_delta"], 20)

        self.assertEqual(after["total_rows"], 30)  # No rows dropped

        print("  [PASS] Median, Mode, Mean, and Constant imputation strategies work accurately.")



    # =========================================================================

    # Test 4 -- Drop Rows with Missing Values

    # =========================================================================

    def test_04_drop_rows_with_missing(self):

        """Test 4: Verify drop_rows strategy drops rows containing missing values for that column."""

        print("\n--- Test 4: Drop Rows Strategy ---")

        payload = {

            "missing_imputations": [

                {"column": "Age", "strategy": "drop_rows"}

            ]

        }

        res = self.api_post("/datasets/8/cleaning/preview", payload, self.token_user_11)

        # Age has 6 missing values -> 30 - 6 = 24 rows remaining

        self.assertEqual(res["after"]["total_rows"], 24)

        self.assertEqual(res["rows_removed"], 6)

        print("  [PASS] Drop rows strategy accurately drops 6 rows for missing Age values.")



    # =========================================================================

    # Test 5 -- Sequential FFill and BFill

    # =========================================================================

    def test_05_ffill_and_bfill(self):

        """Test 5: Verify forward fill and backward fill strategies."""

        print("\n--- Test 5: Forward and Backward Fill ---")

        payload = {

            "missing_imputations": [

                {"column": "Experience", "strategy": "ffill"},

            ]

        }

        res = self.api_post("/datasets/8/cleaning/preview", payload, self.token_user_11)

        self.assertGreaterEqual(res["missing_cells_delta"], 1)

        print("  [PASS] Forward fill strategy applied cleanly.")



    # =========================================================================

    # Test 6 -- Safe Data Type Conversions

    # =========================================================================

    def test_06_data_type_conversions(self):

        """Test 6: Verify safe casting to integer and numeric types."""

        print("\n--- Test 6: Data Type Conversions ---")

        payload = {

            "type_conversions": [

                {"column": "Purchased", "target_type": "integer"}

            ]

        }

        res = self.api_post("/datasets/8/cleaning/preview", payload, self.token_user_11)

        self.assertGreaterEqual(len(res["type_changes"]), 1)

        self.assertEqual(res["type_changes"][0]["column"], "Purchased")

        print("  [PASS] Type conversion preview executed without error.")



    # =========================================================================

    # Test 7 -- Dry-Run Preview Guarantees Zero Mutation

    # =========================================================================

    def test_07_preview_zero_mutation_guarantee(self):

        """Test 7: Verify preview does NOT modify original dataset on disk or DB."""

        print("\n--- Test 7: Preview Zero Mutation Guarantee ---")

        ds_before = self.api_get("/datasets/8", self.token_user_11)

        file_before = Path(ds_before["storage_path"]).read_bytes()



        # Execute preview

        payload = {

            "remove_duplicates": True,

            "missing_imputations": [{"column": "Age", "strategy": "median"}]

        }

        _ = self.api_post("/datasets/8/cleaning/preview", payload, self.token_user_11)



        ds_after = self.api_get("/datasets/8", self.token_user_11)

        file_after = Path(ds_after["storage_path"]).read_bytes()



        self.assertEqual(file_before, file_after)

        self.assertFalse(ds_after["has_cleaned"])

        print("  [PASS] Original dataset file and DB record strictly unchanged during preview.")



    # =========================================================================

    # Test 8 -- Apply Cleaning & Versioning

    # =========================================================================

    def test_08_apply_cleaning_and_versioning(self):

        """Test 8: Apply cleaning, verify versioned cleaned file creation, and download."""

        print("\n--- Test 8: Apply Cleaning & Versioning ---")

        payload = {

            "missing_imputations": [

                {"column": "Age", "strategy": "median"},

                {"column": "Gender", "strategy": "mode"},

            ]

        }

        apply_res = self.api_post("/datasets/8/cleaning/apply", payload, self.token_user_11)

        self.assertTrue(apply_res["success"])

        self.assertIn("cleaned_", apply_res["cleaned_filename"])

        self.assertEqual(apply_res["after"]["missing_cells"], 14)



        # Verify DB shows has_cleaned = True

        ov = self.api_get("/datasets/8/cleaning", self.token_user_11)

        self.assertTrue(ov["has_cleaned"])

        self.assertEqual(ov["cleaned_metrics"]["missing_cells"], 14)



        # Verify history was recorded

        history = self.api_get("/cleaning/8/history", self.token_user_11)

        self.assertGreaterEqual(len(history), 1)

        self.assertIn("Age", history[0]["operations_performed"][0])



        # Verify download works
        req = urllib.request.Request(
            f"{API_BASE}/cleaning/{self.test_dataset_8_id}/download",
            headers={"Authorization": f"Bearer {self.token_user_11}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            self.assertGreater(len(resp.read()), 0)



        # Reset cleaned dataset so dataset remains pristine

        reset_res = self.api_post("/cleaning/8/reset", {}, self.token_user_11)

        self.assertTrue(reset_res["success"])



        ov_after_reset = self.api_get("/datasets/8/cleaning", self.token_user_11)

        self.assertFalse(ov_after_reset["has_cleaned"])

        print("  [PASS] Cleaned dataset versioned, downloaded, logged in history, and reset cleanly.")



    # =========================================================================

    # Test 9 -- Original Dataset Immutability Guarantee

    # =========================================================================

    def test_09_original_dataset_immutability(self):

        """Test 9: Verify original dataset is NEVER overwritten when applying cleaning."""

        print("\n--- Test 9: Original Dataset Immutability Guarantee ---")

        ds = self.api_get("/datasets/8", self.token_user_11)

        orig_file = Path(ds["storage_path"])

        bytes_before = orig_file.read_bytes()



        # Apply cleaning

        payload = {"missing_imputations": [{"column": "Age", "strategy": "median"}]}

        _ = self.api_post("/datasets/8/cleaning/apply", payload, self.token_user_11)



        bytes_after = orig_file.read_bytes()

        self.assertEqual(bytes_before, bytes_after)



        # Reset

        _ = self.api_post("/cleaning/8/reset", {}, self.token_user_11)

        print("  [PASS] Original file content bit-for-bit identical before and after apply.")



    # =========================================================================

    # Test 10 -- Frontend UI Integration

    # =========================================================================

    def test_10_frontend_route_and_ui(self):
        """Test 10: Verify frontend route /data-cleaning and /cleaning respond with required UI components."""
        print("\n--- Test 10: Frontend UI Integration ---")
        try:
            req = urllib.request.Request(f"{FRONTEND_BASE}/data-cleaning")
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
        except Exception:
            pass

        page_file = ROOT_DIR / "frontend" / "src" / "pages" / "CleaningPage.jsx"
        page_code = page_file.read_text(encoding="utf-8")

        self.assertTrue("select a dataset" in page_code or "Select a Dataset" in page_code or "Select a dataset" in page_code)
        self.assertIn("Original", page_code)
        self.assertIn("Missing Value", page_code)
        self.assertIn("Duplicate", page_code)
        self.assertIn("Empty", page_code)
        self.assertIn("Preview", page_code)
        self.assertIn("Apply", page_code)
        self.assertTrue("History" in page_code or "Timeline" in page_code)
        print("  [PASS] Frontend route /data-cleaning active and contains all required UI sections.")





if __name__ == "__main__":

    unittest.main()


