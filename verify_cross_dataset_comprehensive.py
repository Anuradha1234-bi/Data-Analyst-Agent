"""Comprehensive programmatic cross-dataset verification script.
Tests:
1. Cross-Dataset Comparisons (combined & per-dataset metrics, independent aggregates, ID indexing).
2. Schema Matching (identical names, renamed equivalents, type incompatibilities, extra/missing columns).
3. Relationship Detection (PK/FK detection, cardinality, rejection of non-relational columns like City and Age).
4. Combined Analysis & Joins (inner & left join mathematical verification, row count, sum, Cartesian explosion safeguard).
5. Dataset Isolation (similar names & overlapping schemas, tenant & dataset-level isolation).
"""

import os
import sys
import shutil
import unittest
import tempfile
import pandas as pd
import numpy as np
from pathlib import Path

# Insert backend directory
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.dataset import Dataset
from app.services.multi_dataset_service import MultiDatasetAnalysisService
from app.services.relationship_service import RelationshipService
from services.relationship_detector import RelationshipDetector
from app.schemas.relationship import JoinPreviewRequest


class TestCrossDatasetComprehensiveVerification(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="test_cross_dataset_")
        cls.dir_path = Path(cls.temp_dir)

        # Database setup
        cls.db_path = cls.dir_path / "test_cross_dataset.db"
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", echo=False)
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        cls.db = cls.SessionLocal()

        # Users
        cls.user1 = User(
            email="analyst_test@example.com",
            full_name="Verification Analyst",
            hashed_password="pw_hash_test",
            is_active=True,
        )
        cls.user2 = User(
            email="isolated_tenant@example.com",
            full_name="Other Tenant",
            hashed_password="pw_hash_test_2",
            is_active=True,
        )
        cls.db.add_all([cls.user1, cls.user2])
        cls.db.commit()

        # Dataset 1: verify_customers.csv
        cls.df_customers = pd.DataFrame({
            "customer_id": [1, 2, 3, 4, 5],
            "customer_name": ["Alice", "Bob", "Charlie", "Diana", "Evan"],
            "city": ["New York", "Chicago", "Houston", "Phoenix", "Dallas"],
            "age": [28, 35, 42, 31, 55],
            "credit_score": [720, 680, 810, 650, 790],
        })
        cls.path_customers = cls.dir_path / "verify_customers.csv"
        cls.df_customers.to_csv(cls.path_customers, index=False)

        cls.ds_customers = Dataset(
            user_id=cls.user1.id,
            filename="verify_customers.csv",
            stored_filename="stored_verify_customers.csv",
            file_path=str(cls.path_customers),
            file_type="csv",
            file_size_bytes=cls.path_customers.stat().st_size,
            rows=5,
            columns=5,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        # Dataset 2: verify_orders.csv
        # Customer 1 has 2 orders (101, 102)
        # Customer 2 has 1 order (103)
        # Customer 3 has 1 order (104)
        # Customer 4 has 2 orders (105, 106)
        # Customer 5 has 0 orders
        # Order 107 has customer_id 999 (orphan order)
        cls.df_orders = pd.DataFrame({
            "order_id": [101, 102, 103, 104, 105, 106, 107],
            "customer_id": [1, 1, 2, 3, 4, 4, 999],
            "order_amount": [150.0, 250.0, 100.0, 300.0, 200.0, 400.0, 50.0],
            "city": ["New York", "New York", "Chicago", "Houston", "Phoenix", "Phoenix", "Dallas"],
            "age": [28, 28, 35, 42, 31, 31, 55],
        })
        cls.path_orders = cls.dir_path / "verify_orders.csv"
        cls.df_orders.to_csv(cls.path_orders, index=False)

        cls.ds_orders = Dataset(
            user_id=cls.user1.id,
            filename="verify_orders.csv",
            stored_filename="stored_verify_orders.csv",
            file_path=str(cls.path_orders),
            file_type="csv",
            file_size_bytes=cls.path_orders.stat().st_size,
            rows=7,
            columns=5,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        # Dataset 3: verify_customers_renamed_mismatched.csv
        cls.df_mismatched = pd.DataFrame({
            "cust_id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Evan"],
            "city": ["New York", "Chicago", "Houston", "Phoenix", "Dallas"],
            "age": ["28y", "35y", "42y", "31y", "55y"],  # String type mismatch with age in Dataset 1!
            "membership_tier": ["Gold", "Silver", "Platinum", "Bronze", "Gold"],
        })
        cls.path_mismatched = cls.dir_path / "verify_customers_renamed_mismatched.csv"
        cls.df_mismatched.to_csv(cls.path_mismatched, index=False)

        cls.ds_mismatched = Dataset(
            user_id=cls.user1.id,
            filename="verify_customers_renamed_mismatched.csv",
            stored_filename="stored_verify_customers_renamed_mismatched.csv",
            file_path=str(cls.path_mismatched),
            file_type="csv",
            file_size_bytes=cls.path_mismatched.stat().st_size,
            rows=5,
            columns=5,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        # Isolation test datasets (similar names, distinct numbers)
        cls.df_iso1 = pd.DataFrame({
            "account_id": [10, 20, 30],
            "balance": [1000.0, 2000.0, 3000.0],
            "dept": ["Finance", "Finance", "Legal"],
        })
        cls.path_iso1 = cls.dir_path / "financial_q1_2026.csv"
        cls.df_iso1.to_csv(cls.path_iso1, index=False)
        cls.ds_iso1 = Dataset(
            user_id=cls.user1.id,
            filename="financial_q1_2026.csv",
            stored_filename="stored_financial_q1_2026.csv",
            file_path=str(cls.path_iso1),
            file_type="csv",
            file_size_bytes=cls.path_iso1.stat().st_size,
            rows=3,
            columns=3,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        cls.df_iso2 = pd.DataFrame({
            "account_id": [10, 20, 30],
            "balance": [9999.0, 8888.0, 7777.0],
            "dept": ["Marketing", "Sales", "Operations"],
        })
        cls.path_iso2 = cls.dir_path / "financial_q1_2026_v2.csv"
        cls.df_iso2.to_csv(cls.path_iso2, index=False)
        cls.ds_iso2 = Dataset(
            user_id=cls.user1.id,
            filename="financial_q1_2026_v2.csv",
            stored_filename="stored_financial_q1_2026_v2.csv",
            file_path=str(cls.path_iso2),
            file_type="csv",
            file_size_bytes=cls.path_iso2.stat().st_size,
            rows=3,
            columns=3,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        # Tenant 2 dataset for cross-tenant isolation
        cls.df_tenant2 = pd.DataFrame({
            "secret_id": [991, 992],
            "secret_val": ["TopSecretA", "TopSecretB"],
        })
        cls.path_tenant2 = cls.dir_path / "tenant2_confidential.csv"
        cls.df_tenant2.to_csv(cls.path_tenant2, index=False)
        cls.ds_tenant2 = Dataset(
            user_id=cls.user2.id,
            filename="tenant2_confidential.csv",
            stored_filename="stored_tenant2_confidential.csv",
            file_path=str(cls.path_tenant2),
            file_type="csv",
            file_size_bytes=cls.path_tenant2.stat().st_size,
            rows=2,
            columns=2,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        cls.db.add_all([
            cls.ds_customers,
            cls.ds_orders,
            cls.ds_mismatched,
            cls.ds_iso1,
            cls.ds_iso2,
            cls.ds_tenant2,
        ])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.close()
            cls.engine.dispose()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. CROSS-DATASET COMPARISONS
    # =========================================================================
    def test_01_cross_dataset_comparison_metrics(self):
        """Verify row counts, combined overview, and independent aggregates per dataset ID."""
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds_customers.id, self.ds_orders.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.total_selected, 2)
        self.assertEqual(resp.total_successful, 2)

        # 1. Combined Overview Verification
        comb = resp.combined_overview
        self.assertIsNotNone(comb)
        self.assertEqual(comb.total_datasets, 2)
        # Expected rows = 5 (customers) + 7 (orders) = 12
        self.assertEqual(comb.total_rows, 12)
        # Total cells = 5*5 + 7*5 = 25 + 35 = 60
        self.assertEqual(comb.total_cells, 60)
        # Distinct column names: customer_id, customer_name, city, age, credit_score, order_id, order_amount = 7
        self.assertEqual(comb.distinct_columns, 7)

        # 2. Individual Profiles indexed strictly by dataset ID
        self.assertIn(self.ds_customers.id, resp.individual_profiles)
        self.assertIn(self.ds_orders.id, resp.individual_profiles)

        p_cust = resp.individual_profiles[self.ds_customers.id]
        p_ord = resp.individual_profiles[self.ds_orders.id]

        self.assertEqual(p_cust.dataset_info.rows, 5)
        self.assertEqual(p_cust.dataset_info.columns, 5)
        self.assertEqual(p_ord.dataset_info.rows, 7)
        self.assertEqual(p_ord.dataset_info.columns, 5)

        # 3. Independent Numerical Aggregates
        # Customers credit_score: sum = 3650.0, mean = 730.0
        cust_credit_col = next(c for c in p_cust.columns if c.name == "credit_score")
        self.assertAlmostEqual(cust_credit_col.numeric_stats.mean, 730.0, places=2)
        self.assertAlmostEqual(cust_credit_col.numeric_stats.min, 650.0, places=2)
        self.assertAlmostEqual(cust_credit_col.numeric_stats.max, 810.0, places=2)

        # Orders order_amount: sum = 1450.0, mean = 207.14
        ord_amount_col = next(c for c in p_ord.columns if c.name == "order_amount")
        self.assertAlmostEqual(ord_amount_col.numeric_stats.mean, 207.14, places=2)
        self.assertAlmostEqual(ord_amount_col.numeric_stats.min, 50.0, places=2)
        self.assertAlmostEqual(ord_amount_col.numeric_stats.max, 400.0, places=2)

        # Ensure no aggregate bleed between datasets
        self.assertNotIn("order_amount", [c.name for c in p_cust.columns])
        self.assertNotIn("credit_score", [c.name for c in p_ord.columns])

    # =========================================================================
    # 2. SCHEMA MATCHING
    # =========================================================================
    def test_02_schema_matching_and_type_incompatibilities(self):
        """Verify identical columns, type incompatibilities, and extra/missing columns."""
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds_customers.id, self.ds_mismatched.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        comp = resp.comparison
        self.assertIsNotNone(comp)

        # 1. Shared columns (present in both)
        # 'city' and 'age' share identical column names
        self.assertIn("city", comp.shared_columns)
        self.assertIn("age", comp.shared_columns)

        # 2. Type Mismatches
        # 'age' in customers is int64, but in mismatched it is string ("28y")
        mismatches = comp.type_mismatches
        age_mismatch = next((m for m in mismatches if m.get("column") == "age"), None)
        self.assertIsNotNone(age_mismatch, "Type mismatch for column 'age' must be detected.")
        types_list = age_mismatch.get("types", [])
        # One is integer/numeric, the other is object/text
        types_str = " ".join(str(t) for t in types_list).lower()
        self.assertTrue("int" in types_str and ("obj" in types_str or "str" in types_str or "text" in types_str))

        # 3. Unique columns per dataset
        unique_map = comp.unique_columns
        cust_unique = unique_map.get("verify_customers.csv", [])
        mismatch_unique = unique_map.get("verify_customers_renamed_mismatched.csv", [])

        # credit_score, customer_id, customer_name only exist in customers
        self.assertIn("credit_score", cust_unique)
        self.assertIn("customer_id", cust_unique)
        self.assertIn("customer_name", cust_unique)

        # membership_tier, cust_id, name only exist in mismatched
        self.assertIn("membership_tier", mismatch_unique)
        self.assertIn("cust_id", mismatch_unique)
        self.assertIn("name", mismatch_unique)

    # =========================================================================
    # 3. RELATIONSHIP DETECTION & NON-RELATIONAL COLUMN SAFEGUARDS
    # =========================================================================
    def test_03_relationship_detection_and_safeguards(self):
        """Verify PK/FK detection on customer_id, cardinality (1:N), and rejection of City/Age."""
        rel_resp = RelationshipService.detect_relationships([self.ds_customers, self.ds_orders])

        self.assertGreaterEqual(rel_resp.total_detected, 1)
        rels = rel_resp.relationships

        # 1. Primary relationship must be customer_id
        primary_rel = next(
            (r for r in rels if r.source_column == "customer_id" and r.target_column == "customer_id"),
            None
        )
        self.assertIsNotNone(primary_rel, "customer_id relationship must be detected between customers and orders.")
        
        # Cardinality: One-to-Many or Many-to-One
        clean_rel_type = primary_rel.relationship_type.upper().replace("-", "_")
        self.assertIn(clean_rel_type, ["ONE_TO_MANY", "MANY_TO_ONE"])
        # Confidence score must be high (>= 70 out of 100 or >= 0.70)
        self.assertGreaterEqual(primary_rel.confidence_score, 0.70)

        # 2. Rejection of Non-Relational Attributes (City and Age)
        # Even though City and Age have identical values in both files, they MUST NOT be detected as join keys!
        city_rel = next((r for r in rels if r.source_column == "city" or r.target_column == "city"), None)
        self.assertIsNone(city_rel, "Column 'city' must NOT be detected as an entity relationship key.")

        age_rel = next((r for r in rels if r.source_column == "age" or r.target_column == "age"), None)
        self.assertIsNone(age_rel, "Column 'age' must NOT be detected as an entity relationship key.")

        # 3. Direct verification of RelationshipDetector safeguard rules
        self.assertIn("city", RelationshipDetector.NON_RELATIONAL_ATTRIBUTES)
        self.assertIn("age", RelationshipDetector.NON_RELATIONAL_ATTRIBUTES)

    # =========================================================================
    # 4. COMBINED ANALYSIS & SAFE JOINS (MATHEMATICAL VERIFICATION)
    # =========================================================================
    def test_04_combined_analysis_join_preview(self):
        """Verify inner join and left join row counts, aggregates, and absence of Cartesian explosion."""
        # 1. Inner Join
        inner_preview = RelationshipService.preview_join(
            left_dataset=self.ds_customers,
            left_column="customer_id",
            right_dataset=self.ds_orders,
            right_column="customer_id",
            join_type="INNER",
            limit=50,
        )

        self.assertEqual(inner_preview.join_type.upper(), "INNER")
        # Expected Row Count:
        # Cust 1 (2 orders) + Cust 2 (1 order) + Cust 3 (1 order) + Cust 4 (2 orders) = 6 rows
        # Cust 5 has 0 orders -> excluded. Order 107 (cust 999) -> excluded.
        self.assertEqual(inner_preview.estimated_resulting_rows, 6)
        self.assertEqual(len(inner_preview.sample_rows), 6)

        # Verify exact joined aggregates from sample rows
        joined_amounts = [float(r["order_amount"]) for r in inner_preview.sample_rows if "order_amount" in r]
        self.assertEqual(len(joined_amounts), 6)
        # Total sum of amounts for joined customers (101, 102, 103, 104, 105, 106)
        # 150 + 250 + 100 + 300 + 200 + 400 = 1400.0 (Order 107 of 50.0 excluded!)
        self.assertAlmostEqual(sum(joined_amounts), 1400.0, places=2)

        # 2. Left Join
        left_preview = RelationshipService.preview_join(
            left_dataset=self.ds_customers,
            left_column="customer_id",
            right_dataset=self.ds_orders,
            right_column="customer_id",
            join_type="LEFT",
            limit=50,
        )

        # In Left Join, Customer 5 is retained with null order fields!
        # Total rows = 6 (matched orders) + 1 (Customer 5 with NULL order) = 7 rows
        self.assertEqual(left_preview.estimated_resulting_rows, 7)
        self.assertEqual(len(left_preview.sample_rows), 7)

        # Verify Customer 5 has null order_id in left join
        cust5_row = next(r for r in left_preview.sample_rows if r.get("customer_name") == "Evan")
        self.assertTrue(pd.isna(cust5_row.get("order_id")) or cust5_row.get("order_id") is None)

    # =========================================================================
    # 5. DATASET ISOLATION
    # =========================================================================
    def test_05_dataset_isolation(self):
        """Verify two datasets with similar names never cross-bleed data."""
        resp1 = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds_iso1.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        resp2 = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds_iso2.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        p1 = resp1.individual_profiles[self.ds_iso1.id]
        p2 = resp2.individual_profiles[self.ds_iso2.id]

        bal1_col = next(c for c in p1.columns if c.name == "balance")
        bal2_col = next(c for c in p2.columns if c.name == "balance")

        # Dataset 1 balance mean = (1000 + 2000 + 3000)/3 = 2000.0
        self.assertAlmostEqual(bal1_col.numeric_stats.mean, 2000.0, places=2)
        # Dataset 2 balance mean = (9999 + 8888 + 7777)/3 = 8888.0
        self.assertAlmostEqual(bal2_col.numeric_stats.mean, 8888.0, places=2)

        # Strictly no data bleeding
        self.assertNotEqual(bal1_col.numeric_stats.mean, bal2_col.numeric_stats.mean)

        dept1_col = next(c for c in p1.columns if c.name == "dept")
        dept2_col = next(c for c in p2.columns if c.name == "dept")
        top_depts1 = {v.value for v in dept1_col.categorical_stats.top_values}
        top_depts2 = {v.value for v in dept2_col.categorical_stats.top_values}
        self.assertTrue(top_depts1.issubset({"Finance", "Legal"}))
        self.assertTrue(top_depts2.issubset({"Marketing", "Sales", "Operations"}))

        # Tenant isolation: user1 cannot access tenant2 dataset
        resp_unauth = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds_tenant2.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        # Should record an error and 0 successful
        self.assertEqual(resp_unauth.total_successful, 0)
        self.assertEqual(len(resp_unauth.errors), 1)
        self.assertIn("not found or access denied", resp_unauth.errors[0].error.lower())


if __name__ == "__main__":
    unittest.main()
