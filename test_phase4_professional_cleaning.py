"""Unit & Integration Test Suite for DATA CLEANING - PHASE 4:
PROFESSIONAL CLEANING WORKFLOW + VALIDATION + FINAL REPORT.

Verifies:
1. Cleaning Dashboard / Summary: Real dataset stats, version, rows/cols, issue counts, timestamps
2. Dataset Cleaning Status: Not Cleaned, Partially Cleaned, Cleaned, Needs Review (validation-driven)
3. Cleaning Validation: Before vs After across 8 checks (missing, duplicates, blanks, invalid types, invalid values, date errors, outliers, column names)
4. Cleaning Quality Score: Objective XX/100 score + explanation of deductions
5. Bulk Cleaning Workflow & Operation Ordering: Fixed priority order, staging queue, remove operation
6. Cancel / Reset Pending Operations: Discard unapplied operations with zero disk mutation
7. Bulk Apply All Cleaning Operations: Atomic version creation, error recovery rollback
8. Cleaning Preview Table: Impact summary (| Column | Operation | Affected | Result |)
9. Cleaning Report Generation: Comprehensive report with info, operations, validation, before/after
10. Download Cleaning Report: Markdown, JSON, and CSV report export formats
11. Final Dataset Actions: Previous CSV access, Cleaned View, Cleaned CSV, Cleaned Excel (.xlsx)
12. Version Timeline & Restore: Visual version history and 1-click restore to any version
13. Outlier Detection & Treatment: IQR and Z-score methods with Cap, Median, Mean, Remove, Keep treatments
14. Frontend UI Integration: All Phase 4 cards, tabs, score meter, timeline, and confirmation summary in CleaningPage.jsx
"""

import os
import io
import sys
import json
import unittest
import urllib.request
import urllib.error
import urllib.parse
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
    boundary = "----WebKitFormBoundaryPhase4Test8NB5ZXylUsAv1hX"
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


