"""Comprehensive regression test suite for complete multi-dataset processing pipeline.

Verifies:
1. Multiple selected datasets are all processed.
2. Every dataset receives the same applicable processing stages as the single-dataset workflow:
   - File loading and validation
   - Data Profiling
   - Data Quality assessment
   - Missing-value & duplicate detection
   - Data Cleaning & preprocessing diagnostics
   - Column type detection
   - Statistical summaries and descriptive analytics
   - Outlier and anomaly detection
   - Dataset-specific insights
3. Profiling and quality metrics are calculated independently for every dataset.
4. Cleaning decisions and cleaned outputs remain dataset-specific.
5. Identical data under different filenames remains stored separately (never auto-merged).
6. Cross-dataset relationships and schema comparisons continue working.
7. Analytical joins and multi-file queries do not modify original files.
8. One dataset's processing failure does not silently skip other datasets (partial failure tolerance).
9. Dataset ownership and authorization are strictly enforced.
10. Existing single-dataset processing continues working correctly.
"""

import sys
import unittest
import tempfile
import shutil
from pathlib import Path
import pandas as pd
import numpy as np
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.dataset import Dataset
from app.schemas.analyst import AnalysisAskRequest
from app.schemas.anomaly import AnomalyDetectRequest
from app.services.profiling_service import ProfilingService
from app.services.quality_service import DataQualityService
from app.services.cleaning_service import DataCleaningService
from app.services.analytics_service import AnalyticsService
from app.services.anomaly_service import AnomalyService
from app.services.data_analyst_service import DataAnalystService
from app.services.multi_dataset_service import MultiDatasetAnalysisService


class TestMultiDatasetFullPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="test_full_pipeline_")
        cls.db_path = Path(cls.temp_dir) / "test_pipeline.db"
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", echo=False)
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        cls.db = cls.SessionLocal()

        # Users
        cls.user1 = User(
            email="analyst@enterprise.com",
            full_name="Lead Analyst",
            hashed_password="pw1",
            is_active=True,
        )
        cls.user2 = User(
            email="intruder@enterprise.com",
            full_name="Intruder",
            hashed_password="pw2",
            is_active=True,
        )
        cls.db.add_all([cls.user1, cls.user2])
        cls.db.commit()

        # Create three distinct datasets for User 1
        # Dataset 1: customers.csv
        cls.df_customers = pd.DataFrame({
            "customer_id": [101, 102, 103, 104, 105],
            "customer_name": ["Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", "Evan Wright"],
            "region": ["North", "South", "East", "West", "North"],
            "age": [28, 34, 45, 29, 52],
        })
        cust_path = Path(cls.temp_dir) / "customers.csv"
        cls.df_customers.to_csv(cust_path, index=False)
        cls.ds_customers = Dataset(
            user_id=cls.user1.id,
            filename="customers.csv",
            stored_filename="stored_customers.csv",
            file_type="csv",
            file_path=str(cust_path),
            rows=len(cls.df_customers),
            columns=len(cls.df_customers.columns),
            file_size_bytes=cust_path.stat().st_size,
        )

        # Dataset 2: orders.csv
        cls.df_orders = pd.DataFrame({
            "order_id": [1001, 1002, 1003, 1004, 1005, 1006],
            "customer_id": [101, 102, 101, 103, 104, 105],
            "order_amount": [250.0, 120.5, 450.0, 95.0, 1200.0, 310.0],
            "order_date": ["2026-01-15", "2026-01-16", "2026-01-18", "2026-01-20", "2026-01-22", "2026-01-25"],
        })
        orders_path = Path(cls.temp_dir) / "orders.csv"
        cls.df_orders.to_csv(orders_path, index=False)
        cls.ds_orders = Dataset(
            user_id=cls.user1.id,
            filename="orders.csv",
            stored_filename="stored_orders.csv",
            file_type="csv",
            file_path=str(orders_path),
            rows=len(cls.df_orders),
            columns=len(cls.df_orders.columns),
            file_size_bytes=orders_path.stat().st_size,
        )

        # Dataset 3: products.csv
        cls.df_products = pd.DataFrame({
            "product_id": [1, 2, 3, 4, 5],
            "product_name": ["Laptop", "Mouse", "Keyboard", "Monitor", "Headphones"],
            "category": ["Electronics", "Accessories", "Accessories", "Electronics", "Audio"],
            "unit_price": [1200.0, 25.0, 75.0, 300.0, 150.0],
        })
        prod_path = Path(cls.temp_dir) / "products.csv"
        cls.df_products.to_csv(prod_path, index=False)
        cls.ds_products = Dataset(
            user_id=cls.user1.id,
            filename="products.csv",
            stored_filename="stored_products.csv",
            file_type="csv",
            file_path=str(prod_path),
            rows=len(cls.df_products),
            columns=len(cls.df_products.columns),
            file_size_bytes=prod_path.stat().st_size,
        )

        # Dataset 4: Identical data to customers.csv but with a different filename (duplicate data test)
        ident_path = Path(cls.temp_dir) / "customers_backup_copy.csv"
        cls.df_customers.to_csv(ident_path, index=False)
        cls.ds_identical = Dataset(
            user_id=cls.user1.id,
            filename="customers_backup_copy.csv",
            stored_filename="stored_customers_backup_copy.csv",
            file_type="csv",
            file_path=str(ident_path),
            rows=len(cls.df_customers),
            columns=len(cls.df_customers.columns),
            file_size_bytes=ident_path.stat().st_size,
        )

        # Dataset 5: Owned by User 2 (unauthorized test)
        u2_path = Path(cls.temp_dir) / "user2_private.csv"
        pd.DataFrame({"secret": [1, 2, 3]}).to_csv(u2_path, index=False)
        cls.ds_user2 = Dataset(
            user_id=cls.user2.id,
            filename="user2_private.csv",
            stored_filename="stored_user2_private.csv",
            file_type="csv",
            file_path=str(u2_path),
            rows=3,
            columns=1,
            file_size_bytes=u2_path.stat().st_size,
        )

        cls.db.add_all([cls.ds_customers, cls.ds_orders, cls.ds_products, cls.ds_identical, cls.ds_user2])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_multiple_selected_datasets_all_processed(self):
        """1. Verify selecting 3 datasets processes all 3 datasets completely."""
        ids = [self.ds_customers.id, self.ds_orders.id, self.ds_products.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.total_selected, 3)
        self.assertEqual(resp.total_successful, 3)
        self.assertEqual(resp.total_failed, 0)
        self.assertEqual(len(resp.individual_profiles), 3)
        self.assertEqual(len(resp.dataset_pipeline_results), 3)

    def test_02_all_phases_executed_per_dataset(self):
        """2. Verify every dataset goes through all applicable processing stages."""
        ids = [self.ds_customers.id, self.ds_orders.id, self.ds_products.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        for ds_id in ids:
            # Check pipeline result container
            pipe_res = resp.dataset_pipeline_results.get(ds_id)
            self.assertIsNotNone(pipe_res, f"Dataset {ds_id} missing pipeline result")
            self.assertEqual(pipe_res.status, "completed")

            # Phase 1: Loading
            self.assertIn("loading", pipe_res.phases_completed)

            # Phase 2: Profiling
            self.assertIn("profiling", pipe_res.phases_completed)
            self.assertIsNotNone(resp.individual_profiles.get(ds_id))
            self.assertIsNotNone(pipe_res.profile)

            # Phase 3: Data Quality Assessment
            self.assertIn("quality", pipe_res.phases_completed)
            self.assertIsNotNone(resp.individual_quality.get(ds_id))
            self.assertIsNotNone(pipe_res.quality)
            self.assertGreaterEqual(pipe_res.quality.summary.quality_score, 0)

            # Phase 4: Data Cleaning Diagnostics
            self.assertIn("cleaning", pipe_res.phases_completed)
            self.assertIsNotNone(resp.individual_cleaning.get(ds_id))
            self.assertIsNotNone(pipe_res.cleaning)

            # Phase 5: Statistical Analytics & KPIs
            self.assertIn("analytics", pipe_res.phases_completed)
            self.assertIsNotNone(resp.individual_analytics.get(ds_id))
            self.assertIsNotNone(pipe_res.analytics)
            self.assertGreater(len(pipe_res.analytics.kpi_cards), 0)

            # Phase 6: Outlier & Anomaly Detection
            self.assertIn("anomalies", pipe_res.phases_completed)
            self.assertIsNotNone(resp.individual_anomalies.get(ds_id))
            self.assertIsNotNone(pipe_res.anomalies)

            # Phase 7: Dataset-Specific Insights
            self.assertIn("insights", pipe_res.phases_completed)
            self.assertIsNotNone(resp.individual_insights.get(ds_id))
            self.assertIsNotNone(pipe_res.insights)

    def test_03_independent_profiling_and_quality_metrics(self):
        """3. Profiling and quality metrics are calculated independently per dataset."""
        ids = [self.ds_customers.id, self.ds_orders.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        cust_profile = resp.individual_profiles[self.ds_customers.id]
        orders_profile = resp.individual_profiles[self.ds_orders.id]

        # Row counts match their respective distinct datasets
        self.assertEqual(cust_profile.dataset_info.rows, 5)
        self.assertEqual(orders_profile.dataset_info.rows, 6)

        # Columns match distinct schemas
        self.assertEqual(cust_profile.dataset_info.columns, 4)
        self.assertEqual(orders_profile.dataset_info.columns, 4)
        cust_cols = [c.name for c in cust_profile.columns]
        orders_cols = [c.name for c in orders_profile.columns]
        self.assertIn("customer_name", cust_cols)
        self.assertNotIn("order_amount", cust_cols)
        self.assertIn("order_amount", orders_cols)

    def test_04_cleaning_decisions_dataset_specific(self):
        """4. Cleaning decisions and recommendations remain isolated per dataset."""
        ids = [self.ds_customers.id, self.ds_orders.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        cust_clean = resp.individual_cleaning[self.ds_customers.id]
        orders_clean = resp.individual_cleaning[self.ds_orders.id]

        self.assertEqual(cust_clean.dataset_id, self.ds_customers.id)
        self.assertEqual(orders_clean.dataset_id, self.ds_orders.id)
        self.assertEqual(cust_clean.filename, "customers.csv")
        self.assertEqual(orders_clean.filename, "orders.csv")

    def test_05_identical_data_different_filenames_never_merged(self):
        """5. Different filenames containing identical data remain separate datasets."""
        ids = [self.ds_customers.id, self.ds_identical.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        # Both remain distinct datasets with their own IDs
        self.assertEqual(resp.total_selected, 2)
        self.assertEqual(resp.total_successful, 2)
        self.assertIn(self.ds_customers.id, resp.individual_profiles)
        self.assertIn(self.ds_identical.id, resp.individual_profiles)
        self.assertNotEqual(self.ds_customers.id, self.ds_identical.id)

        # Files on disk are preserved separately
        self.assertNotEqual(self.ds_customers.file_path, self.ds_identical.file_path)
        self.assertTrue(Path(self.ds_customers.file_path).exists())
        self.assertTrue(Path(self.ds_identical.file_path).exists())

    def test_06_cross_dataset_relationships_and_schema_comparison(self):
        """6. Cross-dataset relationships and schema comparisons work accurately."""
        ids = [self.ds_customers.id, self.ds_orders.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        self.assertIsNotNone(resp.comparison)
        self.assertIn("customer_id", resp.comparison.shared_columns)
        self.assertIn("customer_name", resp.comparison.unique_columns.get("customers.csv", []))
        self.assertIn("order_amount", resp.comparison.unique_columns.get("orders.csv", []))

        # Check detected relationship
        self.assertGreater(len(resp.relationships), 0)
        rel_cols = [(r.source_column.lower(), r.target_column.lower()) for r in resp.relationships]
        self.assertTrue(any("customer_id" in pair for pair in rel_cols))

    def test_07_immutability_original_files_untouched(self):
        """7. Profiling, cleaning overviews, and analytical joins do not alter original files."""
        cust_mtime_before = Path(self.ds_customers.file_path).stat().st_mtime
        cust_size_before = Path(self.ds_customers.file_path).stat().st_size

        # Run multi-file analysis
        MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds_customers.id, self.ds_orders.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        # Run multi-dataset question
        DataAnalystService.ask_question(
            request=AnalysisAskRequest(
                dataset_id=self.ds_customers.id,
                dataset_ids=[self.ds_customers.id, self.ds_orders.id],
                question="Compare row count between customers and orders",
            ),
            current_user=self.user1,
            db=self.db,
        )

        cust_mtime_after = Path(self.ds_customers.file_path).stat().st_mtime
        cust_size_after = Path(self.ds_customers.file_path).stat().st_size

        self.assertEqual(cust_mtime_before, cust_mtime_after)
        self.assertEqual(cust_size_before, cust_size_after)

    def test_08_partial_failure_tolerance(self):
        """8. One dataset failing does not silently prevent other datasets from processing."""
        # Non-existent ID 9999 + valid ID
        ids = [self.ds_customers.id, 9999]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        self.assertEqual(resp.status, "partial")
        self.assertEqual(resp.total_selected, 2)
        self.assertEqual(resp.total_successful, 1)
        self.assertEqual(resp.total_failed, 1)
        self.assertEqual(resp.errors[0].dataset_id, 9999)

        # Valid dataset succeeded completely across its pipeline
        pipe_res = resp.dataset_pipeline_results.get(self.ds_customers.id)
        self.assertIsNotNone(pipe_res)
        self.assertEqual(pipe_res.status, "completed")
        self.assertIn("profiling", pipe_res.phases_completed)
        self.assertIn("quality", pipe_res.phases_completed)

    def test_09_ownership_and_authorization_enforced(self):
        """9. Multi-dataset analysis rejects unauthorized datasets belonging to other users."""
        ids = [self.ds_customers.id, self.ds_user2.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        self.assertEqual(resp.status, "partial")
        self.assertEqual(resp.total_successful, 1)
        self.assertEqual(resp.total_failed, 1)
        self.assertEqual(resp.errors[0].dataset_id, self.ds_user2.id)
        self.assertIn("access denied", resp.errors[0].error.lower())

    def test_10_single_dataset_processing_unaffected(self):
        """10. Existing single-dataset workflows continue working without disruption."""
        prof = ProfilingService.get_dataset_profile(self.ds_customers)
        self.assertEqual(prof.dataset_info.rows, 5)

        qual = DataQualityService.analyze_dataset_quality(self.ds_customers)
        self.assertEqual(qual.dataset_id, self.ds_customers.id)

        clean = DataCleaningService.get_cleaning_overview(self.ds_customers, self.db)
        self.assertEqual(clean.dataset_id, self.ds_customers.id)

        analytics = AnalyticsService.get_analytics_overview(self.ds_customers.id, "original", self.user1, self.db)
        self.assertEqual(analytics.rows, 5)


if __name__ == "__main__":
    unittest.main()
