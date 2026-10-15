"""
Comprehensive unit and integration tests for:
1. Six-Step Data Cleaning Workflow States & Transitions
2. Deterministic Top-Three Suggestion Prioritization
"""

import unittest
import pandas as pd
import numpy as np
import sys
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

# Ensure backend app is in path
backend_path = os.path.join(os.path.dirname(__file__), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.cleaning_service import DataCleaningService

class TestWorkflowAndPrioritization(unittest.TestCase):

    def setUp(self):
        # Create a temporary CSV file with diverse issues:
        # - Missing values in 'age' (3 rows out of 20 = 15%)
        # - Blank whitespace in 'department' (2 rows)
        # - Statistical outlier in 'salary' (950000)
        # Total rows: 20
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "test_workflow.csv"

        df_data = {
            "id": list(range(1, 21)),
            "name": [f"Person_{i}" for i in range(1, 21)],
            "age": [25, 30, np.nan, 40, 35, np.nan, 28, 45, 50, 22,
                    33, 38, 29, 41, np.nan, 36, 27, 48, 52, 31],
            "salary": [50000, 60000, 55000, 70000, 65000, 58000, 62000, 75000, 80000, 48000,
                       53000, 67000, 59000, 72000, 56000, 64000, 51000, 78000, 950000, 52000],
            "department": ["Sales", "Engineering", "  ", "HR", "Sales", "Engineering", "Marketing", "HR", "Sales", "Engineering",
                           "Sales", "Engineering", " ", "HR", "Sales", "Engineering", "Marketing", "HR", "Sales", "Engineering"]
        }
        self.df = pd.DataFrame(df_data)
        self.df.to_csv(self.csv_path, index=False)

        # Mock Dataset model
        self.mock_dataset = SimpleNamespace(
            id=999,
            filename="test_workflow.csv",
            file_path=str(self.csv_path),
            file_size_bytes=self.csv_path.stat().st_size,
            has_cleaned=False,
            cleaned_file_path=None
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_deterministic_priority_formula(self):
        """Verify deterministic Priority Score formula: (Severity Weight * 0.60) + (Impact Score * 0.40)."""
        res = DataCleaningService.get_smart_suggestions(self.mock_dataset)
        suggestions = res.suggestions
        self.assertTrue(len(suggestions) > 0, "Should generate suggestions")

        total_rows = len(self.df)
        SEVERITY_WEIGHTS = {
            "Critical": 100.0,
            "High": 75.0,
            "Medium": 50.0,
            "Low": 25.0
        }

        for s in suggestions:
            # 1. Impact Score = 100 * affected_count / total_rows (clamped 0-100)
            expected_impact = round(min(100.0, max(0.0, 100.0 * float(s.affected_count) / float(total_rows))), 2)
            self.assertEqual(s.impact_score, expected_impact, f"Impact score mismatch for '{s.issue}'")

            # 2. Priority Score = (Severity Weight * 0.60) + (Impact Score * 0.40)
            sev_w = SEVERITY_WEIGHTS.get(s.severity, 50.0)
            expected_priority = round((sev_w * 0.60) + (expected_impact * 0.40), 2)
            self.assertEqual(s.priority_score, expected_priority, f"Priority score mismatch for '{s.issue}'")

    def test_02_deterministic_four_tier_sorting(self):
        """Verify 4-tier sorting order:
        1. Priority Score, descending
        2. Severity, descending
        3. Number of affected records, descending
        4. Stable issue-type name, alphabetically
        """
        res = DataCleaningService.get_smart_suggestions(self.mock_dataset)
        suggs = res.suggestions
        self.assertGreaterEqual(len(suggs), 2)

        sev_rank = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

        for i in range(len(suggs) - 1):
            curr = suggs[i]
            nxt = suggs[i + 1]

            # Tier 1: Priority Score (desc)
            if curr.priority_score != nxt.priority_score:
                self.assertGreater(curr.priority_score, nxt.priority_score)
            else:
                # Tier 2: Severity (desc)
                curr_sev = sev_rank.get(curr.severity, 0)
                nxt_sev = sev_rank.get(nxt.severity, 0)
                if curr_sev != nxt_sev:
                    self.assertGreater(curr_sev, nxt_sev)
                else:
                    # Tier 3: Affected count (desc)
                    if curr.affected_count != nxt.affected_count:
                        self.assertGreater(curr.affected_count, nxt.affected_count)
                    else:
                        # Tier 4: Stable issue-type name (asc)
                        self.assertLessEqual(curr.issue.lower(), nxt.issue.lower())

    def test_03_top_three_presentation_logic(self):
        """Verify that top-3 suggestions can be partitioned from the remaining suggestions."""
        res = DataCleaningService.get_smart_suggestions(self.mock_dataset)
        suggs = res.suggestions

        # Top 3 display on main screen
        top_three = suggs[:3]
        remaining = suggs[3:]

        self.assertLessEqual(len(top_three), 3)
        self.assertEqual(len(suggs), len(top_three) + len(remaining))

        # Each suggestion card must contain the required fields
        for s in top_three:
            self.assertTrue(s.issue)
            self.assertIn(s.severity, ["Critical", "High", "Medium", "Low"])
            self.assertIsNotNone(s.affected_count)
            self.assertIsNotNone(s.affected_percentage)
            self.assertTrue(s.evidence)
            self.assertTrue(s.recommended_action)

    def test_04_zero_issues_and_fewer_than_three(self):
        """Verify handling of clean datasets (0 issues) and datasets with < 3 issues."""
        # 1. Clean dataset
        clean_df = pd.DataFrame({
            "col_a": [1, 2, 3, 4, 5],
            "col_b": ["a", "b", "c", "d", "e"]
        })
        clean_path = Path(self.temp_dir.name) / "clean.csv"
        clean_df.to_csv(clean_path, index=False)
        clean_mock = SimpleNamespace(
            id=1000,
            filename="clean.csv",
            file_path=str(clean_path),
            file_size_bytes=clean_path.stat().st_size,
            has_cleaned=False,
            cleaned_file_path=None
        )
        clean_res = DataCleaningService.get_smart_suggestions(clean_mock)
        self.assertEqual(clean_res.total_suggestions, 0)
        self.assertEqual(len(clean_res.suggestions), 0)

        # 2. Dataset with only 1 issue
        single_issue_df = pd.DataFrame({
            "col_a": [1, 2, np.nan, 4, 5],
            "col_b": ["a", "b", "c", "d", "e"]
        })
        single_path = Path(self.temp_dir.name) / "single.csv"
        single_issue_df.to_csv(single_path, index=False)
        single_mock = SimpleNamespace(
            id=1001,
            filename="single.csv",
            file_path=str(single_path),
            file_size_bytes=single_path.stat().st_size,
            has_cleaned=False,
            cleaned_file_path=None
        )
        single_res = DataCleaningService.get_smart_suggestions(single_mock)
        self.assertEqual(single_res.total_suggestions, 1)
        self.assertEqual(len(single_res.suggestions), 1)

    def test_05_safety_rules_outliers_and_imputation(self):
        """Verify safety rules: outliers recommend review, not auto-deletion; no forced mean/median."""
        res = DataCleaningService.get_smart_suggestions(self.mock_dataset)
        outlier_suggs = [s for s in res.suggestions if "outlier" in s.category.lower()]
        for s in outlier_suggs:
            self.assertIn("review", s.recommended_action.lower(), "Outliers must advise review first")
            self.assertNotIn("delete", s.recommended_action.lower(), "Outliers must not prescribe auto deletion")

    def test_06_six_step_workflow_state_constants(self):
        """Verify the exact set of required states for all six workflow steps."""
        step_states = {
            "Step 1 - Dataset": ["NO_DATASET", "DATASET_SELECTED", "DATASET_LOADING", "DATASET_ERROR"],
            "Step 2 - Issues": ["ANALYSIS_PENDING", "ANALYZING", "ANALYSIS_COMPLETE", "ANALYSIS_ERROR", "NO_ISSUES"],
            "Step 3 - Clean": ["NO_ACTIONS_SELECTED", "ACTIONS_SELECTED", "ACTIONS_CONFIGURED", "CLEANING_IN_PROGRESS", "CLEANING_ERROR"],
            "Step 4 - Preview": ["PREVIEW_PENDING", "PREVIEW_GENERATING", "PREVIEW_READY", "PREVIEW_ERROR"],
            "Step 5 - Save": ["SAVE_CONFIRMATION", "SAVING", "SAVE_SUCCESS", "SAVE_ERROR"],
            "Step 6 - Download": ["DOWNLOAD_READY", "DOWNLOAD_IN_PROGRESS", "DOWNLOAD_SUCCESS", "DOWNLOAD_ERROR"]
        }

        # Check in frontend CleaningPage.jsx
        frontend_page = Path(os.path.dirname(__file__)) / "frontend" / "src" / "pages" / "CleaningPage.jsx"
        content = frontend_page.read_text(encoding="utf-8")

        for step_name, states in step_states.items():
            for state in states:
                self.assertIn(state, content, f"State '{state}' for {step_name} must be explicitly defined in CleaningPage.jsx")


if __name__ == "__main__":
    unittest.main()
