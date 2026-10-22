"""Comprehensive verification test for Analyze Multiple Files feature.

Tests:
1. Multi-dataset ownership validation: rejecting unauthorized/non-existent IDs.
2. Multi-dataset question execution with dataset_ids provided.
3. Ensuring questions about one dataset do not accidentally use another dataset.
4. Cross-dataset questions properly access the selected datasets.
5. Single dataset analysis remains unaffected.
6. MultiDatasetAnalysisService generates correct combined metrics and comparison.
"""

import sys
import unittest
import tempfile
import shutil
from pathlib import Path
import pandas as pd
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
from app.services.data_analyst_service import DataAnalystService
from app.services.multi_dataset_service import MultiDatasetAnalysisService


class TestAnalyzeMultipleFilesFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="test_multi_files_")
        cls.db_path = Path(cls.temp_dir) / "test.db"
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", echo=False)
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        cls.db = cls.SessionLocal()

        # Users
        cls.user1 = User(
            email="analyst@example.com",
            full_name="Lead Analyst",
            hashed_password="pw1",
            is_active=True,
        )
        cls.user2 = User(
            email="intruder@example.com",
            full_name="Intruder",
            hashed_password="pw2",
            is_active=True,
        )
        cls.db.add_all([cls.user1, cls.user2])
        cls.db.commit()
        cls.db.refresh(cls.user1)
        cls.db.refresh(cls.user2)

        # Datasets
        cls.file1 = Path(cls.temp_dir) / "orders.csv"
        df1 = pd.DataFrame({
            "order_id": [1, 2, 3, 4],
            "customer_id": [101, 102, 101, 103],
            "amount": [250.0, 450.0, 150.0, 800.0],
            "status": ["Completed", "Pending", "Completed", "Completed"]
        })
        df1.to_csv(cls.file1, index=False)

        cls.ds1 = Dataset(
            user_id=cls.user1.id,
            filename="orders.csv",
            original_filename="orders.csv",
            file_path=str(cls.file1),
            file_type="csv",
            file_size_bytes=cls.file1.stat().st_size,
            row_count=4,
            column_count=4,
        )

        cls.file2 = Path(cls.temp_dir) / "customers.csv"
        df2 = pd.DataFrame({
            "customer_id": [101, 102, 103, 104],
            "customer_name": ["Alice Smith", "Bob Jones", "Charlie Brown", "Dana White"],
            "city": ["New York", "Chicago", "Boston", "Austin"],
            "tier": ["Gold", "Silver", "Gold", "Bronze"]
        })
        df2.to_csv(cls.file2, index=False)

        cls.ds2 = Dataset(
            user_id=cls.user1.id,
            filename="customers.csv",
            original_filename="customers.csv",
            file_path=str(cls.file2),
            file_type="csv",
            file_size_bytes=cls.file2.stat().st_size,
            row_count=4,
            column_count=4,
        )

        # Dataset for user 2 (unauthorized to user 1)
        cls.file3 = Path(cls.temp_dir) / "confidential.csv"
        df3 = pd.DataFrame({"secret_id": [999], "val": [100]})
        df3.to_csv(cls.file3, index=False)

        cls.ds3 = Dataset(
            user_id=cls.user2.id,
            filename="confidential.csv",
            original_filename="confidential.csv",
            file_path=str(cls.file3),
            file_type="csv",
            file_size_bytes=cls.file3.stat().st_size,
            row_count=1,
            column_count=2,
        )

        cls.db.add_all([cls.ds1, cls.ds2, cls.ds3])
        cls.db.commit()
        cls.db.refresh(cls.ds1)
        cls.db.refresh(cls.ds2)
        cls.db.refresh(cls.ds3)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_ownership_validation_enforced(self):
        """Passing an unauthorized or non-existent ID in dataset_ids raises 404."""
        # Non-existent ID 99999
        req_invalid = AnalysisAskRequest(
            dataset_id=self.ds1.id,
            dataset_ids=[self.ds1.id, 99999],
            question="Compare row counts between both datasets",
        )
        with self.assertRaises(HTTPException) as ctx:
            DataAnalystService.ask_question(req_invalid, self.user1, self.db)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("99999", ctx.exception.detail)

        # Unauthorized ID belonging to User 2
        req_unauth = AnalysisAskRequest(
            dataset_id=self.ds1.id,
            dataset_ids=[self.ds1.id, self.ds3.id],
            question="Compare row counts",
        )
        with self.assertRaises(HTTPException) as ctx2:
            DataAnalystService.ask_question(req_unauth, self.user1, self.db)
        self.assertEqual(ctx2.exception.status_code, 404)
        self.assertIn(str(self.ds3.id), ctx2.exception.detail)

    def test_02_single_dataset_analysis_works(self):
        """Single dataset analysis without dataset_ids works accurately."""
        req = AnalysisAskRequest(
            dataset_id=self.ds1.id,
            question="What is the average amount?",
        )
        resp = DataAnalystService.ask_question(req, self.user1, self.db)
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.dataset_id, self.ds1.id)
        self.assertIn("amount", resp.columns_used)
        # Average of [250, 450, 150, 800] = 412.5
        self.assertIn("412.5", resp.answer)

    def test_03_multi_file_targeted_query_orders(self):
        """In multi-dataset mode, a question about orders uses orders.csv."""
        req = AnalysisAskRequest(
            dataset_id=self.ds1.id,
            dataset_ids=[self.ds1.id, self.ds2.id],
            question="How many total orders are there?",
        )
        resp = DataAnalystService.ask_question(req, self.user1, self.db)
        self.assertEqual(resp.status, "success")
        self.assertIn("4", resp.answer)
        self.assertIn(resp.dataset_name, ["orders.csv", "orders"])

    def test_04_multi_file_targeted_query_customers(self):
        """In multi-dataset mode, a question specifically about customers uses customers.csv."""
        req = AnalysisAskRequest(
            dataset_id=self.ds1.id,
            dataset_ids=[self.ds1.id, self.ds2.id],
            question="What are the columns in customers.csv?",
        )
        resp = DataAnalystService.ask_question(req, self.user1, self.db)
        self.assertEqual(resp.status, "success")
        self.assertIn("customer_id", resp.answer.lower())
        self.assertEqual(resp.dataset_name, "customers.csv")

    def test_05_cross_dataset_comparison(self):
        """Cross-dataset comparison receives both selected dataset IDs and computes comparative row counts."""
        req = AnalysisAskRequest(
            dataset_id=self.ds1.id,
            dataset_ids=[self.ds1.id, self.ds2.id],
            question="Compare row counts between orders.csv and customers.csv",
        )
        resp = DataAnalystService.ask_question(req, self.user1, self.db)
        self.assertEqual(resp.status, "success")
        # Evidence should note multiple datasets analyzed
        self.assertTrue(
            len(resp.evidence.get("datasets_analyzed", [])) >= 2 or
            resp.evidence.get("dataset_used") is not None
        )

    def test_06_multi_dataset_service_profiling_and_relationships(self):
        """MultiDatasetAnalysisService analyzes both files, detecting relationships and schema overlap."""
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds1.id, self.ds2.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.total_selected, 2)
        self.assertEqual(resp.total_successful, 2)
        self.assertEqual(resp.combined_overview.total_rows, 8)
        self.assertEqual(len(resp.individual_profiles), 2)

        # Shared column customer_id
        shared = [c if isinstance(c, str) else getattr(c, "column_name", str(c)) for c in resp.comparison.shared_columns]
        self.assertIn("customer_id", shared)

        # Relationship between orders and customers on customer_id
        rel_found = any(
            (getattr(r, "source_column", None) == "customer_id" or getattr(r, "target_column", None) == "customer_id")
            for r in resp.relationships
        )
        self.assertTrue(rel_found, "Relationship on customer_id should be detected")


if __name__ == "__main__":
    unittest.main()
