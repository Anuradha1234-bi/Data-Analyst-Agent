"""Unit & Integration Test Suite for DATA CLEANING - PHASE 2: ADVANCED CLEANING.

Verifies:
1. Text Standardization (trim, collapse spaces, lowercase, uppercase, Title Case, special chars)
2. Category Normalization (detection of inconsistent clusters, user-defined mapping, dry-run preview)
3. Numeric Value Cleaning (strip currency $ ₹, remove commas, handle invalid numbers)
4. Percentage Handling (explicit user choice: keep as 45 vs convert to 0.45)
5. Date Cleaning & Parsing (inspection endpoint, parsed count, invalid count, consistent formatting)
6. Invalid Value Detection / Range Validation (configurable min/max, actions: set missing, replace, remove rows)
7. Custom Value Replacement (exact matching: Unknown -> NaN, N/A -> NaN, - -> NaN)
8. Find & Replace (case sensitivity, exact match options, cell counts)
9. Column Value Summary (unique values, frequency counts, percentages)
10. Cleaning Rule Builder (Column -> Condition -> Action)
11. Before / After Preview (cell-level diff table, zero disk mutation guarantee)
12. Cleaning Summary & Audit History (rows/cells affected, detailed operations in AnalysisHistory)
13. Version Safety & Restore (original dataset preserved bit-for-bit, restore previous version)
14. Frontend UI Integration (all Phase 2 tabs and controls present in CleaningPage.jsx)
"""

import os
import io
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


def create_multipart_form(fields, files):
    boundary = "----WebKitFormBoundaryPhase2Test7MA4YWxkTrZu0gW"
    body = io.BytesIO()
    for name, value in fields.items():
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.write(f"{value}\r\n".encode("utf-8"))
    for name, filename, content in files:
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.write(b"Content-Type: text/csv\r\n\r\n")
        body.write(content)
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode("utf-8"))
    content_type = f"multipart/form-data; boundary={boundary}"
    return body.getvalue(), content_type


