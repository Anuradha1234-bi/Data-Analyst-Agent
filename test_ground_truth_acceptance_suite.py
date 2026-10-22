"""Comprehensive Ground-Truth Acceptance Test Suite for AI Data Analyst Agent.
Validates the complete 10-phase analysis lifecycle against deterministic ground truth:

1. Dataset upload & validation.
2. Data profiling.
3. Data quality assessment & quality score.
4. Data cleaning recommendations & execution.
5. Post-cleaning profiling.
6. Recalculated post-cleaning quality score.
7. Before-and-after comparison.
8. Unified analysis summary and reports.
9. Multiple-dataset analysis & tenant isolation.
10. Schema matching, compatible relationship detection, and validated join analysis.

Calculates exact correctness rate:
Correctness rate = (number of correctly verified test assertions / total eligible test assertions) * 100
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

# Set project paths
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.dataset import Dataset
from app.schemas.cleaning import CleaningOperationsRequest
from app.services.profiling_service import ProfilingService
from app.services.quality_service import DataQualityService
from app.services.cleaning_service import DataCleaningService
from app.services.multi_dataset_service import MultiDatasetAnalysisService
from app.services.relationship_service import RelationshipService
from services.relationship_detector import RelationshipDetector


class GroundTruthAcceptanceSuite(unittest.TestCase):
    """Predefined Ground-Truth Acceptance Test Suite across all 10 lifecycle phases."""

    # Track assertions globally across all tests in this suite
    total_assertions = 0
    passed_assertions = 0
    failures_log = []

    def check(self, condition: bool, msg: str):
        """Helper to record individual assertion outcomes for exact correctness rate."""
        GroundTruthAcceptanceSuite.total_assertions += 1
        if condition:
            GroundTruthAcceptanceSuite.passed_assertions += 1
        else:
            GroundTruthAcceptanceSuite.failures_log.append(msg)
            self.fail(msg)

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="gt_acceptance_")
        cls.dir_path = Path(cls.temp_dir)

        # Isolated SQLite database
        cls.db_path = cls.dir_path / "acceptance_test.db"
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", echo=False)
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        cls.db = cls.SessionLocal()

        # Users
        cls.user1 = User(
            email="lead_analyst@enterprise.ai",
            full_name="Lead Analyst",
            hashed_password="hash_pw_1",
            is_active=True,
        )
        cls.user2 = User(
            email="other_tenant@enterprise.ai",
            full_name="Other Tenant",
            hashed_password="hash_pw_2",
            is_active=True,
        )
        cls.db.add_all([cls.user1, cls.user2])
        cls.db.commit()

        # =====================================================================
        # GROUND TRUTH DATASET 1: acceptance_dirty_master.csv
        # 15 rows total:
        # - Row 13 is exact duplicate of Row 3 (1 duplicate row)
        # - Row 15 is completely empty (1 empty row)
        # - Missing values: customer_name (2 missing + empty row), amount (1 missing + empty row)
        # - Whitespace & lowercase in customer_name ("  Alice Smith  ", "bob jones")
        # - Casing variants in category ("Electronics", "electronics", "ELECTRONICS")
        # - Outlier in amount: 50000.0 (typical range: 80 - 400)
        # - Null-like tokens in status: "n/a", "?"
        # =====================================================================
        cls.df_dirty = pd.DataFrame({
            "txn_id": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 103, 113, np.nan],
            "customer_name": [
                "  Alice Smith  ", "bob jones", "Charlie Brown", None, "Diana Prince",
                "Evan Wright", "Fiona Gallagher", "George Clark", "Hannah Abbott", "Ian Malcolm",
                "Julia Roberts", "Kevin Bacon", "Charlie Brown", None, None
            ],
            "category": [
                "Electronics", "electronics", "ELECTRONICS", "Clothing", "Clothing",
                "Home", "Home", "Books", "Books", "Sports",
                "Sports", "Toys", "ELECTRONICS", "Toys", None
            ],
            "amount": [
                150.0, 250.0, 100.0, None, 200.0,
                400.0, 300.0, 120.0, 80.0, 50000.0,
                220.0, 180.0, 100.0, 160.0, None
            ],
            "order_date": [
                "2026-01-15", "01/20/2026", "2026/02/01", "2026-02-10", "2026-02-15",
                "2026-02-20", "2026-02-25", "2026-03-01", "2026-03-05", "2026-03-10",
                "2026-03-15", "invalid-date", "2026/02/01", "2026-03-25", None
            ],
            "status": [
                "Completed", "Completed", "Pending", "Pending", "n/a",
                "Completed", "Pending", "?", "Completed", "Completed",
                "Pending", "Completed", "Pending", "Pending", None
            ],
        })
        cls.path_dirty = cls.dir_path / "acceptance_dirty_master.csv"
        cls.df_dirty.to_csv(cls.path_dirty, index=False)

        cls.ds_dirty = Dataset(
            user_id=cls.user1.id,
            filename="acceptance_dirty_master.csv",
            stored_filename="stored_acceptance_dirty_master.csv",
            file_path=str(cls.path_dirty),
            file_type="csv",
            file_size_bytes=cls.path_dirty.stat().st_size,
            rows=15,
            columns=6,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        # =====================================================================
        # GROUND TRUTH DATASETS 2 & 3: master_customers.csv & master_orders.csv
        # Customers: 5 rows (cust_id 1..5)
        # Orders: 7 rows (cust_id 1 has 2 orders, 2 has 1, 3 has 1, 4 has 2, 5 has 0; 999 is orphan)
        # Inner Join math: 6 rows, sum = 1450.0 (orphan 75.0 excluded)
        # Left Join math: 7 rows (Evan preserved with order_id=null)
        # City overlaps: New York, Chicago, Houston, Phoenix, Dallas
        # =====================================================================
        cls.df_cust = pd.DataFrame({
            "cust_id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Evan"],
            "city": ["New York", "Chicago", "Houston", "Phoenix", "Dallas"],
            "age": [28, 35, 42, 31, 55],
        })
        cls.path_cust = cls.dir_path / "master_customers.csv"
        cls.df_cust.to_csv(cls.path_cust, index=False)
        cls.ds_cust = Dataset(
            user_id=cls.user1.id,
            filename="master_customers.csv",
            stored_filename="stored_master_customers.csv",
            file_path=str(cls.path_cust),
            file_type="csv",
            file_size_bytes=cls.path_cust.stat().st_size,
            rows=5,
            columns=4,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        cls.df_ord = pd.DataFrame({
            "order_id": [1001, 1002, 1003, 1004, 1005, 1006, 1007],
            "cust_id": [1, 1, 2, 3, 4, 4, 999],
            "order_amount": [100.0, 200.0, 150.0, 300.0, 250.0, 450.0, 75.0],
            "city": ["New York", "New York", "Chicago", "Houston", "Phoenix", "Phoenix", "Dallas"],
        })
        cls.path_ord = cls.dir_path / "master_orders.csv"
        cls.df_ord.to_csv(cls.path_ord, index=False)
        cls.ds_ord = Dataset(
            user_id=cls.user1.id,
            filename="master_orders.csv",
            stored_filename="stored_master_orders.csv",
            file_path=str(cls.path_ord),
            file_type="csv",
            file_size_bytes=cls.path_ord.stat().st_size,
            rows=7,
            columns=4,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        # =====================================================================
        # GROUND TRUTH DATASET 4: Identical content, different filename
        # =====================================================================
        cls.path_ident = cls.dir_path / "master_customers_backup.csv"
        cls.df_cust.to_csv(cls.path_ident, index=False)
        cls.ds_ident = Dataset(
            user_id=cls.user1.id,
            filename="master_customers_backup.csv",
            stored_filename="stored_master_customers_backup.csv",
            file_path=str(cls.path_ident),
            file_type="csv",
            file_size_bytes=cls.path_ident.stat().st_size,
            rows=5,
            columns=4,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        # =====================================================================
        # GROUND TRUTH DATASET 5: Tenant 2 Private Dataset (Security Isolation)
        # =====================================================================
        cls.path_t2 = cls.dir_path / "tenant2_private.csv"
        pd.DataFrame({"secret_code": [901, 902], "balance": [50000, 75000]}).to_csv(cls.path_t2, index=False)
        cls.ds_t2 = Dataset(
            user_id=cls.user2.id,
            filename="tenant2_private.csv",
            stored_filename="stored_tenant2_private.csv",
            file_path=str(cls.path_t2),
            file_type="csv",
            file_size_bytes=cls.path_t2.stat().st_size,
            rows=2,
            columns=2,
            has_cleaned=False,
            cleaned_file_path=None,
        )

        cls.db.add_all([
            cls.ds_dirty,
            cls.ds_cust,
            cls.ds_ord,
            cls.ds_ident,
            cls.ds_t2,
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
    # PHASE 1: DATASET UPLOAD & VALIDATION (10 Assertions)
    # =========================================================================
    def test_01_upload_and_validation(self):
        """Phase 1: Validate file storage integrity, row/col counts, and file existence."""
        self.check(self.path_dirty.exists(), "Original dirty dataset file must exist on disk.")
        self.check(self.ds_dirty.rows == 15, f"Expected 15 rows registered in DB, got {self.ds_dirty.rows}")
        self.check(self.ds_dirty.columns == 6, f"Expected 6 columns registered in DB, got {self.ds_dirty.columns}")
        self.check(self.ds_dirty.user_id == self.user1.id, "Dataset must belong to user1.")

        # Customer & Order datasets
        self.check(self.path_cust.exists(), "Customer dataset file must exist.")
        self.check(self.ds_cust.rows == 5, f"Expected 5 customer rows, got {self.ds_cust.rows}")
        self.check(self.path_ord.exists(), "Order dataset file must exist.")
        self.check(self.ds_ord.rows == 7, f"Expected 7 order rows, got {self.ds_ord.rows}")

        # Identical content dataset has separate ID
        self.check(self.ds_ident.id != self.ds_cust.id, "Duplicate file contents must have distinct dataset IDs.")
        self.check(self.ds_ident.filename == "master_customers_backup.csv", "Filename preserved accurately.")

    # =========================================================================
    # PHASE 2: DATA PROFILING (12 Assertions)
    # =========================================================================
    def test_02_data_profiling(self):
        """Phase 2: Validate statistical profiling, data types, and null counts."""
        profile = ProfilingService.get_dataset_profile(self.ds_dirty)
        self.check(profile is not None, "Profile response must not be None.")
        self.check(profile.dataset_info.rows == 15, f"Profile row count expected 15, got {profile.dataset_info.rows}")
        self.check(profile.dataset_info.columns == 6, f"Profile column count expected 6, got {profile.dataset_info.columns}")

        cols_map = {c.name: c for c in profile.columns}
        self.check("amount" in cols_map, "Column 'amount' must be profiled.")
        amt_col = cols_map["amount"]
        self.check(amt_col.data_type.lower().startswith(("float", "num")), f"'amount' type should be numeric, got {amt_col.data_type}")
        self.check(amt_col.missing_count == 2, f"'amount' expected 2 missing cells, got {amt_col.missing_count}")
        self.check(amt_col.numeric_stats is not None, "'amount' must have numeric stats.")
        self.check(amt_col.numeric_stats.max == 50000.0, f"'amount' max expected 50000.0, got {amt_col.numeric_stats.max}")

        # Category profiling
        self.check("category" in cols_map, "Column 'category' must be profiled.")
        cat_col = cols_map["category"]
        self.check(cat_col.missing_count == 1, f"'category' expected 1 missing cell, got {cat_col.missing_count}")
        self.check(cat_col.categorical_stats is not None, "'category' must have categorical stats.")
        self.check(cat_col.categorical_stats.unique_count >= 5, f"'category' unique values expected >= 5, got {cat_col.categorical_stats.unique_count}")

    # =========================================================================
    # PHASE 3: DATA QUALITY ASSESSMENT & INITIAL SCORE (12 Assertions)
    # =========================================================================
    def test_03_data_quality_assessment(self):
        """Phase 3: Validate quality diagnostics, duplicate detection, and pre-cleaning score."""
        quality = DataQualityService.assess_dataset(self.ds_dirty, version="original")
        self.check(quality is not None, "Quality response must not be None.")
        self.check(quality.summary.total_rows == 15, f"Expected 15 total rows, got {quality.summary.total_rows}")
        self.check(quality.summary.total_columns == 6, f"Expected 6 total columns, got {quality.summary.total_columns}")

        # Duplicate detection (Row 13 is duplicate of Row 3)
        self.check(quality.duplicate_report.duplicate_rows >= 1, f"Expected at least 1 duplicate row, got {quality.duplicate_report.duplicate_rows}")

        # Empty row detection (Row 15 is completely empty)
        self.check(quality.empty_report.empty_rows_count >= 1, f"Expected at least 1 empty row, got {quality.empty_report.empty_rows_count}")

        # Missing cells
        self.check(quality.missing_report.total_missing_cells >= 5, f"Expected >= 5 missing cells, got {quality.missing_report.total_missing_cells}")

        # Consistency: null-like tokens ("n/a", "?")
        null_tokens = [item.token.lower() for item in quality.consistency_report.null_like_values_detected]
        self.check(any("?" in t or "n/a" in t for t in null_tokens), "Null-like tokens '?' or 'n/a' must be detected.")

        # Initial Quality Score
        initial_score = quality.summary.quality_score
        self.check(initial_score < 80.0, f"Uncleaned dirty dataset score must reflect penalties (< 80.0), got {initial_score}")
        self.check(quality.summary.overall_status in ["Poor", "Needs Attention"], f"Initial status must reflect issues, got {quality.summary.overall_status}")
        self.check(len(quality.columns) == 6, f"Expected 6 column quality evaluations, got {len(quality.columns)}")
        self.check(quality.missing_report.affected_columns_count >= 2, f"Expected >= 2 columns with missing, got {quality.missing_report.affected_columns_count}")

    # =========================================================================
    # PHASE 4: DATA CLEANING RECOMMENDATIONS & EXECUTION (15 Assertions)
    # =========================================================================
    def test_04_data_cleaning_execution(self):
        """Phase 4: Execute multi-step cleaning pipeline and record exact transformations."""
        overview = DataCleaningService.get_cleaning_overview(self.ds_dirty, self.db)
        self.check(overview is not None, "Cleaning overview must not be None.")
        self.check(overview.duplicate_rows_count >= 1, "Cleaning overview must detect duplicate rows.")
        self.check(overview.empty_rows_count >= 1, "Cleaning overview must detect empty rows.")

        # Configure targeted cleaning operations
        ops = CleaningOperationsRequest(
            remove_duplicates=True,
            remove_empty_rows=True,
            convert_blanks_to_na=True,
            standardize_column_names=True,
            text_standardizations=[
                {"column": "customer_name", "trim_whitespace": True, "collapse_spaces": True, "case_conversion": "titlecase"}
            ],
            category_normalizations=[
                {"column": "category", "mappings": {"electronics": "Electronics", "ELECTRONICS": "Electronics"}}
            ],
            missing_imputations=[
                {"column": "amount", "strategy": "median"}
            ],
            outlier_cleanings=[
                {"column": "amount", "method": "iqr", "multiplier": 1.5, "action": "cap"}
            ],
        )

        # Dry-run Preview first (Zero disk modification)
        preview = DataCleaningService.preview_cleaning(self.ds_dirty, ops)
        self.check(preview is not None, "Cleaning preview must succeed.")
        self.check(preview.rows_removed >= 2, f"Expected >= 2 rows removed (1 dup + 1 empty), got {preview.rows_removed}")
        self.check(self.ds_dirty.has_cleaned is False, "Preview must NOT modify dataset.has_cleaned.")

        # Apply Cleaning
        apply_res = DataCleaningService.apply_cleaning(self.ds_dirty, ops, self.user1, self.db)
        self.check(apply_res.success, "Cleaning apply must succeed.")
        self.check(apply_res.rows_removed >= 2, f"Applied rows removed expected >= 2, got {apply_res.rows_removed}")
        self.check(apply_res.after.total_rows == 13, f"Expected 13 rows after cleaning (15 - 1 dup - 1 empty), got {apply_res.after.total_rows}")
        self.check(apply_res.after.duplicate_rows == 0, f"Expected 0 duplicate rows after cleaning, got {apply_res.after.duplicate_rows}")
        self.check(self.ds_dirty.has_cleaned is True, "Dataset must now be flagged has_cleaned = True.")
        self.check(self.ds_dirty.cleaned_file_path is not None, "cleaned_file_path must be populated.")
        self.check(Path(self.ds_dirty.cleaned_file_path).exists(), "Cleaned CSV file must exist on disk.")
        self.check(len(apply_res.operations_performed) >= 3, "At least 3 operations must be recorded in audit log.")

    # =========================================================================
    # PHASE 5: POST-CLEANING PROFILING & IMMUTABILITY (10 Assertions)
    # =========================================================================
    def test_05_post_cleaning_profiling(self):
        """Phase 5: Independently profile cleaned artifact and verify original immutability."""
        # 1. Original file remains completely unchanged
        orig_df = pd.read_csv(self.path_dirty)
        self.check(len(orig_df) == 15, f"Original file on disk must retain 15 rows, found {len(orig_df)}")
        self.check(orig_df["amount"].max() == 50000.0, "Original file must preserve the raw 50000.0 outlier.")

        # 2. Cleaned file profiling
        cleaned_path = Path(self.ds_dirty.cleaned_file_path)
        cleaned_df = pd.read_csv(cleaned_path)
        self.check(len(cleaned_df) == 13, f"Cleaned file must have 13 rows, got {len(cleaned_df)}")
        self.check(cleaned_df.duplicated().sum() == 0, "Cleaned file must have 0 duplicate rows.")

        # Cleaned amount outlier capped
        self.check(cleaned_df["amount"].max() < 50000.0, f"Cleaned amount max must be capped (< 50000.0), got {cleaned_df['amount'].max()}")
        self.check(cleaned_df["amount"].isnull().sum() == 0, "Missing amounts must be imputed (0 nulls remaining).")

        # Cleaned text whitespace trimmed
        alice_name = cleaned_df.loc[cleaned_df["txn_id"] == 101, "customer_name"].iloc[0]
        self.check(alice_name == "Alice Smith", f"Expected trimmed titlecase 'Alice Smith', got '{alice_name}'")

        # Category standardized
        elec_values = set(cleaned_df.loc[cleaned_df["category"].str.lower() == "electronics", "category"].unique())
        self.check(elec_values == {"Electronics"}, f"Electronics casing variants must be unified to {{'Electronics'}}, got {elec_values}")
        self.check(cleaned_df["category"].nunique() <= 6, "Categorical variants consolidated.")
        self.check(len(cleaned_df.columns) == 6, f"Expected 6 columns in cleaned dataset, got {len(cleaned_df.columns)}")

    # =========================================================================
    # PHASE 6: RECALCULATED QUALITY SCORE (10 Assertions)
    # =========================================================================
    def test_06_recalculated_quality_score(self):
        """Phase 6: Verify recalculated quality metrics and score improvement."""
        q_orig = DataQualityService.assess_dataset(self.ds_dirty, version="original")
        q_clean = DataQualityService.assess_dataset(self.ds_dirty, version="cleaned")

        self.check(q_clean is not None, "Cleaned quality assessment must not be None.")
        self.check(q_clean.summary.total_rows == 13, f"Cleaned quality evaluation rows expected 13, got {q_clean.summary.total_rows}")
        self.check(q_clean.duplicate_report.duplicate_rows == 0, "Cleaned duplicates must be 0.")
        self.check(q_clean.empty_report.empty_rows_count == 0, "Cleaned empty rows must be 0.")

        score_before = q_orig.summary.quality_score
        score_after = q_clean.summary.quality_score
        self.check(score_after > score_before, f"Quality score must improve after cleaning: before={score_before}, after={score_after}")
        self.check(score_after >= 80.0, f"Cleaned dataset score must achieve good standing (>= 80.0), got {score_after}")

        # Issue counts comparison
        self.check(q_clean.summary.quality_issues_count < q_orig.summary.quality_issues_count, "Total quality issues must decrease.")
        self.check(q_clean.summary.missing_percentage < q_orig.summary.missing_percentage, "Missing percentage must decrease.")
        self.check(q_clean.summary.overall_status in ["Good", "Needs Attention"], f"Cleaned status should be Good, got {q_clean.summary.overall_status}")
        self.check(q_clean.summary.duplicate_percentage == 0.0, "Duplicate percentage must be 0.0%.")

    # =========================================================================
    # PHASE 7: BEFORE-AND-AFTER COMPARISON & VALIDATION REPORT (10 Assertions)
    # =========================================================================
    def test_07_before_after_comparison(self):
        """Phase 7: Validate 8-point validation report and cell diff tracking."""
        val_report = DataCleaningService.get_validation_report(self.ds_dirty, self.db)
        self.check(val_report is not None, "Validation report must not be None.")
        self.check(val_report.dataset_id == self.ds_dirty.id, "Validation report must match dataset ID.")
        self.check(val_report.total_issues_before >= 1, f"Validation report total_issues_before expected >= 1, got {val_report.total_issues_before}")
        self.check(val_report.total_issues_after <= val_report.total_issues_before, "Validation report total_issues_after should decrease or stay equal.")
        self.check(val_report.cleaning_score >= 80, f"Cleaning score in validation report expected >= 80, got {val_report.cleaning_score}")

        # Checks array verification
        self.check(len(val_report.checks) >= 5, f"Validation report must contain >= 5 checks, got {len(val_report.checks)}")
        dup_check = next((c for c in val_report.checks if "duplicate" in c.check_name.lower()), None)
        self.check(dup_check is not None, "Duplicate check must be present in validation report.")
        self.check(dup_check.after_value == 0 or dup_check.after_value == "0", f"Duplicate check after_value expected 0, got {dup_check.after_value}")
        self.check(dup_check.status in ["Resolved", "Good", "PASS"], f"Duplicate check status expected Resolved/Good, got {dup_check.status}")

    # =========================================================================
    # PHASE 8: UNIFIED REPORTS & TIMELINE (10 Assertions)
    # =========================================================================
    def test_08_reports_and_timeline(self):
        """Phase 8: Validate version timeline, history logging, and report exports."""
        # 1. Version timeline
        timeline = DataCleaningService.get_version_timeline(self.ds_dirty, self.db)
        self.check(len(timeline) >= 2, f"Expected at least 2 versions in timeline, got {len(timeline)}")
        v0 = timeline[0]
        self.check(v0.version == "Original", f"Initial version expected 'Original', got '{v0.version}'")
        self.check(v0.rows == 15, f"Original version rows expected 15, got {v0.rows}")
        v1 = timeline[1]
        self.check("Cleaned v" in v1.version or "v1" in v1.version.lower(), f"Version tag expected 'Cleaned v1', got '{v1.version}'")
        self.check(v1.rows == 13, f"Timeline version rows expected 13, got {v1.rows}")

        # 2. History audit log
        history = DataCleaningService.get_cleaning_history(self.ds_dirty, self.db)
        self.check(len(history) >= 1, f"Expected >= 1 cleaning history record, got {len(history)}")
        h0 = history[0]
        self.check(h0.dataset_id == self.ds_dirty.id, "History entry dataset_id must match.")
        self.check(len(h0.operations_performed) >= 1, "History entry must contain operations_performed.")

        # 3. Report Generation & Export
        report = DataCleaningService.generate_cleaning_report(self.ds_dirty, self.db)
        self.check(report is not None, "Generated cleaning report must not be None.")
        self.check(report.quality_score >= 80, f"Report quality score expected >= 80, got {report.quality_score}")
        self.check(len(report.cleaning_operations) >= 1, "Report must list executed cleaning operations.")

        md_content, md_fn, md_type = DataCleaningService.export_cleaning_report(self.ds_dirty, "markdown", self.db)
        self.check("markdown" in md_type or "text" in md_type, f"Markdown media type expected text/markdown, got {md_type}")
        self.check(len(md_content) > 100, "Markdown report content must be populated.")
        self.check("Data Cleaning" in md_content or "Report" in md_content, "Report must include summary title.")

        csv_content, csv_fn, csv_type = DataCleaningService.export_cleaning_report(self.ds_dirty, "csv", self.db)
        self.check("csv" in csv_fn.lower(), "CSV report filename must have .csv extension.")

    # =========================================================================
    # PHASE 9: MULTIPLE-DATASET ANALYSIS & SECURITY (12 Assertions)
    # =========================================================================
    def test_09_multi_dataset_analysis_and_isolation(self):
        """Phase 9: Combined overview, distinct columns, and cross-tenant isolation."""
        resp = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds_cust.id, self.ds_ord.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )

        self.check(resp.status == "success", f"Multi-dataset analysis status expected success, got {resp.status}")
        self.check(resp.total_selected == 2, f"Total selected expected 2, got {resp.total_selected}")
        self.check(resp.total_successful == 2, f"Total successful expected 2, got {resp.total_successful}")

        # Combined Overview: 5 customers + 7 orders = 12 combined rows
        comb = resp.combined_overview
        self.check(comb is not None, "Combined overview must not be None.")
        self.check(comb.total_datasets == 2, f"Combined total_datasets expected 2, got {comb.total_datasets}")
        self.check(comb.total_rows == 12, f"Combined rows expected 12, got {comb.total_rows}")
        # Distinct columns: cust_id, name, city, age, order_id, order_amount = 6
        self.check(comb.distinct_columns == 6, f"Combined distinct attributes expected 6, got {comb.distinct_columns}")

        # Individual profiles strictly isolated by dataset ID
        self.check(self.ds_cust.id in resp.individual_profiles, "Customer dataset profile must be in response.")
        self.check(self.ds_ord.id in resp.individual_profiles, "Order dataset profile must be in response.")
        self.check(resp.individual_profiles[self.ds_cust.id].dataset_info.rows == 5, "Customer rows must be 5.")
        self.check(resp.individual_profiles[self.ds_ord.id].dataset_info.rows == 7, "Order rows must be 7.")

        # Cross-Tenant Security Isolation: User 1 cannot access Tenant 2 dataset
        resp_unauth = MultiDatasetAnalysisService.analyze_datasets(
            dataset_ids=[self.ds_t2.id],
            mode="all",
            current_user=self.user1,
            db=self.db,
        )
        self.check(resp_unauth.total_successful == 0, "Unauthorized dataset analysis must yield 0 successful.")

    # =========================================================================
    # PHASE 10: SCHEMA MATCHING, RELATIONSHIPS & SAFE JOINS (14 Assertions)
    # =========================================================================
    def test_10_schema_matching_and_safe_joins(self):
        """Phase 10: Foreign key detection, cardinality, city/age guardrail, and join preview."""
        # 1. Relationship Discovery
        rel_resp = RelationshipService.detect_relationships([self.ds_cust, self.ds_ord])
        self.check(rel_resp.total_detected >= 1, f"Expected >= 1 relationship detected, got {rel_resp.total_detected}")

        primary_rel = next((r for r in rel_resp.relationships if r.source_column == "cust_id" and r.target_column == "cust_id"), None)
        self.check(primary_rel is not None, "cust_id join relationship must be discovered.")
        self.check(primary_rel.relationship_type.upper().replace("-", "_") in ["ONE_TO_MANY", "MANY_TO_ONE"], f"Cardinality expected 1:N, got {primary_rel.relationship_type}")
        self.check(primary_rel.confidence_score >= 0.70, f"Confidence score expected >= 0.70, got {primary_rel.confidence_score}")

        # Guardrail check: City overlaps between datasets, but MUST NOT be classified as join key!
        city_rel = next((r for r in rel_resp.relationships if r.source_column == "city" or r.target_column == "city"), None)
        self.check(city_rel is None, "Non-relational demographic column 'city' must NOT be detected as join key.")
        self.check("city" in RelationshipDetector.NON_RELATIONAL_ATTRIBUTES, "City must be in RelationshipDetector.NON_RELATIONAL_ATTRIBUTES.")
        self.check("age" in RelationshipDetector.NON_RELATIONAL_ATTRIBUTES, "Age must be in RelationshipDetector.NON_RELATIONAL_ATTRIBUTES.")

        # 2. Safe Join Preview: INNER JOIN
        inner_preview = RelationshipService.preview_join(
            left_dataset=self.ds_cust,
            left_column="cust_id",
            right_dataset=self.ds_ord,
            right_column="cust_id",
            join_type="INNER",
            limit=50,
        )
        self.check(inner_preview.join_type.upper() == "INNER", "Join type must be INNER.")
        # Exact Math: Cust 1 (2 orders) + Cust 2 (1) + Cust 3 (1) + Cust 4 (2) = 6 rows (Evan has 0, orphan 999 excluded)
        self.check(inner_preview.estimated_resulting_rows == 6, f"Inner join rows expected 6, got {inner_preview.estimated_resulting_rows}")
        amounts = [float(r["order_amount"]) for r in inner_preview.sample_rows if "order_amount" in r]
        self.check(sum(amounts) == 1450.0, f"Inner join total amount expected 1450.0, got {sum(amounts)}")

        # 3. Safe Join Preview: LEFT JOIN
        left_preview = RelationshipService.preview_join(
            left_dataset=self.ds_cust,
            left_column="cust_id",
            right_dataset=self.ds_ord,
            right_column="cust_id",
            join_type="LEFT",
            limit=50,
        )
        self.check(left_preview.join_type.upper() == "LEFT", "Join type must be LEFT.")
        # Left join preserves Customer 5 (Evan) with null order_id -> 6 + 1 = 7 rows
        self.check(left_preview.estimated_resulting_rows == 7, f"Left join rows expected 7, got {left_preview.estimated_resulting_rows}")
        evan_row = next(r for r in left_preview.sample_rows if r.get("name") == "Evan")
        self.check(pd.isna(evan_row.get("order_id")) or evan_row.get("order_id") is None, "Customer 5 (Evan) order_id must be null in Left Join.")
        self.check(inner_preview.row_explosion_risk is False, "No row explosion risk detected.")


def run_acceptance_suite():
    """Execute acceptance suite and print exact verification scorecard."""
    suite = unittest.TestLoader().loadTestsFromTestCase(GroundTruthAcceptanceSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = GroundTruthAcceptanceSuite.total_assertions
    passed = GroundTruthAcceptanceSuite.passed_assertions
    failed = len(GroundTruthAcceptanceSuite.failures_log)
    rate = round((passed / total * 100), 2) if total > 0 else 0.0

    print("\n" + "=" * 70)
    print("GROUND-TRUTH ACCEPTANCE SUITE EXECUTION SCORECARD")
    print("=" * 70)
    print(f"Total Eligible Test Assertions:  {total}")
    print(f"Successfully Passed Assertions:  {passed}")
    print(f"Failed Test Assertions:          {failed}")
    print(f"Calculated Correctness Rate:     {rate}%")
    print("=" * 70)

    if rate >= 95.0 and len(result.failures) == 0 and len(result.errors) == 0:
        print(f"[SUCCESS] 95% Correctness Gate Achieved: {rate}% >= 95.00%")
        return 0
    else:
        print(f"[FAIL] Acceptance Gate Not Met: {rate}% < 95.00%")
        for f in GroundTruthAcceptanceSuite.failures_log:
            print(f"  - Failure: {f}")
        return 1


if __name__ == "__main__":
    sys.exit(run_acceptance_suite())