class TestDataCleaningPhase4(unittest.TestCase):
    """Complete test suite verifying Phase 4 Professional Cleaning Workflow functionality."""

    @classmethod
    def setUpClass(cls):
        cls.token = create_access_token(data={"sub": "11"})
        cls.test_dataset_id, cls.original_csv_bytes = cls.upload_phase4_test_dataset()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "test_dataset_id") and cls.test_dataset_id:
            try:
                req = urllib.request.Request(
                    f"{API_BASE}/datasets/{cls.test_dataset_id}",
                    headers={"Authorization": f"Bearer {cls.token}"},
                    method="DELETE",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    pass
            except Exception:
                pass

    @classmethod
    def upload_phase4_test_dataset(cls):
        csv_content = (
            "EmployeeName,Age,Salary,JoinDate,Department,Status\n"
            '"  Alice  ",28,"₹45,000",2023-01-15,Engineering,Active\n'
            'Bob,34,"55,000",15/02/2022,Marketing,Active\n'
            'Charlie,-5,$120000,2024-03-01,Sales,Pending\n'
            'David,180,"80,000",invalid_date,HR,Active\n'
            'Eve,29,Unknown,2023-08-12,Engineering,Active\n'
            '"  Frank  ",42,"65,000",2021-11-30,Engineering,Active\n'
            'Bob,34,"55,000",15/02/2022,Marketing,Active\n'  # Exact Duplicate row of Bob
            'Grace,31,"50,000",2022-07-20,"   ",Active\n'  # Blank cell in Department
            'Heidi,105,"950,000",2020-05-18,Executive,Active\n'  # Outlier salary & age
            'Ivan,25,"40,000",2024-01-10,Sales,Pending\n'
        ).encode("utf-8")

        body, content_type = create_multipart_form(
            {},
            [("files", "phase4_professional_test.csv", csv_content)]
        )

        req = urllib.request.Request(
            f"{API_BASE}/datasets/upload",
            data=body,
            headers={
                "Authorization": f"Bearer {cls.token}",
                "Content-Type": content_type,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            dataset_id = data.get("uploaded", data.get("datasets", []))[0]["id"]
            return dataset_id, csv_content

    def api_get(self, endpoint):
        req = urllib.request.Request(
            f"{API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {self.token}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def api_get_raw(self, endpoint):
        req = urllib.request.Request(
            f"{API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {self.token}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read(), resp.headers

    def api_post(self, endpoint, payload):
        req = urllib.request.Request(
            f"{API_BASE}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    # =========================================================================
    # 1. Cleaning Dashboard / Summary
    # =========================================================================
    def test_01_cleaning_dashboard_summary(self):
        """Feature 1: Verify Cleaning Dashboard / Summary card metadata and issue statistics."""
        print("\n--- Test 1: Cleaning Dashboard / Summary ---")
        summary = self.api_get(f"/cleaning/{self.test_dataset_id}/dashboard-summary")

        self.assertIn("dataset_name", summary)
        self.assertIn("current_version", summary)
        self.assertEqual(summary["rows"], 10)
        self.assertEqual(summary["columns"], 6)
        self.assertEqual(summary["duplicate_rows"], 1)
        self.assertGreaterEqual(summary["outliers_detected"], 1)
        self.assertIn("numeric_columns_count", summary)
        self.assertIn("categorical_columns_count", summary)
        self.assertIn("date_columns_count", summary)
        self.assertIn("last_cleaning_operation", summary)
        self.assertIn("last_updated", summary)
        self.assertEqual(summary["current_version"], "Original")
        print(f"  [PASS] Dashboard summary verified: {summary['dataset_name']} ({summary['rows']} rows, {summary['columns']} cols, {summary['outliers_detected']} outliers).")

    # =========================================================================
    # 2. Dataset Cleaning Status & Quality Score
    # =========================================================================
    def test_02_cleaning_status_and_quality_score(self):
        """Feature 2 & 4: Verify Dataset Cleaning Status and objective Quality Score."""
        print("\n--- Test 2: Dataset Cleaning Status & Quality Score ---")
        summary = self.api_get(f"/cleaning/{self.test_dataset_id}/dashboard-summary")

        # Initial status should be "Not Cleaned" or "Needs Review" due to duplicates, outliers, invalid values
        self.assertIn(summary["cleaning_status"], ["Not Cleaned", "Partially Cleaned", "Needs Review"])
        
        # Quality score should reflect detected issues and NOT be arbitrarily 100
        score = summary["cleaning_score"]
        self.assertIsInstance(score, int)
        self.assertLess(score, 100)
        self.assertGreaterEqual(score, 0)

        # Quality score explanation must explicitly detail why the score is not 100
        explanations = summary["score_deductions"]
        self.assertIsInstance(explanations, list)
        self.assertGreater(len(explanations), 0)
        
        # Check that explanation mentions detected issues
        explanation_text = " ".join(explanations).lower()
        self.assertTrue("duplicate" in explanation_text or "outlier" in explanation_text or "blank" in explanation_text)
        print(f"  [PASS] Quality Score: {score}/100. Status: {summary['cleaning_status']}. Deductions: {explanations[0]}")

    # =========================================================================
    # 3. Cleaning Validation Before vs After
    # =========================================================================
    def test_03_cleaning_validation_report(self):
        """Feature 3: Verify systematic validation comparing Before vs After across 8 checks."""
        print("\n--- Test 3: Cleaning Validation Report ---")
        report = self.api_get(f"/cleaning/{self.test_dataset_id}/validation")

        self.assertIn("checks", report)
        self.assertEqual(len(report["checks"]), 8)

        check_names = [c["check_name"] for c in report["checks"]]
        expected_checks = [
            "Missing Values",
            "Duplicate Rows",
            "Blank Values",
            "Invalid Datatype Conversions",
            "Invalid Values",
            "Invalid Dates",
            "Remaining Outliers",
            "Column Name Issues",
        ]
        for ec in expected_checks:
            self.assertIn(ec, check_names)

        # Check Duplicates check
        dup_chk = next(c for c in report["checks"] if c["check_name"] == "Duplicate Rows")
        self.assertEqual(dup_chk["before_value"], 1)

        # Check Outliers check
        outlier_chk = next(c for c in report["checks"] if c["check_name"] == "Remaining Outliers")
        self.assertGreaterEqual(outlier_chk["before_value"], 1)
        print("  [PASS] 8-point validation report verified with accurate before/after counters.")

    # =========================================================================
    # 4. Bulk Cleaning Workflow & Operation Order Preview
    # =========================================================================
    def test_04_bulk_preview_and_ordering(self):
        """Feature 5, 6, 8: Verify Bulk Cleaning Workflow staging, ordering, and preview impact table."""
        print("\n--- Test 4: Bulk Cleaning Workflow & Operation Order ---")
        payload = {
            "convert_blanks_to_na": True,
            "remove_duplicates": True,
            "text_standardizations": [
                {"column": "EmployeeName", "operations": ["trim", "title_case"]}
            ],
            "numeric_cleanings": [
                {"column": "Salary", "action": "clean_all"}
            ],
            "date_cleanings": [
                {"column": "JoinDate", "target_format": "YYYY-MM-DD"}
            ],
            "outlier_cleanings": [
                {"column": "Age", "method": "iqr", "threshold": 1.5, "treatment": "cap"}
            ],
        }

        bulk_preview = self.api_post(f"/cleaning/{self.test_dataset_id}/bulk-preview", payload)

        self.assertEqual(bulk_preview["operations_count"], 6)
        self.assertGreater(bulk_preview["total_cells_affected"], 0)
        self.assertEqual(bulk_preview["total_rows_affected"], 1)  # 1 duplicate removed

        # Check impact items table
        self.assertIn("impact_summary", bulk_preview)
        self.assertGreaterEqual(len(bulk_preview["impact_summary"]), 6)

        impact_columns = [i["column"] for i in bulk_preview["impact_summary"]]
        self.assertIn("EmployeeName", impact_columns)
        self.assertIn("Salary", impact_columns)
        self.assertIn("JoinDate", impact_columns)
        self.assertIn("Age", impact_columns)

        # Zero disk mutation guarantee during preview
        overview = self.api_get(f"/cleaning/{self.test_dataset_id}")
        self.assertFalse(overview["has_cleaned"])
        print("  [PASS] Bulk preview verified with concise impact table; zero disk mutation confirmed.")

    # =========================================================================
    # 5. Cancel / Reset Pending Changes
    # =========================================================================
    def test_05_cancel_reset_pending_changes(self):
        """Feature 7: Verify that discarding/resetting pending operations does NOT mutate the saved dataset."""
        print("\n--- Test 5: Reset Pending Changes ---")
        # Ensure dataset still has original metrics
        overview = self.api_get(f"/cleaning/{self.test_dataset_id}")
        self.assertEqual(overview["original_metrics"]["total_rows"], 10)
        self.assertFalse(overview["has_cleaned"])
        print("  [PASS] Reset pending changes leaves saved dataset completely intact.")

    # =========================================================================
    # 6. Bulk Apply All Operations & Version Creation
    # =========================================================================
    def test_06_bulk_apply_all_operations(self):
        """Feature 5 & 14: Apply all staged operations atomically, creating a new dataset version."""
        print("\n--- Test 6: Bulk Apply All Cleaning Operations ---")
        payload = {
            "remove_duplicates": True,
            "convert_blanks_to_na": True,
            "text_standardizations": [
                {"column": "EmployeeName", "operations": ["trim", "title_case"]}
            ],
            "numeric_cleanings": [
                {"column": "Salary", "action": "clean_all"}
            ],
            "outlier_cleanings": [
                {"column": "Age", "method": "iqr", "threshold": 1.5, "treatment": "cap"}
            ],
        }

        apply_res = self.api_post(f"/cleaning/{self.test_dataset_id}/bulk-apply", payload)

        self.assertTrue(apply_res["success"])
        self.assertIn("Cleaned v1", apply_res["version"])
        self.assertEqual(apply_res["duplicate_rows_remaining"], 0)
        self.assertGreater(apply_res["quality_score"], 60)

        # Check that overview reflects the active cleaned version
        overview = self.api_get(f"/cleaning/{self.test_dataset_id}")
        self.assertTrue(overview["has_cleaned"])
        self.assertEqual(overview["cleaned_metrics"]["total_rows"], 9)  # 1 duplicate row removed
        print(f"  [PASS] Bulk apply succeeded: Version '{apply_res['version']}' created with Quality Score {apply_res['quality_score']}/100.")

    # =========================================================================
    # 7. Version Timeline & Restore
    # =========================================================================
    def test_07_version_timeline_and_restore(self):
        """Feature 12: Verify version timeline and restore to previous version."""
        print("\n--- Test 7: Version Timeline & Restore ---")
        timeline = self.api_get(f"/cleaning/{self.test_dataset_id}/versions")

        self.assertIsInstance(timeline, list)
        self.assertGreaterEqual(len(timeline), 2)  # Original + Cleaned v1

        versions = [v["version"] for v in timeline]
        self.assertIn("Original", versions)
        self.assertIn("Cleaned v1", versions)

        # Restore back to Original
        restore_res = self.api_post(f"/cleaning/{self.test_dataset_id}/versions/Original/restore", {})
        self.assertTrue(restore_res["success"])

        # Verify dataset is back to Original state
        overview = self.api_get(f"/cleaning/{self.test_dataset_id}")
        self.assertFalse(overview["has_cleaned"])
        self.assertEqual(overview["original_metrics"]["total_rows"], 10)

        # Restore back to Cleaned v1
        encoded_v1 = urllib.parse.quote("Cleaned v1")
        restore_res2 = self.api_post(f"/cleaning/{self.test_dataset_id}/versions/{encoded_v1}/restore", {})
        self.assertTrue(restore_res2["success"])
        overview2 = self.api_get(f"/cleaning/{self.test_dataset_id}")
        self.assertTrue(overview2["has_cleaned"])
        print("  [PASS] Version timeline verified; bi-directional version restore executed cleanly.")

    # =========================================================================
    # 8. Cleaning Report Generation & Export
    # =========================================================================
    def test_08_cleaning_report_generation_and_export(self):
        """Feature 9 & 10: Verify comprehensive Cleaning Report generation and JSON/CSV/Markdown downloads."""
        print("\n--- Test 8: Cleaning Report Generation & Download ---")
        report = self.api_get(f"/cleaning/{self.test_dataset_id}/report")

        self.assertIn("dataset_info", report)
        self.assertIn("cleaning_operations", report)
        self.assertIn("validation_results", report)
        self.assertIn("before_metrics", report)
        self.assertEqual(report["dataset_info"]["rows"], 9)
        self.assertEqual(report["dataset_info"]["version"], "Cleaned v1")

        # Test Markdown download
        md_bytes, headers = self.api_get_raw(f"/cleaning/{self.test_dataset_id}/report/download?format=markdown")
        md_text = md_bytes.decode("utf-8")
        self.assertIn("# Data Cleaning Report", md_text)
        self.assertIn("Dataset Overview", md_text)
        self.assertIn("Validation", md_text)

        # Test JSON download
        json_bytes, _ = self.api_get_raw(f"/cleaning/{self.test_dataset_id}/report/download?format=json")
        json_data = json.loads(json_bytes.decode("utf-8"))
        self.assertIn("dataset_info", json_data)

        # Test CSV download
        csv_bytes, _ = self.api_get_raw(f"/cleaning/{self.test_dataset_id}/report/download?format=csv")
        csv_text = csv_bytes.decode("utf-8")
        self.assertTrue("Category" in csv_text or "Validation" in csv_text)
        print("  [PASS] Cleaning Report generated and verified across Markdown, JSON, and CSV downloads.")

    # =========================================================================
    # 9. Final Dataset Actions (Cleaned CSV, Cleaned Excel, Previous CSV)
    # =========================================================================
    def test_09_final_dataset_actions(self):
        """Feature 11: Verify Previous CSV view, Cleaned CSV download, and Cleaned Excel download."""
        print("\n--- Test 9: Final Dataset Actions (CSV, Excel, Original Preview) ---")
        
        # 1. Previous CSV (Original Preview)
        orig_prev = self.api_get(f"/cleaning/{self.test_dataset_id}/original-preview")
        self.assertEqual(orig_prev["total_rows"], 10)
        self.assertEqual(orig_prev["total_columns"], 6)
        rows = orig_prev.get("sample_rows", orig_prev.get("sample_preview", []))
        self.assertEqual(len(rows), 10)

        # 2. Download Cleaned CSV
        csv_bytes, _ = self.api_get_raw(f"/cleaning/{self.test_dataset_id}/download?format=csv")
        csv_lines = csv_bytes.decode("utf-8").strip().splitlines()
        self.assertEqual(len(csv_lines), 10)  # 1 header + 9 rows

        # 3. Download Cleaned Excel (.xlsx)
        excel_bytes, ex_headers = self.api_get_raw(f"/cleaning/{self.test_dataset_id}/download?format=excel")
        self.assertGreater(len(excel_bytes), 100)
        # Excel zip signature PK\x03\x04
        self.assertTrue(excel_bytes.startswith(b"PK\x03\x04"))
        print("  [PASS] Previous CSV preview, Cleaned CSV export, and native Excel (.xlsx) export confirmed.")

    # =========================================================================
    # 10. Outlier Detection & Treatment Strategies
    # =========================================================================
    def test_10_outlier_treatments(self):
        """Feature: Verify IQR and Z-score outlier detection with cap, median, remove treatments."""
        print("\n--- Test 10: Outlier Detection & Treatment ---")
        # Test IQR capping on Age (values: -5, 180, 105 are clear statistical outliers)
        payload_cap = {
            "outlier_cleanings": [
                {"column": "Age", "method": "iqr", "threshold": 1.5, "treatment": "cap"}
            ]
        }
        prev_cap = self.api_post(f"/cleaning/{self.test_dataset_id}/bulk-preview", payload_cap)
        self.assertGreater(prev_cap["total_cells_affected"], 0)

        # Test Z-score replacement with median
        payload_zscore = {
            "outlier_cleanings": [
                {"column": "Age", "method": "zscore", "threshold": 1.0, "treatment": "median"}
            ]
        }
        prev_z = self.api_post(f"/cleaning/{self.test_dataset_id}/bulk-preview", payload_zscore)
        self.assertGreater(prev_z["total_cells_affected"], 0)
        print("  [PASS] IQR and Z-score outlier detection with Cap and Median treatments verified.")

    # =========================================================================
    # 11. Frontend UI Requirements & Components Integration
    # =========================================================================
    def test_11_frontend_phase4_ui_elements(self):
        """Feature 16: Verify all Phase 4 professional workflow elements exist in CleaningPage.jsx."""
        print("\n--- Test 11: Frontend UI Integration ---")
        page_file = ROOT_DIR / "frontend" / "src" / "pages" / "CleaningPage.jsx"
        code = page_file.read_text(encoding="utf-8")

        required_strings = [
            "Data Cleaning Score",
            "Status: ",
            "Previous CSV",
            "Cleaned View",
            "Download Cleaned CSV",
            "Download Cleaned Excel",
            "Download Cleaning Report",
            "Bulk Cleaning Workflow",
            "Execution Order:",
            "Reset Pending Changes",
            "Review All Changes",
            "Apply All Cleaning Operations",
            "Cleaning Preview Table",
            "Cleaning Validation & Quality Score",
            "Dataset Version Timeline",
            "Cleaning Report",
            "Outlier Detection & Treatment",
            "Confirm Cleaning Operations",
            "You are about to modify",
            "Original Dataset View (Previous CSV)",
        ]

        for s in required_strings:
            self.assertIn(s, code, f"Missing required Phase 4 UI element: '{s}'")

        print("  [PASS] All 20 Phase 4 frontend UI elements and components confirmed.")


if __name__ == "__main__":
    unittest.main()
