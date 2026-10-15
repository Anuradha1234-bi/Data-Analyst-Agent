"""Comprehensive automated test suite for Multi-Dataset Relationship Detection.

Validates the 12 required test scenarios:
1. One-to-One (1:1): unique keys on both datasets.
2. One-to-Many (1:N): unique keys in A and repeated keys in B.
3. Many-to-One (N:1): repeated keys in A and unique keys in B.
4. Many-to-Many (M:N): repeated matching keys on both sides with row multiplication warning.
5. Different column naming conventions (customer_id, Customer ID, CUSTOMER_ID, cust_id).
6. Matching keys with some unmatched records (partial overlap).
7. Null values and duplicate values handling.
8. Same column names but incompatible/non-overlapping values.
9. No genuine relationship.
10. Multiple relationships between the same two datasets (and best candidate recommendation).
11. Empty datasets and columns with different data types (numeric <-> string conversion).
12. API response serialization and structure.
"""

import sys
import os
import json
import unittest
import pandas as pd
import numpy as np

# Ensure root and backend are in path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

from services.relationship_detector import RelationshipDetector
from app.schemas.relationship import RelationshipItem, RelationshipDetectResponse


class TestMultiDatasetRelationships(unittest.TestCase):
    """Test suite for RelationshipDetector and relationship schemas."""

    def test_01_one_to_one(self):
        """1. One-to-One: unique keys on both datasets."""
        df_users = pd.DataFrame({
            "user_id": [1, 2, 3, 4],
            "username": ["alice", "bob", "charlie", "david"],
        })
        df_profiles = pd.DataFrame({
            "user_id": [1, 2, 3, 4],
            "bio": ["Engineer", "Designer", "Analyst", "Manager"],
        })

        rels = RelationshipDetector.detect_all_relationships({
            "users.csv": df_users,
            "profiles.csv": df_profiles,
        })

        self.assertGreaterEqual(len(rels), 1)
        r = [rel for rel in rels if rel.source_column == "user_id" or rel.target_column == "user_id"][0]
        self.assertEqual(r.relationship_type, "One-to-One")
        self.assertEqual(r.cardinality_symbol, "1:1")
        self.assertTrue(r.source_unique)
        self.assertTrue(r.target_unique)
        self.assertTrue(r.safe_for_join)
        self.assertEqual(r.matching_values_count, 4)

    def test_02_one_to_many(self):
        """2. One-to-Many: unique keys in A and repeated keys in B."""
        df_customers = pd.DataFrame({
            "customer_id": [101, 102, 103],
            "customer_name": ["Acme Corp", "Beta LLC", "Gamma Inc"],
        })
        df_orders = pd.DataFrame({
            "order_id": [1, 2, 3, 4, 5],
            "customer_id": [101, 101, 102, 103, 103],
            "amount": [150.0, 300.0, 75.0, 200.0, 450.0],
        })

        rels = RelationshipDetector.detect_all_relationships({
            "customers.csv": df_customers,
            "orders.csv": df_orders,
        })

        self.assertGreaterEqual(len(rels), 1)
        r = [rel for rel in rels if "customer_id" in rel.source_column and "customer_id" in rel.target_column][0]
        self.assertEqual(r.relationship_type, "One-to-Many")
        self.assertEqual(r.cardinality_symbol, "1:N")
        self.assertTrue(r.source_unique)
        self.assertFalse(r.target_unique)
        self.assertTrue(r.safe_for_join)
        self.assertIn("One record in Dataset A can match multiple records in Dataset B", r.cardinality_explanation)

    def test_03_many_to_one(self):
        """3. Many-to-One: repeated keys in A and unique keys in B."""
        df_orders = pd.DataFrame({
            "order_id": [1, 2, 3, 4, 5],
            "customer_id": [101, 101, 102, 103, 103],
        })
        df_customers = pd.DataFrame({
            "customer_id": [101, 102, 103],
            "name": ["Acme Corp", "Beta LLC", "Gamma Inc"],
        })

        rels = RelationshipDetector.detect_all_relationships({
            "orders.csv": df_orders,
            "customers.csv": df_customers,
        })

        self.assertGreaterEqual(len(rels), 1)
        r = [rel for rel in rels if "customer_id" in rel.source_column and "customer_id" in rel.target_column][0]
        self.assertEqual(r.relationship_type, "Many-to-One")
        self.assertEqual(r.cardinality_symbol, "N:1")
        self.assertFalse(r.source_unique)
        self.assertTrue(r.target_unique)
        self.assertTrue(r.safe_for_join)

    def test_04_many_to_many(self):
        """4. Many-to-Many: repeated matching keys on both sides."""
        df_store_inventory = pd.DataFrame({
            "product_id": [10, 10, 20, 30, 30],
            "store_code": ["S1", "S2", "S1", "S1", "S2"],
        })
        df_supplier_catalog = pd.DataFrame({
            "product_id": [10, 10, 20, 20, 30],
            "vendor_code": ["V1", "V2", "V1", "V3", "V2"],
        })

        rels = RelationshipDetector.detect_all_relationships({
            "inventory.csv": df_store_inventory,
            "suppliers.csv": df_supplier_catalog,
        })

        self.assertGreaterEqual(len(rels), 1)
        r = [rel for rel in rels if "product_id" in rel.source_column][0]
        self.assertEqual(r.relationship_type, "Many-to-Many")
        self.assertEqual(r.cardinality_symbol, "M:N")
        self.assertFalse(r.source_unique)
        self.assertFalse(r.target_unique)
        self.assertFalse(r.safe_for_join)
        # Verify row multiplication warning is included
        warning_text = " ".join(r.warning_messages)
        self.assertIn("Many-to-Many warning", warning_text)
        self.assertIn("multiply rows", warning_text)

    def test_05_column_naming_conventions(self):
        """5. Different column naming conventions (customer_id, Customer ID, CUSTOMER_ID, cust_id)."""
        df_a = pd.DataFrame({"Customer ID": [1, 2, 3], "data_a": ["x", "y", "z"]})
        df_b = pd.DataFrame({"customer_id": [1, 2, 3], "data_b": ["p", "q", "r"]})
        df_c = pd.DataFrame({"CUSTOMER_ID": [1, 2, 3], "data_c": ["m", "n", "o"]})
        df_d = pd.DataFrame({"cust_id": [1, 2, 3], "data_d": ["u", "v", "w"]})

        rels_ab = RelationshipDetector.detect_all_relationships({"a.csv": df_a, "b.csv": df_b})
        self.assertEqual(len(rels_ab), 1)
        self.assertEqual(rels_ab[0].source_column, "Customer ID")
        self.assertEqual(rels_ab[0].target_column, "customer_id")

        rels_ac = RelationshipDetector.detect_all_relationships({"a.csv": df_a, "c.csv": df_c})
        self.assertEqual(len(rels_ac), 1)
        self.assertEqual(rels_ac[0].source_column, "Customer ID")
        self.assertEqual(rels_ac[0].target_column, "CUSTOMER_ID")

        rels_bd = RelationshipDetector.detect_all_relationships({"b.csv": df_b, "d.csv": df_d})
        self.assertEqual(len(rels_bd), 1)
        self.assertEqual(rels_bd[0].source_column, "customer_id")
        self.assertEqual(rels_bd[0].target_column, "cust_id")

    def test_06_unmatched_records_partial_overlap(self):
        """6. Matching keys with some unmatched records (partial overlap)."""
        df_left = pd.DataFrame({"user_id": [1, 2, 3, 4, 5]})
        df_right = pd.DataFrame({"user_id": [3, 4, 5, 6, 7]})

        rels = RelationshipDetector.detect_all_relationships({"left.csv": df_left, "right.csv": df_right})
        self.assertEqual(len(rels), 1)
        r = rels[0]
        self.assertEqual(r.matching_values_count, 3)
        self.assertEqual(r.unmatched_source_count, 2)
        self.assertEqual(r.unmatched_target_count, 2)
        self.assertEqual(r.value_overlap_pct, 60.0)

    def test_07_null_and_duplicate_values(self):
        """7. Null values and duplicate values handling."""
        df_a = pd.DataFrame({
            "emp_id": [10, 20, None, np.nan, 30],
            "name": ["A", "B", "C", "D", "E"],
        })
        df_b = pd.DataFrame({
            "emp_id": [10, 20, 30, 40, None],
            "salary": [50000, 60000, 70000, 80000, 90000],
        })

        rels = RelationshipDetector.detect_all_relationships({"a.csv": df_a, "b.csv": df_b})
        self.assertGreaterEqual(len(rels), 1)
        r = [rel for rel in rels if "emp_id" in rel.source_column][0]
        self.assertEqual(r.matching_values_count, 3)
        self.assertEqual(r.source_null_count, 2)
        self.assertEqual(r.target_null_count, 1)
        # Check that warnings report null counts
        warning_str = " ".join(r.warning_messages)
        self.assertIn("null", warning_str)

    def test_08_same_names_incompatible_values(self):
        """8. Same column names but incompatible/non-overlapping values."""
        df_alpha = pd.DataFrame({"code": ["A100", "B200", "C300"]})
        df_beta = pd.DataFrame({"code": ["X999", "Y888", "Z777"]})

        rels = RelationshipDetector.detect_all_relationships({"alpha.csv": df_alpha, "beta.csv": df_beta})
        self.assertEqual(len(rels), 0)

    def test_09_no_genuine_relationship(self):
        """9. No genuine relationship."""
        df_weather = pd.DataFrame({
            "city": ["Paris", "Tokyo", "London"],
            "temperature": [18.5, 22.0, 15.2],
        })
        df_stock = pd.DataFrame({
            "ticker": ["AAPL", "GOOGL", "MSFT"],
            "price": [175.0, 140.0, 380.0],
        })

        rels = RelationshipDetector.detect_all_relationships({"weather.csv": df_weather, "stocks.csv": df_stock})
        self.assertEqual(len(rels), 0)

    def test_10_multiple_relationships(self):
        """10. Multiple relationships between the same pair of datasets."""
        df_employees = pd.DataFrame({
            "emp_id": [1, 2, 3],
            "email": ["e1@company.com", "e2@company.com", "e3@company.com"],
            "name": ["Alice", "Bob", "Charlie"],
        })
        df_access_cards = pd.DataFrame({
            "emp_id": [1, 2, 3],
            "email": ["e1@company.com", "e2@company.com", "e3@company.com"],
            "card_num": ["C001", "C002", "C003"],
        })

        rels = RelationshipDetector.detect_all_relationships({
            "employees.csv": df_employees,
            "access_cards.csv": df_access_cards,
        })

        # Should discover both emp_id and email
        self.assertGreaterEqual(len(rels), 2)
        cols_matched = {r.source_column for r in rels}
        self.assertIn("emp_id", cols_matched)
        self.assertIn("email", cols_matched)
        # Verify ambiguity handling: all marked ambiguous and exactly one marked recommended
        for r in rels:
            self.assertTrue(r.is_ambiguous)
        recommended = [r for r in rels if r.is_recommended]
        self.assertEqual(len(recommended), 1)

    def test_11_empty_datasets_and_type_conversion(self):
        """11. Empty datasets and columns with different data types (numeric <-> string)."""
        df_empty = pd.DataFrame({"id": [], "val": []})
        df_valid = pd.DataFrame({"id": [1, 2], "val": ["a", "b"]})

        rels_empty = RelationshipDetector.detect_all_relationships({"empty.csv": df_empty, "valid.csv": df_valid})
        self.assertEqual(len(rels_empty), 0)

        # Cross-type numeric <-> string
        df_num = pd.DataFrame({"item_id": [101, 102, 103], "name": ["Pen", "Pencil", "Eraser"]})
        df_str = pd.DataFrame({"item_id": ["101", "102", "103"], "price": [1.5, 0.8, 0.5]})

        rels_types = RelationshipDetector.detect_all_relationships({"num.csv": df_num, "str.csv": df_str})
        self.assertGreaterEqual(len(rels_types), 1)
        r = rels_types[0]
        self.assertEqual(r.matching_values_count, 3)
        self.assertEqual(r.relationship_type, "One-to-One")

    def test_12_schema_and_api_serialization(self):
        """12. Schema and API response serialization."""
        item = RelationshipItem(
            id="1:customer_id:2:customer_id",
            source_dataset_id=1,
            source_dataset_name="customers.csv",
            source_column="customer_id",
            source_dtype="int64",
            source_unique_count=100,
            source_null_count=0,
            source_null_pct=0.0,
            source_is_pk_candidate=True,
            source_is_fk_candidate=False,
            target_dataset_id=2,
            target_dataset_name="orders.csv",
            target_column="customer_id",
            target_dtype="int64",
            target_unique_count=100,
            target_null_count=5,
            target_null_pct=1.2,
            target_is_pk_candidate=False,
            target_is_fk_candidate=True,
            data_type_compatible=True,
            matching_values_count=100,
            value_overlap_pct=100.0,
            relationship_type="One-to-Many",
            confidence="HIGH",
            confidence_score=95.0,
            confidence_label="Strong Relationship",
            confidence_reasons=["Matching key with verified Primary Key to Foreign Key structure"],
            warning_messages=[],
            cardinality="One-to-Many",
            cardinality_symbol="1:N",
            direction="customers.csv.customer_id -> orders.csv.customer_id",
            cardinality_explanation="One record in Dataset A can match multiple records in Dataset B.",
            safe_for_join=True,
        )

        resp = RelationshipDetectResponse(
            total_detected=1,
            analyzed_datasets_count=2,
            relationships=[item],
            scan_summary={"datasets_analyzed": 2, "strong_relationships": 1},
            message="Discovered 1 potential relationship.",
        )

        # JSON round-trip test
        json_data = resp.model_dump_json()
        loaded = json.loads(json_data)
        self.assertEqual(loaded["total_detected"], 1)
        self.assertEqual(loaded["relationships"][0]["cardinality_symbol"], "1:N")
        self.assertTrue(loaded["relationships"][0]["safe_for_join"])
        self.assertEqual(loaded["scan_summary"]["strong_relationships"], 1)


if __name__ == "__main__":
    unittest.main()
