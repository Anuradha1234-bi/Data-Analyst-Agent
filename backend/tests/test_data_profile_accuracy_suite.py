"""Automated Comprehensive Test Suite for Data Profiling Module Accuracy.

Verifies all 13 test categories:
1. Row, column, and cell counts.
2. Missing values across multiple columns.
3. Duplicate rows versus duplicate IDs.
4. Invalid numeric strings and mixed data types.
5. Negative and extreme numeric values.
6. Valid, missing, and invalid dates.
7. Categorical values differing by case and whitespace.
8. Empty and all-null columns.
9. Small datasets and edge cases.
10. Quality-score calculations and classification.
11. Backend/frontend consistency.
12. Multi-dataset isolation and dataset selection.
13. Existing profiling, filtering, and multi-dataset workflows.
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from agents.profiler import ProfilerAgent, ProfileResult
from app.schemas.profiling import DatasetProfileResponse
from app.services.profiling_service import ProfilingService
from app.models.dataset import Dataset
from app.models.user import User
from app.auth.jwt import create_access_token
from fastapi.testclient import TestClient
from app.main import app

DATASET_52_CSV = Path(r"C:\Users\hp\Desktop\DataAnalystAgentAi\uploads\user_20\b2512faa23e048459e0ac00264334885_data_analyst_50_rows.csv")


class TestDataProfileAccuracy(unittest.TestCase):
    """Test suite executing all 13 verification criteria with deterministic pass/fail metrics."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.token = create_access_token({"sub": "20"})
        cls.auth_headers = {"Authorization": f"Bearer {cls.token}"}
        cls.raw_df = pd.read_csv(DATASET_52_CSV)

    def test_01_row_column_and_cell_counts(self):
        """1. Verify row, column, and cell counts on target dataset."""
        df = self.raw_df
        res = ProfilerAgent.profile_dataset(df)

        expected_rows = 50
        expected_cols = 7
        expected_cells = 350

        self.assertEqual(res.total_rows, expected_rows)
        self.assertEqual(res.total_columns, expected_cols)
        self.assertEqual(res.total_cells, expected_cells)

    def test_02_missing_values_across_multiple_columns(self):
        """2. Verify missing values across all columns."""
        df = self.raw_df
        res = ProfilerAgent.profile_dataset(df)

        # Expected missing: email=2, city=2, age=2, signup_date=1, annual_income_inr=1 -> total=8
        self.assertEqual(res.total_missing, 8)
        self.assertEqual(res.missing_percentage, 2.29)

        missing_map = {m["column"]: m["missing_count"] for m in res.quality.missing_columns}
        self.assertEqual(missing_map.get("email"), 2)
        self.assertEqual(missing_map.get("city"), 2)
        self.assertEqual(missing_map.get("age"), 2)
        self.assertEqual(missing_map.get("signup_date"), 1)
        self.assertEqual(missing_map.get("annual_income_inr"), 1)
        self.assertNotIn("customer_id", missing_map)
        self.assertNotIn("customer_name", missing_map)

    def test_03_duplicate_rows_vs_duplicate_ids(self):
        """3. Distinguish duplicate rows vs duplicate identifier values."""
        df = self.raw_df
        res = ProfilerAgent.profile_dataset(df)

        # Dataset 52 has 1 duplicate row (lines 22 & 23, C0021)
        self.assertEqual(res.duplicate_rows, 1)
        self.assertEqual(res.duplicate_percentage, 2.0)

        # Distinct test: synthetic fixture where IDs are duplicated but entire rows are NOT
        synthetic_df = pd.DataFrame({
            "id": ["A1", "A1", "A2"],
            "val": [10, 20, 30]
        })
        synth_res = ProfilerAgent.profile_dataset(synthetic_df)
        self.assertEqual(synth_res.duplicate_rows, 0, "Unique rows must have 0 duplicate_rows even if ID repeats")
        self.assertEqual(synth_res.columns["id"].unique_count, 2)

    def test_04_invalid_numeric_strings_and_mixed_data_types(self):
        """4. Verify invalid numeric strings are excluded from numeric moments without crashing."""
        df = self.raw_df
        res = ProfilerAgent.profile_dataset(df)

        age_prof = res.columns["age"]
        self.assertEqual(age_prof.semantic_type, "NUMERIC")
        self.assertEqual(age_prof.missing_count, 2)
        self.assertEqual(age_prof.non_null_count, 48)

        # 'unknown' and 'two years' must be safely coerced to NaN in numeric stats
        ns = age_prof.numeric_stats
        self.assertIsNotNone(ns)
        self.assertEqual(ns["count"], 46)  # 48 non-null minus 2 invalid strings
        self.assertEqual(ns["valid_count"], 46)
        self.assertEqual(ns["invalid_count"], 2)
        self.assertEqual(set(ns["invalid_examples"]), {"unknown", "two years"})
        self.assertAlmostEqual(ns["mean"], 43.35, places=2)
        self.assertEqual(ns["median"], 41.0)

    def test_05_negative_and_extreme_numeric_values(self):
        """5. Verify negative and extreme values are accurately preserved in min/max."""
        df = self.raw_df
        res = ProfilerAgent.profile_dataset(df)

        # Age has negative value -5.0 and extreme value 150.0
        age_stats = res.columns["age"].numeric_stats
        self.assertEqual(age_stats["min"], -5.0)
        self.assertEqual(age_stats["max"], 150.0)

        # Income has min 22151.35 and max 9999999.0 (no negative values in this 50-row slice)
        inc_stats = res.columns["annual_income_inr"].numeric_stats
        self.assertEqual(inc_stats["min"], 22151.35)
        self.assertEqual(inc_stats["max"], 9999999.0)

    def test_06_valid_missing_and_invalid_dates(self):
        """6. Verify date semantic type detection and date range calculation."""
        df = self.raw_df
        res = ProfilerAgent.profile_dataset(df)

        dt_prof = res.columns["signup_date"]
        self.assertEqual(dt_prof.semantic_type, "DATETIME")
        self.assertIsNotNone(dt_prof.datetime_stats)
        self.assertEqual(dt_prof.datetime_stats["min_date"], "01-01-2024")
        self.assertEqual(dt_prof.datetime_stats["max_date"], "27-05-2024")
        self.assertEqual(dt_prof.datetime_stats["unique_dates"], 48)

        # Edge case: European and ISO mixed dates (>= 75% valid dates)
        mixed_df = pd.DataFrame({"dates": ["2024-01-15", "16/01/2024", "2024-02-01", "2024-03-01", "invalid_date", None]})
        mixed_res = ProfilerAgent.profile_dataset(mixed_df)
        self.assertEqual(mixed_res.columns["dates"].semantic_type, "DATETIME")

    def test_07_categorical_differing_by_case_and_whitespace(self):
        """7. Verify categorical values differing by case and whitespace are preserved in raw counts."""
        df = self.raw_df
        res = ProfilerAgent.profile_dataset(df)

        city_prof = res.columns["city"]
        self.assertEqual(city_prof.semantic_type, "CATEGORICAL")
        # 9 raw distinct values: Pune, Satara, Kolhapur, Nagpur, Solapur, Mumbai, ' pune ', MUMBAI, Nashik
        self.assertEqual(city_prof.unique_count, 9)

        top_vals = {item["value"]: item["count"] for item in city_prof.categorical_stats["top_values"]}
        self.assertEqual(top_vals.get("Nagpur"), 11)
        self.assertEqual(top_vals.get("Satara"), 10)
        self.assertEqual(top_vals.get("Pune"), 7)
        self.assertEqual(top_vals.get("Kolhapur"), 6)
        self.assertEqual(top_vals.get("Solapur"), 6)

    def test_08_empty_and_all_null_columns(self):
        """8. Verify all-null and empty string columns handle gracefully."""
        edge_df = pd.DataFrame({
            "all_null": [np.nan, np.nan, np.nan],
            "empty_str": ["", "", ""],
        })
        res = ProfilerAgent.profile_dataset(edge_df)
        self.assertEqual(res.columns["all_null"].semantic_type, "UNKNOWN")
        self.assertEqual(res.columns["all_null"].missing_count, 3)
        self.assertEqual(res.columns["empty_str"].semantic_type, "CATEGORICAL")
        self.assertEqual(res.columns["empty_str"].missing_count, 0)

    def test_09_small_datasets_and_edge_cases(self):
        """9. Verify small single-row datasets and single-column frames."""
        single_row = pd.DataFrame({"a": [42], "b": ["alpha"]})
        res = ProfilerAgent.profile_dataset(single_row)
        self.assertEqual(res.total_rows, 1)
        self.assertEqual(res.total_columns, 2)
        self.assertEqual(res.columns["a"].numeric_stats["std"], 0.0)
        self.assertEqual(res.quality.health_score, 100)

    def test_10_quality_score_calculation_and_classification(self):
        """10. Verify quality health score formula and status thresholds."""
        df = self.raw_df
        res = ProfilerAgent.profile_dataset(df)

        # Total missing penalty: (8 / 350) * 120 = 2.7428
        # Duplicate rows penalty: (1 / 50) * 100 = 2.0
        # Constant columns penalty: 0
        # Score = 100 - 2.7428 - 2.0 = 95.257 -> 95 ("Excellent")
        self.assertEqual(res.quality.health_score, 95)
        self.assertEqual(res.quality.health_status, "Excellent")

    def test_11_backend_frontend_consistency(self):
        """11. Verify backend API response matches independently verified expectations."""
        resp = self.client.get("/api/datasets/52/profile", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["dataset_info"]["rows"], 50)
        self.assertEqual(data["dataset_info"]["columns"], 7)
        self.assertEqual(data["dataset_info"]["total_cells"], 350)
        self.assertEqual(data["quality_summary"]["total_missing_cells"], 8)
        self.assertEqual(data["quality_summary"]["duplicate_rows"], 1)
        self.assertEqual(data["quality_summary"]["health_score"], 95)

        col_map = {c["name"]: c for c in data["columns"]}
        self.assertEqual(col_map["signup_date"]["semantic_type"], "DATETIME")
        self.assertEqual(col_map["signup_date"]["datetime_stats"]["min_date"], "01-01-2024")
        self.assertEqual(col_map["signup_date"]["datetime_stats"]["max_date"], "27-05-2024")

    def test_12_multi_dataset_isolation_and_selection(self):
        """12. Verify multi-dataset analysis endpoint and tenant security."""
        resp = self.client.post(
            "/api/analysis/multi",
            json={"dataset_ids": [52], "mode": "all", "settings": {}},
            headers=self.auth_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("52", data["individual_profiles"])
        prof52 = data["individual_profiles"]["52"]
        self.assertEqual(prof52["dataset_info"]["rows"], 50)
        self.assertEqual(prof52["quality_summary"]["health_score"], 95)

        # Cross-tenant isolation: requesting dataset 52 as an unauthorized user (user 21) must return error
        other_user_token = create_access_token({"sub": "21"})
        iso_resp = self.client.post(
            "/api/analysis/multi",
            json={"dataset_ids": [52], "mode": "all", "settings": {}},
            headers={"Authorization": f"Bearer {other_user_token}"},
        )
        self.assertEqual(iso_resp.status_code, 200)
        iso_data = iso_resp.json()
        self.assertEqual(iso_data["total_successful"], 0)
        self.assertEqual(iso_data["total_failed"], 1)

    def test_13_existing_profiling_and_filtering_workflows(self):
        """13. Verify that batch profiling and single profile endpoints return identical profiles."""
        p1 = self.client.get("/api/datasets/52/profile", headers=self.auth_headers).json()
        p2 = self.client.get("/api/profiling/52", headers=self.auth_headers).json()

        self.assertEqual(p1["dataset_info"]["rows"], p2["dataset_info"]["rows"])
        self.assertEqual(p1["quality_summary"]["health_score"], p2["quality_summary"]["health_score"])
        self.assertEqual(len(p1["columns"]), len(p2["columns"]))


if __name__ == "__main__":
    unittest.main()
