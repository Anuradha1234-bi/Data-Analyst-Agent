"""Live end-to-end integration verification against running server (http://127.0.0.1:8002).
Verifies:
1. User login and JWT authentication.
2. Dataset upload (sample_test_data.csv).
3. Data profiling on uploaded dataset.
4. Data quality assessment (version="original").
5. Cleaning operation execution with Apply Changes.
6. Data quality assessment on cleaned version (version="cleaned").
7. Analyst intelligence query on dataset.
8. Support readiness and metadata endpoint.
"""

import os
import requests
import unittest
from pathlib import Path

BASE_URL = "http://127.0.0.1:8002"
TEST_EMAIL = "tester@analytics.io"
TEST_PASSWORD = "StrongPassword123!"


class TestLiveRunningServerE2E(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 1. Login to get token
        res = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10,
        )
        if res.status_code != 200:
            raise RuntimeError(f"Login failed: {res.status_code} {res.text}")
        data = res.json()
        cls.token = data.get("access_token")
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_01_health_and_support_endpoints(self):
        """Verify health check and support status on running server."""
        health = requests.get(f"{BASE_URL}/api/health", timeout=5)
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json().get("status"), "ok")

        support = requests.get(f"{BASE_URL}/api/support/status", timeout=5)
        self.assertEqual(support.status_code, 200)
        sup_data = support.json()
        self.assertEqual(sup_data.get("support_email"), "dataanalystagent@gmail.com")
        self.assertEqual(sup_data.get("helpline"), "+91 9021964018")

    def test_02_upload_and_profile_dataset(self):
        """Upload test dataset and verify profiling on running server."""
        csv_file = Path("sample_test_data.csv")
        self.assertTrue(csv_file.exists())

        with open(csv_file, "rb") as f:
            upload_res = requests.post(
                f"{BASE_URL}/api/datasets/upload",
                headers=self.headers,
                files=[("files", ("sample_test_data.csv", f, "text/csv"))],
                timeout=15,
            )
        self.assertEqual(upload_res.status_code, 200)
        upload_data = upload_res.json()
        self.assertGreater(len(upload_data.get("uploaded", [])), 0)
        dataset_id = upload_data["uploaded"][0]["id"]
        self.assertIsNotNone(dataset_id)
        TestLiveRunningServerE2E.dataset_id = dataset_id

        # Profile the dataset
        profile_res = requests.get(
            f"{BASE_URL}/api/profiling/{dataset_id}",
            headers=self.headers,
            timeout=15,
        )
        self.assertEqual(profile_res.status_code, 200)
        pdata = profile_res.json()
        self.assertIn("columns", pdata)
        self.assertEqual(pdata["dataset_info"]["rows"], 8)
        self.assertEqual(pdata["dataset_info"]["columns"], 6)

    def test_03_quality_before_cleaning(self):
        """Verify original data quality evaluation on running server."""
        dataset_id = getattr(self.__class__, "dataset_id", None)
        self.assertIsNotNone(dataset_id)

        res = requests.get(
            f"{BASE_URL}/api/quality/{dataset_id}?version=original",
            headers=self.headers,
            timeout=15,
        )
        self.assertEqual(res.status_code, 200)
        qdata = res.json()
        self.assertEqual(qdata.get("evaluated_version"), "original")
        # Notice sample dataset has 1 duplicate row and 1 missing cell
        self.assertGreaterEqual(qdata["summary"]["duplicate_rows"], 1)
        self.assertGreaterEqual(qdata["summary"]["missing_cells"], 1)

    def test_04_cleaning_apply_changes(self):
        """Apply cleaning changes (deduplicate and fill missing salary) on live server."""
        dataset_id = getattr(self.__class__, "dataset_id", None)
        self.assertIsNotNone(dataset_id)

        clean_payload = {
            "remove_duplicates": True,
            "missing_imputations": [
                {"column": "Salary", "strategy": "mean"}
            ],
            "category_normalizations": [
                {"column": "Department", "mapping": {"engineering": "Engineering"}}
            ]
        }

        clean_res = requests.post(
            f"{BASE_URL}/api/cleaning/{dataset_id}/apply",
            headers=self.headers,
            json=clean_payload,
            timeout=20,
        )
        self.assertEqual(clean_res.status_code, 200)
        cdata = clean_res.json()
        self.assertTrue(cdata.get("success"))
        self.assertEqual(cdata.get("rows_removed"), 1)  # 1 duplicate dropped
        self.assertIn("Cleaned", cdata.get("version", ""))

    def test_05_quality_after_cleaning(self):
        """Verify post-cleaning quality metrics on live server reflect cleaned state."""
        dataset_id = getattr(self.__class__, "dataset_id", None)
        self.assertIsNotNone(dataset_id)

        res = requests.get(
            f"{BASE_URL}/api/quality/{dataset_id}?version=cleaned",
            headers=self.headers,
            timeout=15,
        )
        self.assertEqual(res.status_code, 200)
        qdata = res.json()
        self.assertEqual(qdata.get("evaluated_version"), "cleaned")
        self.assertTrue(qdata.get("has_cleaned"))
        # Cleaned dataset should now have 0 duplicate rows and 0 missing cells in salary
        self.assertEqual(qdata["summary"]["duplicate_rows"], 0)
        self.assertEqual(qdata["summary"]["missing_cells"], 0)

    def test_06_analyst_query_on_dataset(self):
        """Ask analyst a query on the dataset and verify answer from live server."""
        dataset_id = getattr(self.__class__, "dataset_id", None)
        self.assertIsNotNone(dataset_id)

        query_res = requests.post(
            f"{BASE_URL}/api/analysis/query",
            headers=self.headers,
            json={
                "dataset_id": dataset_id,
                "query": "What is the total number of employees?",
            },
            timeout=30,
        )
        self.assertEqual(query_res.status_code, 200)
        ans_data = query_res.json()
        self.assertIn("answer", ans_data)
        self.assertTrue(len(ans_data["answer"]) > 0)
        self.assertEqual(ans_data.get("status"), "success")


if __name__ == "__main__":
    unittest.main()
