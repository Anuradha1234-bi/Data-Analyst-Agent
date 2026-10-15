"""Complete Unit & Integration Test Suite for DATA CLEANING - PHASES 4 & 5:
VALIDATION + DETERMINISTIC CLEANING SCORE + CLEANING REPORT + SMART SUGGESTIONS + CONSISTENCY CHECKS.
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
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.auth.jwt import create_access_token

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8002/api")


def create_multipart_form(fields, files):
    boundary = "----WebKitFormBoundaryPhase5FinalTest9XZ"
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


class TestDataCleaningPhases4And5(unittest.TestCase):
    """Verifies all Phase 4 & Phase 5 specifications end-to-end."""

    @classmethod
    def setUpClass(cls):
        cls.token = create_access_token(data={"sub": "11"})
        cls.test_dataset_id = cls.upload_messy_dataset()

    @classmethod
    def upload_messy_dataset(cls):
        # Messy dataset covering all required issues:
        # - Duplicates (C101 is duplicated)
        # - Whitespace blanks ("   ", "\t", "")
        # - Skewed numeric missing values in 'bonus'
        # - Categorical missing values in 'notes'
        # - Mixed date formats and invalid date ("2025-13-50", "not-a-date")
        # - Numeric with currency and commas ("₹1,200", "1,500")
        # - Date inconsistency: start_date > end_date in row 1
        # - Numeric inconsistency: quantity = 0 but total_amount > 0 in row 1
        # - Duplicate ID: C101
        # - Category inconsistency: "Mumbai", "mumbai", " Mumbai "
        csv_content = (
            "customer_id,customer_name,city,salary,quantity,total_amount,start_date,end_date,signup_date,notes,bonus\n"
            'C101,Alice,"Mumbai","₹1,200",0,350.0,2025-05-10,2025-04-10,2025-01-15,"Good",\n'
            'C102,Bob,"mumbai","1,500",5,500.0,2025-01-01,2025-01-15,01/02/2025,"   ",100.0\n'
            'C103,Charlie," Mumbai ","2,000",2,200.0,2025-03-15,2025-03-20,2025-13-50,"\t",150.0\n'
            'C101,Alice,"Mumbai","₹1,200",0,350.0,2025-05-10,2025-04-10,2025-01-15,"Good",\n'
            ',Eve,"Delhi","2,500",10,1000.0,2025-02-01,2025-02-28,Feb 1 2025,"",200.0\n'
            'C106,Frank,"Bangalore","150,000",1,150000.0,2025-04-01,2025-04-30,not-a-date,"Active",50000.0\n'
            'C107,Grace,"mumbai","2,200",3,300.0,2025-01-10,2025-01-20,2025-03-01,"Verified",\n'
            'C108,Heidi,"Chennai","1,900",0,0.0,2025-07-01,2025-06-01,2025-03-15,"VIP",120.0\n'
            'C109,Ivan,"Kolkata","2,100",4,400.0,2025-08-01,2025-08-15,32/15/2025,,130.0\n'
            'C110,Judy,"Pune","2,300",6,600.0,2025-09-01,2025-09-30,2025-04-01,"New",140.0\n'
        ).encode("utf-8")

        body, content_type = create_multipart_form(
            {},
            [("files", "phase4_phase5_messy_test.csv", csv_content)]
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
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            dataset_id = data.get("uploaded", data.get("datasets", []))[0]["id"]
            return dataset_id

    def _api_get(self, path):
        req = urllib.request.Request(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {self.token}"},
            method="GET",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _api_post(self, path, payload):
        req = urllib.request.Request(
            f"{API_BASE}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # =========================================================================
    # PART A & B: Validation & Cleaning Score
    # =========================================================================

    def test_01_cleaning_score_weights_and_status(self):
        """Verify deterministic cleaning score with 6 exact weights summing to 100."""
        val = self._api_get(f"/cleaning/{self.test_dataset_id}/validation")
        self.assertIn("cleaning_score", val)
        self.assertIn("score_status", val)
        self.assertIn("checks", val)

        # Check weights sum to 100
        score_checks = [c for c in val["checks"] if c["weight"] > 0]
        total_weight = sum(c["weight"] for c in score_checks)
        self.assertEqual(total_weight, 100, "Component weights must sum exactly to 100")

        # Check expected weights
        expected_weights = {
            "Missing Values": 25,
            "Duplicate Rows": 20,
            "Blank Values": 10,
            "Invalid Values": 15,
            "Invalid Dates": 10,
            "Remaining Outliers": 20,
        }
        for chk in score_checks:
            for exp_name, exp_w in expected_weights.items():
                if exp_name.lower() in chk["check_name"].lower():
                    self.assertEqual(chk["weight"], exp_w, f"Weight for {chk['check_name']} should be {exp_w}")

        # Check score status boundaries
        score = val["cleaning_score"]
        status = val["score_status"]
        if score >= 90:
            self.assertEqual(status, "CLEAN")
        elif score >= 75:
            self.assertEqual(status, "GOOD")
        elif score >= 50:
            self.assertEqual(status, "NEEDS REVIEW")
        else:
            self.assertEqual(status, "CRITICAL")

    def test_02_validation_checks_coverage(self):
        """Verify all 8 hygiene metrics are reported."""
        val = self._api_get(f"/cleaning/{self.test_dataset_id}/validation")
        check_names = [c["check_name"].lower() for c in val["checks"]]
        self.assertTrue(any("missing" in n for n in check_names))
        self.assertTrue(any("duplicate" in n for n in check_names))
        self.assertTrue(any("blank" in n for n in check_names))
        self.assertTrue(any("outlier" in n for n in check_names))
        self.assertTrue(any("date" in n for n in check_names))
        self.assertTrue(any("value" in n for n in check_names))
        self.assertTrue(any("type" in n for n in check_names))
        self.assertTrue(any("name" in n for n in check_names))

    # =========================================================================
    # PART E: Smart Cleaning Suggestions
    # =========================================================================

    def test_03_smart_cleaning_suggestions(self):
        """Verify intelligent, data-driven cleaning suggestions grouped by priority."""
        res = self._api_get(f"/cleaning/{self.test_dataset_id}/suggestions")
        self.assertIn("suggestions", res)
        self.assertGreater(res["total_suggestions"], 0)
        self.assertEqual(
            res["total_suggestions"],
            res["high_priority_count"] + res["medium_priority_count"] + res["low_priority_count"]
        )

        categories = [s["category"] for s in res["suggestions"]]
        actions = [s["action_type"] for s in res["suggestions"]]

        # Should detect numeric formatting in 'salary'
        self.assertIn("numeric", categories)
        self.assertIn("numeric_cleaning", actions)

        # Should detect category inconsistency in 'city'
        self.assertIn("category", categories)
        self.assertIn("category_normalization", actions)

        # Should detect mixed / unparseable dates in 'signup_date'
        self.assertIn("date", categories)

        # Verify evidence field is present and non-empty
        for s in res["suggestions"]:
            self.assertTrue(len(s["evidence"]) > 0, "Suggestion must include concrete data evidence")
            self.assertIn(s["priority"], ["high", "medium", "low"])

    # =========================================================================
    # PART F & H: Data Consistency Checks
    # =========================================================================

    def test_04_data_consistency_checks(self):
        """Verify chronological, relational, and ID consistency checks."""
        res = self._api_get(f"/cleaning/{self.test_dataset_id}/consistency")
        self.assertIn("checks", res)
        self.assertGreater(res["total_violations"], 0)

        check_names = [c["check_name"].lower() for c in res["checks"]]

        # Date consistency: start_date > end_date
        self.assertTrue(any("start_date > end_date" in n for n in check_names))

        # Duplicate ID in 'customer_id'
        self.assertTrue(any("duplicate id" in n for n in check_names))

        # Missing identifier in 'customer_id'
        self.assertTrue(any("missing identifier" in n for n in check_names))

        # Numeric relationship check: quantity = 0 but total_amount > 0
        self.assertTrue(any("quantity = 0 but total_amount > 0" in n for n in check_names))

        # Check sample violations exist
        date_chk = next(c for c in res["checks"] if "start_date > end_date" in c["check_name"].lower())
        self.assertGreater(date_chk["violations_count"], 0)
        self.assertGreater(len(date_chk["sample_violations"]), 0)

    def test_05_custom_cross_column_consistency_rule(self):
        """Verify user-defined cross-column rule evaluation."""
        payload = {
            "rule_name": "High Value Transactions",
            "column_a": "total_amount",
            "operator": ">",
            "constant_value": "1000",
        }
        res = self._api_post(f"/cleaning/{self.test_dataset_id}/consistency/custom-rule", payload)
        self.assertEqual(res["rule_name"], "High Value Transactions")
        self.assertEqual(res["violations_count"], 1)  # row with 150000.0
        self.assertGreater(len(res["sample_violations"]), 0)

    # =========================================================================
    # PART J & K: Cleaning Pipeline Execution, Score Improvement, Versioning
    # =========================================================================

    def test_06_apply_cleaning_and_score_improvement(self):
        """Verify applying cleaning resolves issues and improves the Cleaning Score."""
        init_val = self._api_get(f"/cleaning/{self.test_dataset_id}/validation")
        init_score = init_val["cleaning_score"]

        # Apply operations:
        # 1. Remove duplicate rows
        # 2. Impute missing bonus with median
        # 3. Trim notes whitespace
        ops = {
            "remove_duplicates": True,
            "convert_blanks_to_na": True,
            "imputations": [
                {"column": "bonus", "strategy": "median"},
                {"column": "notes", "strategy": "constant", "fill_value": "Standard"}
            ]
        }
        apply_res = self._api_post(f"/cleaning/{self.test_dataset_id}/bulk-apply", ops)
        self.assertTrue(apply_res["success"])

        # Check new validation and score
        new_val = self._api_get(f"/cleaning/{self.test_dataset_id}/validation")
        new_score = new_val["cleaning_score"]
        self.assertGreaterEqual(new_score, init_score, "Cleaning score must increase or stay equal after resolving issues")

        # Verify duplicate rows resolved to 0
        dup_chk = next(c for c in new_val["checks"] if "duplicate" in c["check_name"].lower())
        self.assertEqual(dup_chk["remaining_issues"], 0)
        self.assertEqual(dup_chk["component_score"], 20.0)

    def test_07_version_timeline_and_comparison(self):
        """Verify version timeline tracks versions with scores, and version comparison works."""
        timeline = self._api_get(f"/cleaning/{self.test_dataset_id}/versions")
        self.assertGreaterEqual(len(timeline), 2, "Timeline must contain Original and at least 1 Cleaned version")

        # Original version has score and status
        orig_ver = timeline[0]
        v_tag = orig_ver.get("version") or orig_ver.get("version_tag")
        self.assertEqual(v_tag, "Original")
        self.assertIsNotNone(orig_ver.get("quality_score"))

        # Compare versions
        v1 = timeline[0].get("version") or timeline[0].get("version_tag")
        v2 = timeline[1].get("version") or timeline[1].get("version_tag")
        q_v1 = urllib.parse.quote(str(v1))
        q_v2 = urllib.parse.quote(str(v2))
        compare_res = self._api_get(f"/cleaning/{self.test_dataset_id}/versions/compare?v1={q_v1}&v2={q_v2}")
        self.assertEqual(compare_res["v1_tag"], v1)
        self.assertEqual(compare_res["v2_tag"], v2)
        self.assertIn("deltas", compare_res)
        self.assertIn("rows_delta", compare_res["deltas"])

    # =========================================================================
    # PART D: Cleaning Report Generation & Export
    # =========================================================================

    def test_08_cleaning_report_exports(self):
        """Verify cleaning report JSON and export download formats (CSV, Markdown)."""
        report = self._api_get(f"/cleaning/{self.test_dataset_id}/report")
        self.assertIn("dataset_info", report)
        self.assertIn("quality_score", report)
        self.assertIn("validation_results", report)
        self.assertEqual(report["dataset_info"]["name"], "phase4_phase5_messy_test.csv")

        # Download Markdown report
        req_md = urllib.request.Request(
            f"{API_BASE}/cleaning/{self.test_dataset_id}/report/download?format=markdown",
            headers={"Authorization": f"Bearer {self.token}"},
            method="GET",
        )
        with urllib.request.urlopen(req_md) as resp:
            md_content = resp.read().decode("utf-8")
            self.assertIn("# Data Cleaning Report", md_content)
            self.assertIn("Cleaning Score", md_content)

        # Download CSV report
        req_csv = urllib.request.Request(
            f"{API_BASE}/cleaning/{self.test_dataset_id}/report/download?format=csv",
            headers={"Authorization": f"Bearer {self.token}"},
            method="GET",
        )
        with urllib.request.urlopen(req_csv) as resp:
            csv_content = resp.read().decode("utf-8")
            self.assertIn("Category", csv_content)
            self.assertIn("Validation", csv_content)


if __name__ == "__main__":
    unittest.main()
