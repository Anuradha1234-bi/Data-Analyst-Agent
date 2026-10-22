"""Regression test suite for Data Cleaning and Data Quality defect fixes.
Verifies:
1. Schema field normalization for CategoryNormalizationConfig, DateCleaningConfig, and OutlierCleaningConfig.
2. DataCleaningService zero-mutation handling (empty operation returns 200 with clean audit status instead of HTTP 400).
3. DataQualityService original vs cleaned semantics (version="original", "cleaned", "auto", evaluated_version, has_cleaned).
4. Category normalization, date cleaning, and outlier treatment execution with frontend-style payloads.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from fastapi import HTTPException

# Add backend directory to sys.path
backend_path = os.path.join(os.path.dirname(__file__), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.schemas.cleaning import (
    CleaningOperationsRequest,
    CategoryNormalizationConfig,
    DateCleaningConfig,
    OutlierCleaningConfig,
    MissingImputationConfig,
)
from app.schemas.quality import DataQualityResponse
from app.services.cleaning_service import DataCleaningService
from app.services.quality_service import DataQualityService


class TestCleaningQualityFixesRegression(unittest.TestCase):
    """Verifies all targeted fixes for data cleaning and data quality."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Create a sample clean dataset (no duplicates)
        self.clean_df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "dept": ["IT", "HR", "Sales", "IT", "HR"],
            "score": [80.0, 85.0, 90.0, 82.0, 88.0],
            "join_date": ["2023-01-15", "2023-02-20", "2023-03-25", "2023-04-10", "2023-05-05"],
        })
        self.clean_file = self.dir_path / "clean_dataset.csv"
        self.clean_df.to_csv(self.clean_file, index=False)

        # Create a dataset with missing values, casing variations, and date varieties
        self.dirty_df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "dept": ["it", "HR", "sales", "IT", "hr"],
            "salary": [50000, np.nan, 70000, 80000, np.nan],
            "join_date": ["15/01/2023", "20/02/2023", "25/03/2023", "10/04/2023", "05/05/2023"],
            "score": [85, 90, 88, 92, 9999],  # Outlier
        })
        self.dirty_file = self.dir_path / "dirty_dataset.csv"
        self.dirty_df.to_csv(self.dirty_file, index=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. SCHEMA FIELD NORMALIZATION TESTS
    def test_01_category_normalization_schema_aliases(self):
        """CategoryNormalizationConfig must accept both 'mapping' and 'mappings'."""
        # Using 'mapping' (frontend payload format)
        config1 = CategoryNormalizationConfig(
            column="dept",
            mapping={"it": "IT", "hr": "HR"}
        )
        self.assertEqual(config1.mappings, {"it": "IT", "hr": "HR"})
        self.assertEqual(config1.mapping, {"it": "IT", "hr": "HR"})

        # Using 'mappings' (backend standard format)
        config2 = CategoryNormalizationConfig(
            column="dept",
            mappings={"sales": "Sales"}
        )
        self.assertEqual(config2.mappings, {"sales": "Sales"})
        self.assertEqual(config2.mapping, {"sales": "Sales"})

    def test_02_date_cleaning_schema_aliases(self):
        """DateCleaningConfig must accept both 'output_format' and 'target_format'."""
        # Using 'output_format' (frontend payload format)
        config1 = DateCleaningConfig(
            column="join_date",
            output_format="%Y-%m-%d"
        )
        self.assertEqual(config1.target_format, "%Y-%m-%d")
        self.assertEqual(config1.output_format, "%Y-%m-%d")

        # Using 'target_format' (backend standard format)
        config2 = DateCleaningConfig(
            column="join_date",
            target_format="%d/%m/%Y"
        )
        self.assertEqual(config2.target_format, "%d/%m/%Y")
        self.assertEqual(config2.output_format, "%d/%m/%Y")

    def test_03_outlier_cleaning_schema_aliases(self):
        """OutlierCleaningConfig must accept multiplier->threshold and action->treatment."""
        # Using frontend names 'multiplier' and 'action'
        config1 = OutlierCleaningConfig(
            column="score",
            method="iqr",
            multiplier=1.5,
            action="cap"
        )
        self.assertEqual(config1.threshold, 1.5)
        self.assertEqual(config1.multiplier, 1.5)
        self.assertEqual(config1.treatment, "cap")
        self.assertEqual(config1.action, "cap")

        # Using backend names 'threshold' and 'treatment'
        config2 = OutlierCleaningConfig(
            column="score",
            method="zscore",
            threshold=3.0,
            treatment="remove"
        )
        self.assertEqual(config2.threshold, 3.0)
        self.assertEqual(config2.treatment, "remove")

    # 2. ZERO-MUTATION / EMPTY OPERATION BEHAVIOR
    def test_04_zero_mutation_deduplication_does_not_raise_400(self):
        """Applying deduplication on already unique data should return 200/clean verification, not HTTP 400."""
        dataset = SimpleNamespace(
            id=101,
            user_id=1,
            filename="clean_dataset.csv",
            stored_filename="clean_dataset.csv",
            file_path=str(self.clean_file),
            file_size_bytes=self.clean_file.stat().st_size,
            cleaned_file_path=None,
            has_cleaned=False,
            row_count=5,
            column_count=4,
        )

        req = CleaningOperationsRequest(remove_duplicates=True)
        # Should NOT raise HTTPException
        res = DataCleaningService.apply_cleaning(dataset, req)

        self.assertIsNotNone(res)
        self.assertTrue(res.success)
        self.assertEqual(res.rows_removed, 0)
        # Verify message or operations indicate verification with 0 modifications required
        op_text = res.message.lower() + " " + " ".join(res.operations_performed).lower()
        self.assertTrue("verified" in op_text or "zero modifications" in op_text or "0" in op_text)
        # Verify a new version file was still properly created and recorded
        self.assertIsNotNone(dataset.cleaned_file_path)
        self.assertTrue(os.path.exists(dataset.cleaned_file_path))

    def test_05_zero_mutation_with_no_applicable_changes(self):
        """Applying outlier removal when no outliers exist should succeed safely without error."""
        dataset = SimpleNamespace(
            id=102,
            user_id=1,
            filename="clean_dataset.csv",
            stored_filename="clean_dataset.csv",
            file_path=str(self.clean_file),
            file_size_bytes=self.clean_file.stat().st_size,
            cleaned_file_path=None,
            has_cleaned=False,
            row_count=5,
            column_count=4,
        )

        # scores are 80-90, no outliers at 3.0 threshold
        req = CleaningOperationsRequest(
            outliers=[
                OutlierCleaningConfig(
                    column="score",
                    method="iqr",
                    multiplier=3.0,
                    action="remove"
                )
            ]
        )
        res = DataCleaningService.apply_cleaning(dataset, req)
        self.assertIsNotNone(res)
        self.assertTrue(res.success)
        self.assertEqual(res.rows_removed, 0)

    # 3. END-TO-END EXECUTION WITH FRONTEND-STYLE PAYLOADS
    def test_06_execution_with_aliased_payloads(self):
        """Test full cleaning with mapping, output_format, and multiplier/action in one request."""
        dataset = SimpleNamespace(
            id=103,
            user_id=1,
            filename="dirty_dataset.csv",
            stored_filename="dirty_dataset.csv",
            file_path=str(self.dirty_file),
            file_size_bytes=self.dirty_file.stat().st_size,
            cleaned_file_path=None,
            has_cleaned=False,
            row_count=5,
            column_count=5,
        )

        req = CleaningOperationsRequest(
            missing_values=[
                MissingImputationConfig(column="salary", strategy="mean")
            ],
            categories=[
                CategoryNormalizationConfig(
                    column="dept",
                    mapping={"it": "IT", "hr": "HR", "sales": "Sales"}
                )
            ],
            dates=[
                DateCleaningConfig(
                    column="join_date",
                    output_format="%Y-%m-%d"
                )
            ],
            outliers=[
                OutlierCleaningConfig(
                    column="score",
                    method="iqr",
                    multiplier=1.5,
                    action="cap"
                )
            ]
        )

        res = DataCleaningService.apply_cleaning(dataset, req)
        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        # Verify cleaned file content
        cleaned_df = pd.read_csv(dataset.cleaned_file_path)
        # 1. salary missing filled
        self.assertEqual(cleaned_df["salary"].isna().sum(), 0)
        # 2. dept normalized
        self.assertTrue(set(cleaned_df["dept"].unique()).issubset({"IT", "HR", "Sales"}))
        # 3. score capped (9999 was capped)
        self.assertLess(cleaned_df["score"].max(), 9999)

    # 4. DATA QUALITY ORIGINAL VS CLEANED SEMANTICS
    def test_07_data_quality_original_vs_cleaned(self):
        """DataQualityService must evaluate original or cleaned dataset based on version parameter."""
        dataset = SimpleNamespace(
            id=104,
            user_id=1,
            filename="dirty_dataset.csv",
            stored_filename="dirty_dataset.csv",
            file_path=str(self.dirty_file),
            file_size_bytes=self.dirty_file.stat().st_size,
            cleaned_file_path=None,
            has_cleaned=False,
            row_count=5,
            column_count=5,
        )

        # Before cleaning: original assessment
        report_orig = DataQualityService.assess_dataset(dataset, version="original")
        self.assertEqual(report_orig.evaluated_version, "original")
        self.assertFalse(report_orig.has_cleaned)
        # Missing values exist in original
        self.assertGreater(report_orig.summary.missing_cells, 0)

        # Clean the dataset
        req = CleaningOperationsRequest(
            missing_values=[
                MissingImputationConfig(column="salary", strategy="mean")
            ]
        )
        DataCleaningService.apply_cleaning(dataset, req)

        # After cleaning: assess with version="cleaned"
        report_cleaned = DataQualityService.assess_dataset(dataset, version="cleaned")
        self.assertEqual(report_cleaned.evaluated_version, "cleaned")
        self.assertTrue(report_cleaned.has_cleaned)
        # Missing cells should now be 0 in cleaned
        self.assertEqual(report_cleaned.summary.missing_cells, 0)
        # Quality score of cleaned should be >= original
        self.assertGreaterEqual(report_cleaned.summary.quality_score, report_orig.summary.quality_score)

        # Assess with version="original" should still return original missing cells
        report_orig_again = DataQualityService.assess_dataset(dataset, version="original")
        self.assertEqual(report_orig_again.evaluated_version, "original")
        self.assertTrue(report_orig_again.has_cleaned)  # Cleaned is available
        self.assertGreater(report_orig_again.summary.missing_cells, 0)

        # Assess with version="auto" should pick cleaned since it's available
        report_auto = DataQualityService.assess_dataset(dataset, version="auto")
        self.assertEqual(report_auto.evaluated_version, "cleaned")
        self.assertEqual(report_auto.summary.missing_cells, 0)


if __name__ == "__main__":
    unittest.main()
