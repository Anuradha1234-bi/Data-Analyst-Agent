"""Comprehensive automated test suite for Multi-File Analysis and Multi-Dataset Relationships.

Validates the 12 required test scenarios from the user specification:
1. Uploading and listing multiple files.
2. Selecting three or more datasets.
3. Running individual analysis on different dataset IDs.
4. Combined analysis of all selected datasets.
5. Dataset comparison (shared, unique, type compatibility, comparability notes).
6. Multiple relationships between a dataset pair.
7. One-to-one, one-to-many, many-to-one, and many-to-many cardinality detection.
8. One dataset failing while the others succeed (partial failure tolerance).
9. Invalid, missing, and unauthorized dataset IDs.
10. Ensuring analysis results never overwrite one another.
11. Ensuring original uploaded files remain unchanged (immutability check).
12. Existing single-dataset functionality continues to work without disruption.
"""

import os
import sys
import json
import shutil
import unittest
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np

# Set paths
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.dataset import Dataset
from app.services.profiling_service import ProfilingService
from app.services.multi_dataset_service import MultiDatasetAnalysisService
from services.relationship_detector import RelationshipDetector
from app.schemas.analysis import MultiDatasetAnalysisResponse


class TestMultiFileAnalysisSuite(unittest.TestCase):
    """Full automated verification of Multi-File Analysis and Multi-Dataset features."""

    @classmethod
    def setUpClass(cls):
        """Set up in-memory or dedicated test database and test datasets."""
        cls.temp_dir = tempfile.mkdtemp(prefix="test_multi_file_")
        cls.db_path = Path(cls.temp_dir) / "test_suite.db"
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", echo=False)
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        cls.db = cls.SessionLocal()

        # Create two test users (to test authorization / tenant isolation)
        cls.user1 = User(
            email="analyst1@example.com",
            full_name="Lead Analyst",
            hashed_password="fakehashpassword123",
            is_active=True,
        )
        cls.user2 = User(
            email="intruder@example.com",
            full_name="Other User",
            hashed_password="fakehashpassword456",
            is_active=True,
        )
        cls.db.add_all([cls.user1, cls.user2])
        cls.db.commit()
        cls.db.refresh(cls.user1)
        cls.db.refresh(cls.user2)

        # Create 3 realistic relational datasets for User 1
        # Dataset A: Customers (3 records, unique customer_id)
        cls.df_customers = pd.DataFrame({
            "customer_id": [1001, 1002, 1003],
            "company_name": ["Alpha Inc", "Beta Corp", "Gamma LLC"],
            "region": ["North", "South", "East"],
            "tier": ["Gold", "Silver", "Platinum"],
        })

        # Dataset B: Orders (6 records, repeated customer_id -> Many-to-One to customers)
        cls.df_orders = pd.DataFrame({
            "order_id": [501, 502, 503, 504, 505, 506],
            "customer_id": [1001, 1001, 1002, 1003, 1003, 1003],
            "order_amount": [1200.50, 450.00, 3200.00, 150.25, 980.00, 2100.00],
            "status": ["Completed", "Completed", "Pending", "Completed", "Cancelled", "Completed"],
        })

        # Dataset C: Shipments (6 records, 1:1 match on order_id to orders)
        cls.df_shipments = pd.DataFrame({
            "shipment_id": [901, 902, 903, 904, 905, 906],
            "order_id": [501, 502, 503, 504, 505, 506],
            "carrier": ["FedEx", "UPS", "DHL", "FedEx", "USPS", "DHL"],
            "tracking_number": ["TRK-1", "TRK-2", "TRK-3", "TRK-4", "TRK-5", "TRK-6"],
        })

        # Write files to disk
        cls.path_cust = Path(cls.temp_dir) / "customers.csv"
        cls.path_orders = Path(cls.temp_dir) / "orders.csv"
        cls.path_ship = Path(cls.temp_dir) / "shipments.csv"
        cls.df_customers.to_csv(cls.path_cust, index=False)
        cls.df_orders.to_csv(cls.path_orders, index=False)
        cls.df_shipments.to_csv(cls.path_ship, index=False)

        # Create Database records for User 1
        cls.ds_cust = Dataset(
            user_id=cls.user1.id,
            filename="customers.csv",
            file_type="csv",
            file_path=str(cls.path_cust),
            rows=len(cls.df_customers),
            columns=len(cls.df_customers.columns),
            file_size_bytes=cls.path_cust.stat().st_size,
        )
        cls.ds_orders = Dataset(
            user_id=cls.user1.id,
            filename="orders.csv",
            file_type="csv",
            file_path=str(cls.path_orders),
            rows=len(cls.df_orders),
            columns=len(cls.df_orders.columns),
            file_size_bytes=cls.path_orders.stat().st_size,
        )
        cls.ds_ship = Dataset(
            user_id=cls.user1.id,
            filename="shipments.csv",
            file_type="csv",
            file_path=str(cls.path_ship),
            rows=len(cls.df_shipments),
            columns=len(cls.df_shipments.columns),
            file_size_bytes=cls.path_ship.stat().st_size,
        )

        # Create a dataset for User 2 (unauthorized to User 1)
        cls.path_user2 = Path(cls.temp_dir) / "user2_secret.csv"
        pd.DataFrame({"secret_id": [1, 2]}).to_csv(cls.path_user2, index=False)
        cls.ds_user2 = Dataset(
            user_id=cls.user2.id,
            filename="user2_secret.csv",
            file_type="csv",
            file_path=str(cls.path_user2),
            rows=2,
            columns=1,
            file_size_bytes=cls.path_user2.stat().st_size,
        )

        cls.db.add_all([cls.ds_cust, cls.ds_orders, cls.ds_ship, cls.ds_user2])
        cls.db.commit()
        cls.db.refresh(cls.ds_cust)
        cls.db.refresh(cls.ds_orders)
        cls.db.refresh(cls.ds_ship)
        cls.db.refresh(cls.ds_user2)

    @classmethod
    def tearDownClass(cls):
        """Cleanup test database and temporary directory."""
        cls.db.close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_uploading_and_listing_multiple_files(self):
        """1. Verify multiple files are listed correctly with correct metadata."""
        user1_datasets = (
            self.db.query(Dataset)
            .filter(Dataset.user_id == self.user1.id)
            .order_by(Dataset.id.asc())
            .all()
        )
        self.assertEqual(len(user1_datasets), 3)
        filenames = [d.filename for d in user1_datasets]
        self.assertIn("customers.csv", filenames)
        self.assertIn("orders.csv", filenames)
        self.assertIn("shipments.csv", filenames)

    def test_02_selecting_three_or_more_datasets(self):
        """2. Verify selecting 3 datasets produces a valid MultiDatasetAnalysisResponse."""
        ids = [self.ds_cust.id, self.ds_orders.id, self.ds_ship.id]
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

    def test_03_running_individual_analysis_on_different_dataset_ids(self):
        """3. Running individual analysis associates profiles strictly with correct dataset IDs."""
        ids = [self.ds_cust.id, self.ds_orders.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="individual",
            current_user=self.user1,
            db=self.db,
        )
        prof_cust = resp.individual_profiles.get(self.ds_cust.id)
        prof_orders = resp.individual_profiles.get(self.ds_orders.id)

        self.assertIsNotNone(prof_cust)
        self.assertIsNotNone(prof_orders)

        self.assertEqual(prof_cust.dataset_info.id, self.ds_cust.id)
        self.assertEqual(prof_cust.dataset_info.rows, 3)
        self.assertEqual(prof_cust.dataset_info.columns, 4)

        self.assertEqual(prof_orders.dataset_info.id, self.ds_orders.id)
        self.assertEqual(prof_orders.dataset_info.rows, 6)
        self.assertEqual(prof_orders.dataset_info.columns, 4)

    def test_04_combined_analysis_of_all_selected_datasets(self):
        """4. Combined analysis aggregates rows, columns, cells, and per-dataset summaries."""
        ids = [self.ds_cust.id, self.ds_orders.id, self.ds_ship.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="combined",
            current_user=self.user1,
            db=self.db,
        )
        overview = resp.combined_overview
        self.assertIsNotNone(overview)
        self.assertEqual(overview.total_datasets, 3)
        self.assertEqual(overview.total_rows, 3 + 6 + 6)  # 15 total rows
        self.assertEqual(overview.total_columns, 4 + 4 + 4)  # 12 total columns
        self.assertEqual(len(overview.dataset_summaries), 3)
        self.assertEqual(overview.overall_missing_percentage, 0.0)

    def test_05_dataset_comparison(self):
        """5. Dataset comparison matrix displays shared columns, unique columns, and type checks."""
        ids = [self.ds_cust.id, self.ds_orders.id, self.ds_ship.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="comparison",
            current_user=self.user1,
            db=self.db,
        )
        comp = resp.comparison
        self.assertIsNotNone(comp)
        self.assertTrue(comp.is_comparable)
        self.assertIn("customer_id", comp.shared_columns)
        self.assertIn("order_id", comp.shared_columns)
        self.assertIn("company_name", comp.unique_columns.get("customers.csv", []))
        self.assertIn("tracking_number", comp.unique_columns.get("shipments.csv", []))

    def test_06_multiple_relationships_between_a_dataset_pair(self):
        """6. Multiple relationships between the same pair are identified."""
        df_a = pd.DataFrame({
            "account_id": [1, 2, 3],
            "billing_code": ["B1", "B2", "B3"],
            "data": ["X", "Y", "Z"],
        })
        df_b = pd.DataFrame({
            "account_id": [1, 2, 3],
            "billing_code": ["B1", "B2", "B3"],
            "val": [10, 20, 30],
        })
        rels = RelationshipDetector.detect_all_relationships({"a.csv": df_a, "b.csv": df_b})
        matched_cols = {r.source_column for r in rels}
        self.assertGreaterEqual(len(rels), 2)
        self.assertIn("account_id", matched_cols)
        self.assertIn("billing_code", matched_cols)

    def test_07_all_cardinalities(self):
        """7. Verify 1:1, 1:N, N:1, and M:N cardinalities with safeguards."""
        # 1:1
        df_u = pd.DataFrame({"id": [1, 2, 3], "name": ["A", "B", "C"]})
        df_p = pd.DataFrame({"id": [1, 2, 3], "bio": ["Bio1", "Bio2", "Bio3"]})
        r_11 = RelationshipDetector.detect_all_relationships({"u.csv": df_u, "p.csv": df_p})
        self.assertEqual(r_11[0].relationship_type, "One-to-One")
        self.assertEqual(r_11[0].cardinality_symbol, "1:1")

        # 1:N
        df_dept = pd.DataFrame({"dept_id": [10, 20], "dept_name": ["HR", "IT"]})
        df_emp = pd.DataFrame({"emp_id": [1, 2, 3], "dept_id": [10, 10, 20]})
        r_1n = RelationshipDetector.detect_all_relationships({"dept.csv": df_dept, "emp.csv": df_emp})
        self.assertEqual(r_1n[0].relationship_type, "One-to-Many")
        self.assertEqual(r_1n[0].cardinality_symbol, "1:N")

        # N:1
        r_n1 = RelationshipDetector.detect_all_relationships({"emp.csv": df_emp, "dept.csv": df_dept})
        self.assertEqual(r_n1[0].relationship_type, "Many-to-One")
        self.assertEqual(r_n1[0].cardinality_symbol, "N:1")

        # M:N
        df_m1 = pd.DataFrame({"tag": ["T1", "T1", "T2"], "item": ["I1", "I2", "I3"]})
        df_m2 = pd.DataFrame({"tag": ["T1", "T1", "T2", "T2"], "desc": ["D1", "D2", "D3", "D4"]})
        r_mn = RelationshipDetector.detect_all_relationships({"m1.csv": df_m1, "m2.csv": df_m2})
        self.assertEqual(r_mn[0].relationship_type, "Many-to-Many")
        self.assertEqual(r_mn[0].cardinality_symbol, "M:N")
        self.assertFalse(r_mn[0].safe_for_join)

    def test_08_one_dataset_failing_while_others_succeed(self):
        """8. Partial failure: 1 invalid dataset fails while 2 valid datasets succeed."""
        # Create a corrupted / missing dataset database record
        ghost_ds = Dataset(
            user_id=self.user1.id,
            filename="missing_file.csv",
            file_type="csv",
            file_path=str(Path(self.temp_dir) / "does_not_exist.csv"),
            rows=10,
            columns=2,
            file_size_bytes=100,
        )
        self.db.add(ghost_ds)
        self.db.commit()
        self.db.refresh(ghost_ds)

        ids = [self.ds_cust.id, ghost_ds.id, self.ds_orders.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        self.assertEqual(resp.status, "partial")
        self.assertEqual(resp.total_selected, 3)
        self.assertEqual(resp.total_successful, 2)
        self.assertEqual(resp.total_failed, 1)
        self.assertEqual(len(resp.errors), 1)
        self.assertEqual(resp.errors[0].dataset_id, ghost_ds.id)
        # Ensure remaining 2 datasets were analyzed completely
        self.assertIn(self.ds_cust.id, resp.individual_profiles)
        self.assertIn(self.ds_orders.id, resp.individual_profiles)
        self.assertIsNotNone(resp.combined_overview)
        self.assertEqual(resp.combined_overview.total_datasets, 2)

    def test_09_invalid_missing_and_unauthorized_dataset_ids(self):
        """9. Unauthorized dataset belonging to another user is rejected with error."""
        # User 1 tries to access User 2's dataset
        ids = [self.ds_cust.id, self.ds_user2.id, 999999]  # 999999 is non-existent
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        self.assertEqual(resp.status, "partial")
        self.assertEqual(resp.total_successful, 1)  # Only ds_cust
        self.assertEqual(resp.total_failed, 2)  # ds_user2 and 999999 rejected
        failed_ids = {e.dataset_id for e in resp.errors}
        self.assertIn(self.ds_user2.id, failed_ids)
        self.assertIn(999999, failed_ids)

    def test_10_ensuring_analysis_results_never_overwrite_one_another(self):
        """10. Analysis results for different datasets retain their own schemas and values."""
        ids = [self.ds_cust.id, self.ds_orders.id, self.ds_ship.id]
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        p1 = resp.individual_profiles[self.ds_cust.id]
        p2 = resp.individual_profiles[self.ds_orders.id]
        p3 = resp.individual_profiles[self.ds_ship.id]

        cols1 = {c.name for c in p1.columns}
        cols2 = {c.name for c in p2.columns}
        cols3 = {c.name for c in p3.columns}

        self.assertIn("company_name", cols1)
        self.assertNotIn("company_name", cols2)
        self.assertNotIn("company_name", cols3)

        self.assertIn("order_amount", cols2)
        self.assertNotIn("order_amount", cols1)

        self.assertIn("tracking_number", cols3)
        self.assertNotIn("tracking_number", cols1)

    def test_11_ensuring_original_uploaded_files_remain_unchanged(self):
        """11. File hashes / contents on disk remain exactly identical before and after analysis."""
        with open(self.path_cust, "rb") as f:
            bytes_before = f.read()

        ids = [self.ds_cust.id, self.ds_orders.id]
        MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=ids,
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        with open(self.path_cust, "rb") as f:
            bytes_after = f.read()

        self.assertEqual(bytes_before, bytes_after, "Original uploaded file was mutated!")

    def test_12_existing_single_dataset_functionality_continues_to_work(self):
        """12. ProfilingService.get_dataset_profile works independently without regression."""
        single_profile = ProfilingService.get_dataset_profile(self.ds_cust)
        self.assertIsNotNone(single_profile)
        self.assertEqual(single_profile.dataset_info.id, self.ds_cust.id)
        self.assertEqual(single_profile.dataset_info.rows, 3)
        self.assertEqual(single_profile.dataset_info.columns, 4)
    @classmethod
    def tearDownClass(cls):
        """Clean up test database connection and temporary directory."""
        if hasattr(cls, "db"):
            cls.db.close()
        if hasattr(cls, "engine"):
            cls.engine.dispose()
        if hasattr(cls, "temp_dir") and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