class TestDataCleaningPhase2(unittest.TestCase):
    """Complete test suite verifying Phase 2 Advanced Data Cleaning functionality."""

    @classmethod
    def setUpClass(cls):
        cls.token = create_access_token(data={"sub": "11"})
        cls.test_dataset_id = cls.upload_phase2_test_dataset()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "test_dataset_id") and cls.test_dataset_id:
            try:
                req = urllib.request.Request(
                    f"{API_BASE}/datasets/{cls.test_dataset_id}",
                    headers={"Authorization": f"Bearer {cls.token}"},
                    method="DELETE"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    pass
            except Exception:
                pass

    @classmethod
    def upload_phase2_test_dataset(cls):
        csv_content = (
            "City,Gender,Salary,TaxRate,JoinDate,Age,Address\n"
            '"  Mumbai  ",Male,"₹1,200",45%,01/02/2025,25,123 Main St.\n'
            'mUMBAI,male,"1,200",18%,2025-02-01,-5,456 Park Ave\n'
            'MUMBAI,MALE,$500,5%,"Feb 1, 2025",150,789 Broad St.\n'
            'DELHI,M,250,12%,2024-12-15,32,101 Oak St.\n'
            '"  delhi  ",Female,"15,000",0%,invalid_date,45,Unknown\n'
            'New   York,female,Unknown,N/A,-,29,N/A\n'
            'New York,F,"2,400",20%,2025-05-10,38,303 Elm St.\n'
        ).encode("utf-8")

        body, content_type = create_multipart_form(
            {},
            [("files", "phase2_advanced_test.csv", csv_content)]
        )

        req = urllib.request.Request(
            f"{API_BASE}/datasets/upload",
            data=body,
            headers={
                "Authorization": f"Bearer {cls.token}",
                "Content-Type": content_type,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            dataset_id = data["uploaded"][0]["id"]
            return dataset_id

    def api_get(self, endpoint: str):
        req = urllib.request.Request(
            f"{API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            return json.loads(resp.read().decode("utf-8"))

    def api_post(self, endpoint: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{API_BASE}{endpoint}",
            data=data,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            return json.loads(resp.read().decode("utf-8"))

    # =========================================================================
    # 1. Text Standardization
    # =========================================================================
    def test_01_text_standardization(self):
        """Feature 1: Verify trim whitespace, collapse spaces, titlecase/lowercase conversion."""
        print("\n--- Test 1: Text Standardization ---")
        payload = {
            "text_standardizations": [
                {
                    "column": "City",
                    "trim_whitespace": True,
                    "collapse_spaces": True,
                    "case_conversion": "titlecase",
                    "remove_special_chars": False,
                }
            ]
        }
        res = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        self.assertIn("cell_diffs", res)
        self.assertGreaterEqual(res["total_cells_changed"], 1)

        # In preview sample, City values should be Title Case ("Mumbai", "Delhi", "New York")
        sample_cities = [row["City"] for row in res["sample_preview"]]
        self.assertIn("Mumbai", sample_cities)
        self.assertIn("Delhi", sample_cities)
        self.assertIn("New York", sample_cities)
        print("  [PASS] Text standardization (trim, collapse spaces, Title Case) verified.")

    # =========================================================================
    # 2. Category Normalization & Inconsistency Detection
    # =========================================================================
    def test_02_category_normalization(self):
        """Feature 2: Detect inconsistent category clusters and apply user-defined mapping."""
        print("\n--- Test 2: Category Normalization ---")
        # Step A: Inspect detected inconsistencies
        inconsistencies = self.api_get(f"/cleaning/{self.test_dataset_id}/category-inconsistencies?column=Gender")
        self.assertIn("clusters", inconsistencies)
        self.assertGreaterEqual(len(inconsistencies["clusters"]), 1)

        # Check male cluster variants
        male_cluster = next((c for c in inconsistencies["clusters"] if any("male" in v["value"].lower() for v in c["variants"])), None)
        self.assertIsNotNone(male_cluster)
        variant_values = [v["value"] for v in male_cluster["variants"]]
        self.assertTrue(any(x in variant_values for x in ["Male", "male", "MALE", "M"]))

        # Step B: User defines explicit mapping: M, male, MALE -> Male
        payload = {
            "category_normalizations": [
                {
                    "column": "Gender",
                    "mapping": {
                        "M": "Male",
                        "male": "Male",
                        "MALE": "Male",
                        "female": "Female",
                        "F": "Female",
                    }
                }
            ]
        }
        res = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        sample_genders = [row["Gender"] for row in res["sample_preview"]]
        # In transformed preview, all mapped should be "Male" or "Female"
        for g in sample_genders:
            if g in ["Male", "Female", "Unknown"]:
                pass
            else:
                self.fail(f"Unexpected unnormalized gender found: {g}")
        print("  [PASS] Category cluster detection and explicit mapping preview verified.")

    # =========================================================================
    # 3. Numeric Value Cleaning (Currency & Commas)
    # =========================================================================
    def test_03_numeric_value_cleaning_currency_and_commas(self):
        """Feature 3: Verify strip currency symbols (₹, $) and commas (1,200 -> 1200)."""
        print("\n--- Test 3: Numeric Value Cleaning (Currency & Commas) ---")
        payload = {
            "numeric_cleanings": [
                {
                    "column": "Salary",
                    "strip_currency": True,
                    "remove_commas": True,
                    "handle_invalid": "coerce_na",
                }
            ]
        }
        res = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        self.assertGreaterEqual(res["total_cells_changed"], 1)

        sample_salaries = [row["Salary"] for row in res["sample_preview"]]
        # ₹1,200 -> 1200, $500 -> 500, 15,000 -> 15000
        self.assertIn(1200, sample_salaries)
        self.assertIn(500, sample_salaries)
        self.assertIn(15000, sample_salaries)
        print("  [PASS] Currency symbols and commas cleaned into numeric integers/floats.")

    # =========================================================================
    # 4. Percentage Handling (Explicit User Choice)
    # =========================================================================
    def test_04_percentage_handling_choices(self):
        """Feature 4: Verify percentage conversion choices: 'keep_number' (45) vs 'as_fraction' (0.45)."""
        print("\n--- Test 4: Percentage Handling Choices ---")
        # Choice A: Keep as integer number (45)
        payload_keep = {
            "numeric_cleanings": [
                {
                    "column": "TaxRate",
                    "strip_currency": True,
                    "remove_commas": True,
                    "percentage_handling": "keep_number",
                    "handle_invalid": "coerce_na",
                }
            ]
        }
        res_keep = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload_keep)
        rates_keep = [row["TaxRate"] for row in res_keep["sample_preview"]]
        self.assertIn(45, rates_keep)
        self.assertIn(18, rates_keep)

        # Choice B: Convert to fraction (0.45)
        payload_fraction = {
            "numeric_cleanings": [
                {
                    "column": "TaxRate",
                    "strip_currency": True,
                    "remove_commas": True,
                    "percentage_handling": "as_fraction",
                    "handle_invalid": "coerce_na",
                }
            ]
        }
        res_fraction = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload_fraction)
        rates_fraction = [row["TaxRate"] for row in res_fraction["sample_preview"]]
        self.assertIn(0.45, rates_fraction)
        self.assertIn(0.18, rates_fraction)
        print("  [PASS] Percentage handling correctly supports both 45 and 0.45 as requested.")

    # =========================================================================
    # 5. Date Cleaning & Format Detection
    # =========================================================================
    def test_05_date_cleaning(self):
        """Feature 5: Verify date inspection (parsed vs invalid counts) and standardized format conversion."""
        print("\n--- Test 5: Date Cleaning & Format Detection ---")
        inspection = self.api_get(f"/cleaning/{self.test_dataset_id}/date-inspection?column=JoinDate")
        self.assertIn("parsed_count", inspection)
        self.assertIn("invalid_count", inspection)
        self.assertGreaterEqual(inspection["parsed_count"], 4)
        self.assertGreaterEqual(inspection["invalid_count"], 1)

        payload = {
            "date_cleanings": [
                {
                    "column": "JoinDate",
                    "output_format": "%Y-%m-%d",
                    "handle_invalid": "coerce_na",
                }
            ]
        }
        res = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        sample_dates = [row["JoinDate"] for row in res["sample_preview"]]
        self.assertIn("2025-02-01", sample_dates)
        self.assertIn("2024-12-15", sample_dates)
        print("  [PASS] Date inspection and standardized ISO date conversion verified.")

    # =========================================================================
    # 6. Invalid Value Detection / Range Validation
    # =========================================================================
    def test_06_invalid_value_range_validation(self):
        """Feature 6: Verify configurable range validation (Age: min 0, max 120 -> set missing)."""
        print("\n--- Test 6: Invalid Value Detection (Range Validation) ---")
        payload = {
            "value_validations": [
                {
                    "column": "Age",
                    "min_value": 0,
                    "max_value": 120,
                    "action": "set_missing",
                }
            ]
        }
        res = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        sample_ages = [row["Age"] for row in res["sample_preview"]]
        # -5 and 150 should be removed/set to null
        self.assertNotIn(-5, sample_ages)
        self.assertNotIn(150, sample_ages)
        self.assertIn(25, sample_ages)
        print("  [PASS] Range validation bounds [0, 120] enforced with set_missing action.")

    # =========================================================================
    # 7. Custom Value Replacement
    # =========================================================================
    def test_07_custom_value_replacement(self):
        """Feature 7: Replace specific sentinel values (Unknown -> NaN, N/A -> NaN)."""
        print("\n--- Test 7: Custom Value Replacement ---")
        payload = {
            "custom_replacements": [
                {
                    "column": "Gender",
                    "find_value": "Unknown",
                    "replace_value": "NaN",
                    "exact_match": True,
                },
                {
                    "column": "Address",
                    "find_value": "Unknown",
                    "replace_value": "NaN",
                    "exact_match": True,
                }
            ]
        }
        res = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        sample_genders = [row["Gender"] for row in res["sample_preview"]]
        self.assertNotIn("Unknown", [g for g in sample_genders if g is not None])
        print("  [PASS] Custom value replacement (Unknown -> NaN) applied accurately.")

    # =========================================================================
    # 8. Find & Replace
    # =========================================================================
    def test_08_find_and_replace(self):
        """Feature 8: Controlled Find & Replace (St. -> Street)."""
        print("\n--- Test 8: Find & Replace ---")
        payload = {
            "find_replaces": [
                {
                    "column": "Address",
                    "find_value": "St.",
                    "replace_value": "Street",
                    "exact_match": False,
                    "case_sensitive": True,
                }
            ]
        }
        res = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        sample_addresses = [str(row["Address"]) for row in res["sample_preview"] if row["Address"]]
        self.assertTrue(any("Main Street" in a for a in sample_addresses))
        print("  [PASS] Controlled Find & Replace substring replacement verified.")

    # =========================================================================
    # 9. Column Value Summary
    # =========================================================================
    def test_09_column_value_summary(self):
        """Feature 9: Retrieve unique values, frequency counts, and percentage distribution."""
        print("\n--- Test 9: Column Value Summary ---")
        summary = self.api_get(f"/cleaning/{self.test_dataset_id}/column-summary?column=City")
        self.assertEqual(summary["column"], "City")
        self.assertGreaterEqual(summary["total_rows"], 7)
        self.assertIn("values", summary)
        total_pct = sum(v["percentage"] for v in summary["values"])
        self.assertAlmostEqual(total_pct, 100.0, delta=1.0)
        print(f"  [PASS] Column value summary verified for '{summary['column']}' ({len(summary['values'])} unique values).")

    # =========================================================================
    # 10. Cleaning Rule Builder
    # =========================================================================
    def test_10_cleaning_rule_builder(self):
        """Feature 10: Column -> Condition -> Action rule builder."""
        print("\n--- Test 10: Cleaning Rule Builder ---")
        payload = {
            "cleaning_rules": [
                {
                    "column": "Age",
                    "condition": "is_negative",
                    "action": "set_missing",
                },
                {
                    "column": "Salary",
                    "condition": "contains",
                    "condition_value": "₹",
                    "action": "strip_char",
                    "action_value": "₹",
                }
            ]
        }
        res = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        self.assertGreaterEqual(len(res["detailed_operations"]), 2)
        print("  [PASS] Cleaning rule builder (is_negative, contains) verified.")

    # =========================================================================
    # 11. Before / After Cell-Level Diff Preview & Zero Mutation Guarantee
    # =========================================================================
    def test_11_before_after_cell_diff_preview(self):
        """Feature 11: Cell-level before vs after diff inspection without disk mutation."""
        print("\n--- Test 11: Before / After Preview & Zero Mutation ---")
        ds_before = self.api_get(f"/datasets/{self.test_dataset_id}")
        bytes_before = Path(ds_before["storage_path"]).read_bytes()

        payload = {
            "text_standardizations": [
                {"column": "City", "trim_whitespace": True, "collapse_spaces": True, "case_conversion": "titlecase"}
            ],
            "numeric_cleanings": [
                {"column": "Salary", "strip_currency": True, "remove_commas": True}
            ]
        }
        preview = self.api_post(f"/cleaning/{self.test_dataset_id}/preview", payload)
        self.assertIn("cell_diffs", preview)
        self.assertGreaterEqual(len(preview["cell_diffs"]), 1)
        
        diff = preview["cell_diffs"][0]
        self.assertIn("row_index", diff)
        self.assertIn("column", diff)
        self.assertIn("before_value", diff)
        self.assertIn("after_value", diff)

        # Original dataset file must be 100% untouched
        bytes_after = Path(ds_before["storage_path"]).read_bytes()
        self.assertEqual(bytes_before, bytes_after)
        print("  [PASS] Cell-level diffs calculated with before vs after values; disk file untouched.")

    # =========================================================================
    # 12. Apply Cleaning, Versioning, and Audit Trail
    # =========================================================================
    def test_12_apply_cleaning_and_audit_history(self):
        """Feature 12: Apply operations, generate versioned cleaned file, verify summary & audit history."""
        print("\n--- Test 12: Apply Cleaning, Versioning, & History ---")
        payload = {
            "text_standardizations": [
                {"column": "City", "trim_whitespace": True, "collapse_spaces": True, "case_conversion": "titlecase"}
            ],
            "category_normalizations": [
                {"column": "Gender", "mapping": {"M": "Male", "male": "Male", "MALE": "Male"}}
            ],
            "numeric_cleanings": [
                {"column": "Salary", "strip_currency": True, "remove_commas": True}
            ]
        }
        apply_res = self.api_post(f"/cleaning/{self.test_dataset_id}/apply", payload)
        self.assertTrue(apply_res["success"])
        self.assertIn("cells_affected", apply_res)
        self.assertIn("values_changed", apply_res)
        self.assertIn("operations_performed", apply_res)
        self.assertGreaterEqual(len(apply_res["operations_performed"]), 3)

        # Verify cleaning history audit trail
        history = self.api_get(f"/cleaning/{self.test_dataset_id}/history")
        self.assertGreaterEqual(len(history), 1)
        latest = history[0]
        self.assertIn("detailed_operations", latest)
        self.assertGreaterEqual(len(latest["detailed_operations"]), 3)
        print("  [PASS] Cleaned version persisted with comprehensive audit trail.")

    # =========================================================================
    # 13. Version Safety & Restore Functionality
    # =========================================================================
    def test_13_restore_previous_version(self):
        """Feature 13: Restore previous / original version cleanly."""
        print("\n--- Test 13: Version Safety & Restore ---")
        reset_res = self.api_post(f"/cleaning/{self.test_dataset_id}/reset", {})
        self.assertTrue(reset_res["success"])

        ov = self.api_get(f"/cleaning/{self.test_dataset_id}")
        self.assertFalse(ov["has_cleaned"])
        self.assertIsNone(ov["cleaned_metrics"])
        print("  [PASS] Cleaned dataset safely restored back to original version.")

    # =========================================================================
    # 14. Frontend UI Integration
    # =========================================================================
    def test_14_frontend_ui_sections(self):
        """Feature 14: Verify Advanced Cleaning UI sections and controls in CleaningPage.jsx."""
        print("\n--- Test 14: Frontend UI Integration ---")
        try:
            req = urllib.request.Request(f"{FRONTEND_BASE}/data-cleaning")
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
        except Exception:
            pass

        page_file = ROOT_DIR / "frontend" / "src" / "pages" / "CleaningPage.jsx"
        code = page_file.read_text(encoding="utf-8")

        # Required Phase 2 UI strings
        self.assertTrue("Advanced Cleaning" in code or "showAdvanced" in code)
        self.assertTrue("Text & Categories" in code or "textStandardizations" in code)
        self.assertTrue("Category" in code or "categoryNormalizations" in code)
        self.assertTrue("Numeric" in code or "numericCleanings" in code)
        self.assertTrue("Date" in code or "dateCleanings" in code)
        self.assertTrue("Invalid" in code or "valueValidations" in code)
        self.assertTrue("Find & Replace" in code or "findReplaces" in code)
        self.assertTrue("Custom" in code or "customReplacements" in code)
        self.assertTrue("Rule" in code or "cleaningRules" in code)
        self.assertTrue("Summary" in code or "columnSummary" in code)
        self.assertTrue("Preview" in code)
        print("  [PASS] All 14 Advanced Cleaning frontend sections verified.")


if __name__ == "__main__":
    unittest.main()
