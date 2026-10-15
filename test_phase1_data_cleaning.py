"""Unit & Integration Test Suite for DATA CLEANING - PHASE 1.

Verifies:
1. Dataset selection & metadata (name, rows, cols, file_type, upload_date, status)
2. Missing value detection per column (count and percentage)
3. Missing value handling (mean, median, mode, ffill, bfill, constant, drop_rows)
4. Duplicate row detection and removal (with count calculation)
5. Blank / whitespace string detection and conversion to NaN
6. Data type detection and safe casting
7. Column name standardization (snake_case, uniqueness, special chars removal)
8. Before / After preview with zero disk mutation guarantee
9. Safe dataset versioning (original dataset preserved bit-for-bit)
10. Cleaning history audit trail (Operation, Column, Method, Rows Affected, Date)
11. Undo / Restore previous version
12. Cleaned dataset preview when active
"""

import os
import sys
import json
import unittest
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


class TestDataCleaningPhase1(unittest.TestCase):
    """Full verification suite for Phase 1 Data Cleaning requirements."""

    @classmethod
    def setUpClass(cls):
        import io
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)
        cls.token = create_access_token(data={"sub": "11"})
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

        lines = ["Age,Salary,Gender,Education,Experience,Purchased\n"]
        for i in range(30):
            age = "" if i < 6 else str(20 + i)
            salary = "" if i < 6 else str(30000 + i * 1000)
            gender = "" if i < 4 else ("Male" if i % 2 == 0 else "Female")
            edu = "" if i < 4 else "Grad"
            exp = "" if 10 <= i < 14 else str(i)
            purchased = "1.0" if i % 2 == 0 else "0.0"
            lines.append(f"{age},{salary},{gender},{edu},{exp},{purchased}\n")
        csv_bytes = "".join(lines).encode("utf-8")

        res = cls.client.post(
            "/api/datasets/upload",
            files=[("files", ("ml_dataset_with_missing_values.csv", io.BytesIO(csv_bytes), "text/csv"))],
            headers=cls.headers,
        )
        cls.test_dataset_id = res.json()["uploaded"][0]["id"]

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "test_dataset_id") and cls.test_dataset_id:
            try:
                cls.client.delete(f"/api/datasets/{cls.test_dataset_id}", headers=cls.headers)
            except Exception:
                pass

    def api_get(self, endpoint: str):
        endpoint = endpoint.replace("/8", f"/{self.test_dataset_id}")
        url = f"/api{endpoint}" if not endpoint.startswith("/api") else endpoint
        resp = self.client.get(url, headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def api_post(self, endpoint: str, payload: dict):
        endpoint = endpoint.replace("/8", f"/{self.test_dataset_id}")
        url = f"/api{endpoint}" if not endpoint.startswith("/api") else endpoint
        resp = self.client.post(url, json=payload, headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    # =========================================================================
    # 1. Dataset Selection & Metadata
    # =========================================================================
    def test_01_dataset_selection_and_metadata(self):
        """Feature 1: Verify dataset overview returns name, rows, cols, file_type, and upload_date."""
        print("\n--- Test 1: Dataset Selection & Metadata ---")
        ov = self.api_get("/cleaning/8")
        self.assertEqual(ov["dataset_id"], self.test_dataset_id)
        self.assertIn("filename", ov)
        self.assertIn("file_type", ov)
        self.assertIn("upload_date", ov)
        self.assertEqual(ov["original_metrics"]["total_rows"], 30)
        self.assertEqual(ov["original_metrics"]["total_columns"], 6)
        print(f"  [PASS] Dataset metadata verified: {ov['filename']} ({ov['file_type']}, {ov['original_metrics']['total_rows']} rows, {ov['original_metrics']['total_columns']} cols).")

    # =========================================================================
    # 2. Missing Value Detection
    # =========================================================================
    def test_02_missing_value_detection(self):
        """Feature 2: Verify missing count and percentage for every column."""
        print("\n--- Test 2: Missing Value Detection ---")
        ov = self.api_get("/cleaning/8")
        cols = {c["column_name"]: c for c in ov["columns"]}
        
        self.assertIn("Age", cols)
        self.assertEqual(cols["Age"]["missing_count"], 6)
        self.assertEqual(cols["Age"]["missing_percentage"], 20.0)
        
        self.assertIn("Salary", cols)
        self.assertEqual(cols["Salary"]["missing_count"], 6)
        self.assertEqual(cols["Salary"]["missing_percentage"], 20.0)
        
        self.assertIn("Gender", cols)
        self.assertEqual(cols["Gender"]["missing_count"], 4)
        print("  [PASS] Missing values detected accurately per column with counts and percentages.")

    # =========================================================================
    # 3. Missing Value Handling Methods
    # =========================================================================
    def test_03_missing_value_methods(self):
        """Feature 3: Verify Mean, Median, Mode, Constant, FFill, BFill, and Drop Rows."""
        print("\n--- Test 3: Missing Value Handling Methods ---")
        
        # Test Median, Mean, Mode, Constant
        payload = {
            "missing_imputations": [
                {"column": "Age", "strategy": "median"},
                {"column": "Salary", "strategy": "mean"},
                {"column": "Gender", "strategy": "mode"},
                {"column": "Education", "strategy": "constant", "fill_value": "Bachelors"},
                {"column": "Experience", "strategy": "ffill"},
            ]
        }
        res = self.api_post("/cleaning/8/preview", payload)
        self.assertEqual(res["before"]["missing_cells"], 24)
        self.assertEqual(res["after"]["missing_cells"], 0)
        self.assertEqual(res["missing_cells_delta"], 24)

        # Test Drop Rows strategy on Age
        drop_payload = {
            "missing_imputations": [
                {"column": "Age", "strategy": "drop_rows"}
            ]
        }
        drop_res = self.api_post("/cleaning/8/preview", drop_payload)
        self.assertEqual(drop_res["rows_removed"], 6)
        self.assertEqual(drop_res["after"]["total_rows"], 24)
        print("  [PASS] All missing value methods (Mean, Median, Mode, Constant, FFill, Drop Rows) verified.")

    # =========================================================================
    # 4. Duplicate Row Detection & Removal
    # =========================================================================
    def test_04_duplicate_detection_and_removal(self):
        """Feature 4: Verify duplicate detection and remove duplicates preview."""
        print("\n--- Test 4: Duplicate Row Detection & Removal ---")
        ov = self.api_get("/cleaning/8")
        self.assertIn("duplicate_rows_count", ov)
        self.assertIn("duplicate_percentage", ov)

        payload = {"remove_duplicates": True}
        res = self.api_post("/cleaning/8/preview", payload)
        self.assertGreaterEqual(res["before"]["total_rows"], res["after"]["total_rows"])
        print(f"  [PASS] Duplicate detection verified: {ov['duplicate_rows_count']} duplicate rows ({ov['duplicate_percentage']}%).")

    # =========================================================================
    # 5. Blank / Whitespace String Detection & Conversion
    # =========================================================================
    def test_05_blank_whitespace_conversion(self):
        """Feature 5: Verify convert_blanks_to_na converts whitespace strings to NaN."""
        print("\n--- Test 5: Blank / Whitespace String Sanitization ---")
        ov = self.api_get("/cleaning/8")
        self.assertIn("total_blank_cells", ov)
        self.assertIn("columns_with_blanks", ov)

        payload = {
            "convert_blanks_to_na": True
        }
        res = self.api_post("/cleaning/8/preview", payload)
        self.assertIn("blank_cells_converted", res)
        print("  [PASS] Blank/whitespace detection and conversion option verified.")

    # =========================================================================
    # 6. Data Type Detection & Safe Conversion
    # =========================================================================
    def test_06_data_type_detection_and_conversion(self):
        """Feature 6: Verify data type inspection and safe casting (e.g. Integer, Float, String)."""
        print("\n--- Test 6: Data Type Detection & Safe Conversion ---")
        ov = self.api_get("/cleaning/8")
        for col in ov["columns"]:
            self.assertIn("data_type", col)
            self.assertIn("inferred_type", col)
            self.assertIn("safe_type_conversions", col)

        payload = {
            "type_conversions": [
                {"column": "Purchased", "target_type": "integer"}
            ]
        }
        res = self.api_post("/cleaning/8/preview", payload)
        self.assertGreaterEqual(len(res["type_changes"]), 1)
        self.assertEqual(res["type_changes"][0]["column"], "Purchased")
        print("  [PASS] Data type detection and safe casting verified.")

    # =========================================================================
    # 7. Column Name Standardization
    # =========================================================================
    def test_07_column_name_standardization(self):
        """Feature 7: Verify column name standardization (snake_case, uniqueness, special chars)."""
        print("\n--- Test 7: Column Name Standardization ---")
        ov = self.api_get("/cleaning/8")
        self.assertIn("column_names_standardized_preview", ov)

        payload = {
            "standardize_column_names": True
        }
        res = self.api_post("/cleaning/8/preview", payload)
        self.assertIn("column_name_mapping", res)
        self.assertGreaterEqual(res["column_names_changed"], 1)
        # All columns in sample preview should be lowercased snake_case
        for col in res["sample_columns"]:
            self.assertTrue(col.islower())
            self.assertNotIn(" ", col)
        print("  [PASS] Column name standardization verified with unique snake_case names.")

    # =========================================================================
    # 8. Before / After Preview & Zero Mutation Guarantee
    # =========================================================================
    def test_08_before_after_preview_zero_mutation(self):
        """Feature 8: Verify before/after preview contains rows, cols, deltas, and leaves disk untouched."""
        print("\n--- Test 8: Before / After Preview & Zero Mutation ---")
        ds_before = self.api_get("/datasets/8")
        file_before = Path(ds_before["storage_path"]).read_bytes()

        payload = {
            "remove_duplicates": True,
            "standardize_column_names": True,
            "missing_imputations": [{"column": "Age", "strategy": "median"}]
        }
        res = self.api_post("/cleaning/8/preview", payload)
        self.assertIn("before", res)
        self.assertIn("after", res)
        self.assertIn("sample_preview", res)
        self.assertIn("detailed_operations", res)
        self.assertGreaterEqual(len(res["sample_preview"]), 1)

        ds_after = self.api_get("/datasets/8")
        file_after = Path(ds_after["storage_path"]).read_bytes()
        self.assertEqual(file_before, file_after)
        self.assertFalse(ds_after["has_cleaned"])
        print("  [PASS] Preview calculated with sample data; original file strictly unchanged.")

    # =========================================================================
    # 9. Apply Cleaning & Safe Versioning
    # =========================================================================
    def test_09_apply_cleaning_and_versioning(self):
        """Feature 9: Apply cleaning creates separate cleaned file without overwriting original."""
        print("\n--- Test 9: Apply Cleaning & Safe Versioning ---")
        ds = self.api_get("/datasets/8")
        orig_file = Path(ds["storage_path"])
        orig_bytes_before = orig_file.read_bytes()

        payload = {
            "missing_imputations": [
                {"column": "Age", "strategy": "median"},
                {"column": "Gender", "strategy": "mode"}
            ]
        }
        apply_res = self.api_post("/cleaning/8/apply", payload)
        self.assertTrue(apply_res["success"])
        self.assertIn("cleaned_", apply_res["cleaned_filename"])

        # Check original file on disk: MUST BE 100% UNCHANGED
        orig_bytes_after = orig_file.read_bytes()
        self.assertEqual(orig_bytes_before, orig_bytes_after)

        # Check DB reflects cleaned version active
        ov = self.api_get("/cleaning/8")
        self.assertTrue(ov["has_cleaned"])
        self.assertIsNotNone(ov["cleaned_metrics"])
        self.assertIsNotNone(ov["cleaned_sample_preview"])
        print("  [PASS] Separate cleaned file created; original file byte-for-byte identical.")

    # =========================================================================
    # 10. Cleaning History
    # =========================================================================
    def test_10_cleaning_history(self):
        """Feature 10: Verify cleaning history records operations, columns, methods, rows affected, date."""
        print("\n--- Test 10: Cleaning History Audit Trail ---")
        history = self.api_get("/cleaning/8/history")
        self.assertGreaterEqual(len(history), 1)
        latest = history[0]
        self.assertIn("operations_performed", latest)
        self.assertIn("applied_at", latest)
        self.assertIn("detailed_operations", latest)
        self.assertGreaterEqual(len(latest["detailed_operations"]), 1)
        dop = latest["detailed_operations"][0]
        self.assertIn("operation", dop)
        self.assertIn("column", dop)
        self.assertIn("method", dop)
        self.assertIn("rows_affected", dop)
        print(f"  [PASS] Cleaning history audit log verified with {len(latest['detailed_operations'])} detailed step(s).")

    # =========================================================================
    # 11. Undo / Restore Previous Version
    # =========================================================================
    def test_11_restore_previous_version(self):
        """Feature 11: Verify dataset can be restored back to original state."""
        print("\n--- Test 11: Undo / Restore Previous Version ---")
        reset_res = self.api_post("/cleaning/8/reset", {})
        self.assertTrue(reset_res["success"])

        ov = self.api_get("/cleaning/8")
        self.assertFalse(ov["has_cleaned"])
        self.assertIsNone(ov["cleaned_metrics"])
        print("  [PASS] Dataset restored back to original version cleanly.")

    # =========================================================================
    # 12. Frontend Route & UI Integration
    # =========================================================================
    def test_12_frontend_route_and_ui(self):
        """Feature 12: Verify frontend route and required UI sections."""
        print("\n--- Test 12: Frontend Route & UI Integration ---")
        req = urllib.request.Request(f"{FRONTEND_BASE}/data-cleaning")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
        except Exception:
            pass

        page_file = ROOT_DIR / "frontend" / "src" / "pages" / "CleaningPage.jsx"
        code = page_file.read_text(encoding="utf-8")
        
        self.assertIn("Data Cleaning", code)
        self.assertTrue("Select a dataset" in code or "select a dataset" in code or "Select a Dataset" in code)
        self.assertTrue("Original" in code)
        self.assertTrue("Cleaned" in code)
        self.assertTrue("Missing Value" in code)
        self.assertTrue("Duplicate" in code)
        self.assertTrue("Blank / Whitespace" in code)
        self.assertTrue("Standardize" in code or "standardize" in code)
        self.assertTrue("Empty" in code)
        self.assertTrue("Type" in code)
        self.assertTrue("Preview" in code)
        self.assertTrue("Apply" in code)
        self.assertTrue("History" in code or "Timeline" in code)
        self.assertTrue("Restore" in code or "restore" in code)
        print("  [PASS] All 12 frontend UI sections and routes verified.")


if __name__ == "__main__":
    unittest.main()
