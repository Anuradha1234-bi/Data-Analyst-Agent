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

    def test_13_exact_csvs_datasets_52_and_53(self):
        """13. Exact CSV regression test on Datasets 52 and 53.

        Validates that only customer_id and email are discovered, customer_id is recommended,
        duplicate-key multiplication is flagged, and inner/left join row counts are exactly 52 and 48.
        """
        csv_52_path = os.path.join(ROOT_DIR, "uploads", "user_20", "b2512faa23e048459e0ac00264334885_data_analyst_50_rows.csv")
        csv_53_path = os.path.join(ROOT_DIR, "uploads", "user_20", "36b8c7ba3bda46658906d8f7b9ea256d_customers_quality_test.csv")

        if not (os.path.exists(csv_52_path) and os.path.exists(csv_53_path)):
            self.skipTest("Dataset 52 or 53 CSV files not found on filesystem")

        df52 = pd.read_csv(csv_52_path)
        df53 = pd.read_csv(csv_53_path)

        rels = RelationshipDetector.detect_all_relationships({
            "data_analyst_50_rows.csv": df52,
            "customers_quality_test.csv": df53,
        })

        # Exactly 2 genuine relationships: customer_id and email
        self.assertEqual(len(rels), 2)
        cols_detected = {r.source_column for r in rels}
        self.assertEqual(cols_detected, {"customer_id", "email"})

        # False positive non-relational columns must NEVER be detected
        for rejected_col in ["city", "age", "signup_date", "annual_income_inr", "customer_name"]:
            self.assertNotIn(rejected_col, cols_detected)

        # customer_id must be the recommended primary relationship
        cid_rel = [r for r in rels if r.source_column == "customer_id"][0]
        self.assertTrue(cid_rel.is_recommended)
        self.assertFalse(cid_rel.is_candidate)
        self.assertEqual(cid_rel.cardinality_symbol, "M:N")
        self.assertFalse(cid_rel.safe_for_join)
        self.assertEqual(cid_rel.estimated_inner_join_rows, 52)
        self.assertEqual(cid_rel.estimated_left_join_rows, 52)
        self.assertEqual(cid_rel.join_expansion_factor, 1.04)
        self.assertGreaterEqual(cid_rel.confidence_score, 85.0)

        # email must be the secondary candidate relationship
        email_rel = [r for r in rels if r.source_column == "email"][0]
        self.assertFalse(email_rel.is_recommended)
        self.assertTrue(email_rel.is_candidate)
        self.assertEqual(email_rel.cardinality_symbol, "M:N")
        self.assertFalse(email_rel.safe_for_join)
        self.assertEqual(email_rel.estimated_inner_join_rows, 48)
        self.assertEqual(email_rel.estimated_left_join_rows, 51)
        self.assertGreaterEqual(email_rel.confidence_score, 80.0)

    def test_14_non_relational_attributes_rejection(self):
        """14. Low-cardinality city, age, signup_date, and income false positive rejection."""
        df_a = pd.DataFrame({
            "city": ["Mumbai", "Pune", "Delhi", "Bengaluru"],
            "age": [25, 30, 35, 40],
            "signup_date": ["2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01"],
            "annual_income_inr": [500000, 600000, 700000, 800000],
            "customer_name": ["Alice", "Bob", "Charlie", "David"],
        })
        df_b = pd.DataFrame({
            "city": ["Mumbai", "Pune", "Delhi", "Bengaluru"],
            "age": [25, 30, 35, 40],
            "signup_date": ["2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01"],
            "annual_income_inr": [500000, 600000, 700000, 800000],
            "customer_name": ["Alice", "Bob", "Charlie", "David"],
        })

        rels = RelationshipDetector.detect_all_relationships({
            "table_a.csv": df_a,
            "table_b.csv": df_b,
        })

        # All columns are non-relational attributes; none should be promoted to join keys
        self.assertEqual(len(rels), 0)

    def test_15_schema_confidence_and_compatibility_fields(self):
        """15. Schema confidence serialization, no NaN%, and compatibility fields."""
        item = RelationshipItem(
            id="52:customer_id:53:customer_id",
            source_dataset_id=52,
            source_dataset_name="data_analyst_50_rows.csv",
            source_column="customer_id",
            source_dtype="object",
            source_unique_count=49,
            source_null_count=0,
            source_null_pct=0.0,
            source_is_pk_candidate=False,
            source_is_fk_candidate=False,
            target_dataset_id=53,
            target_dataset_name="customers_quality_test.csv",
            target_column="customer_id",
            target_dtype="object",
            target_unique_count=118,
            target_null_count=0,
            target_null_pct=0.0,
            target_is_pk_candidate=False,
            target_is_fk_candidate=False,
            data_type_compatible=True,
            matching_values_count=49,
            value_overlap_pct=100.0,
            relationship_type="Many-to-Many",
            confidence="MEDIUM",
            confidence_score=90.0,
            confidence_label="Possible Relationship (Minor Duplication)",
            confidence_reasons=["High key overlap (100.0%) with minor duplicate keys (52 rows estimated)"],
            warning_messages=["Many-to-Many warning: Duplicate key values exist in both datasets (1 in source, 2 in target)."],
            cardinality="Many-to-Many",
            cardinality_symbol="M:N",
            direction="data_analyst_50_rows.customer_id <-> customers_quality_test.customer_id",
            cardinality_explanation="The join key repeats in both datasets (1 duplicate(s) in source, 2 in target).",
            safe_for_join=False,
            is_candidate=False,
            is_recommended=True,
            # Compatibility aliases
            source_dataset="data_analyst_50_rows.csv",
            target_dataset="customers_quality_test.csv",
            source_unique=False,
            target_unique=False,
            overlap_score=100.0,
            confidence_pct=90.0,
            estimated_inner_join_rows=52,
            estimated_left_join_rows=52,
            join_expansion_factor=1.04,
        )

        d = item.model_dump()
        self.assertEqual(d["confidence_score"], 90.0)
        self.assertFalse(np.isnan(d["confidence_score"]))
        self.assertEqual(d["source_dataset"], "data_analyst_50_rows.csv")
        self.assertEqual(d["target_dataset"], "customers_quality_test.csv")
        self.assertEqual(d["overlap_score"], 100.0)
        self.assertEqual(d["estimated_inner_join_rows"], 52)
        self.assertEqual(d["estimated_left_join_rows"], 52)
        self.assertEqual(d["join_expansion_factor"], 1.04)

    def test_16_type_mismatch_handling(self):
        """16. Incompatible types are safely rejected."""
        df_dates = pd.DataFrame({"event_id": pd.to_datetime(["2023-01-01", "2023-01-02"])})
        df_bools = pd.DataFrame({"event_id": [True, False]})

        compat, reason, _, _ = RelationshipDetector._check_type_compatibility(
            df_dates["event_id"], df_bools["event_id"]
        )
        self.assertFalse(compat)

    def test_17_case_and_whitespace_normalization(self):
        """17. Case and whitespace normalization in key matching without mutating data."""
        df_a = pd.DataFrame({
            "account_id": [" ACC-01 ", "ACC-02", "acc-03", " ACC-04\t"],
            "balance": [100.0, 200.0, 300.0, 400.0],
        })
        df_b = pd.DataFrame({
            "account_id": ["acc-01", " ACC-02 ", "ACC-03", "acc-05"],
            "tier": ["Gold", "Silver", "Bronze", "Platinum"],
        })

        rels = RelationshipDetector.detect_all_relationships({
            "accounts_a.csv": df_a,
            "accounts_b.csv": df_b,
        })
        self.assertEqual(len(rels), 1)
        r = rels[0]
        # Should match ACC-01, ACC-02, ACC-03 (3 matching keys)
        self.assertEqual(r.matching_values_count, 3)
        self.assertEqual(r.unmatched_source_count, 1)  # acc-04
        self.assertEqual(r.unmatched_target_count, 1)  # acc-05
        # Original DataFrame contents must remain untrimmed/unaltered
        self.assertEqual(df_a["account_id"].iloc[0], " ACC-01 ")
        self.assertEqual(df_b["account_id"].iloc[1], " ACC-02 ")

    def test_18_exact_inner_and_left_join_row_counts_with_duplicates_and_nulls(self):
        """18. Exact INNER and LEFT JOIN row counts with duplicate keys and null keys on both sides."""
        # A: 6 rows. Keys: 1 (x2), 2 (x1), None (x1), 3 (x1), 4 (x1)
        # B: 7 rows. Keys: 1 (x3), 2 (x1), None (x2), 5 (x1)
        df_a = pd.DataFrame({
            "client_id": [1, 1, 2, None, 3, 4],
            "val_a": ["a1", "a2", "b", "null_a", "c", "d"],
        })
        df_b = pd.DataFrame({
            "client_id": [1, 1, 1, 2, None, None, 5],
            "val_b": ["x1", "x2", "x3", "y", "null_b1", "null_b2", "z"],
        })

        metrics = RelationshipDetector._calculate_column_metrics(
            df_a["client_id"], df_b["client_id"],
            name_a="table_a", col_a="client_id",
            name_b="table_b", col_b="client_id",
        )

        # Shared distinct non-null keys: {1, 2} -> count 2
        self.assertEqual(metrics["matching_values_count"], 2)
        # Unmatched distinct non-null keys:
        # A distinct non-null: {1, 2, 3, 4} -> 4 keys. Unmatched in A = 4 - 2 = 2 (keys 3, 4)
        self.assertEqual(metrics["unmatched_source_count"], 2)
        # B distinct non-null: {1, 2, 5} -> 3 keys. Unmatched in B = 3 - 2 = 1 (key 5)
        self.assertEqual(metrics["unmatched_target_count"], 1)

        # Duplicate counts on matching keys:
        # Key 1 in A: count 2 -> 1 duplicate
        # Key 1 in B: count 3 -> 2 duplicates
        self.assertEqual(metrics["matching_dups_source"], 1)
        self.assertEqual(metrics["matching_dups_target"], 2)

        # Expected inner join rows:
        # Key 1: 2 * 3 = 6 rows
        # Key 2: 1 * 1 = 1 row
        # Nulls never match!
        # Total inner join rows = 6 + 1 = 7 rows
        self.assertEqual(metrics["estimated_inner_join_rows"], 7)

        # Expected left join rows:
        # Inner rows = 7
        # Unmatched rows in A: row with key 3, row with key 4, row with key None -> 3 rows
        # Total left rows = 7 + 3 = 10 rows
        self.assertEqual(metrics["estimated_left_join_rows"], 10)

        # Verify against actual pandas merge (with null-key exclusion per SQL standard)
        df_a_non_null = df_a.dropna(subset=["client_id"])
        df_b_non_null = df_b.dropna(subset=["client_id"])
        actual_inner = pd.merge(df_a_non_null, df_b_non_null, on="client_id", how="inner")
        self.assertEqual(len(actual_inner), metrics["estimated_inner_join_rows"])

    def test_19_zero_matching_keys_and_empty_datasets(self):
        """19. Zero matching keys and empty dataset handling."""
        df_empty_a = pd.DataFrame({"cust_id": []})
        df_empty_b = pd.DataFrame({"cust_id": []})
        metrics_empty = RelationshipDetector._calculate_column_metrics(
            df_empty_a["cust_id"], df_empty_b["cust_id"]
        )
        self.assertEqual(metrics_empty["matching_values_count"], 0)
        self.assertEqual(metrics_empty["estimated_inner_join_rows"], 0)
        self.assertEqual(metrics_empty["estimated_left_join_rows"], 0)
        self.assertFalse(metrics_empty["safe_for_join"])

        # Completely disjoint non-empty sets
        df_x = pd.DataFrame({"user_id": [10, 20, 30]})
        df_y = pd.DataFrame({"user_id": [40, 50, 60]})
        rels = RelationshipDetector.detect_all_relationships({"x.csv": df_x, "y.csv": df_y})
        self.assertEqual(len(rels), 0)

    def test_20_schema_comparison_and_non_numeric_detection(self):
        """20. Detect non-numeric non-null values without modifying source data."""
        # Dataset 52 style: float64
        s_clean = pd.Series([50000.0, 60000.0, np.nan, 75000.0], name="annual_income_inr")
        # Dataset 53 style: object with string 'unknown'
        s_dirty = pd.Series([50000.0, "unknown", np.nan, 75000.0], name="annual_income_inr")

        # Verify dtype detection
        self.assertEqual(str(s_clean.dtype), "float64")
        self.assertEqual(str(s_dirty.dtype), "object")

        # Detect non-numeric values without mutating series
        coerced = pd.to_numeric(s_dirty, errors="coerce")
        invalid_mask = s_dirty.notna() & coerced.isna()
        invalid_values = s_dirty[invalid_mask].tolist()

        self.assertEqual(invalid_values, ["unknown"])
        # Original series unchanged
        self.assertEqual(s_dirty.iloc[1], "unknown")


if __name__ == "__main__":
    unittest.main()
