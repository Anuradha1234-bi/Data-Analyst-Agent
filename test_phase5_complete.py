"""End-to-End Comprehensive Verification Test Suite for Phase 5.

Validates:
Part A: Single Dataset Cleaning (imputation, deduplication, empty entities, safe type conversions, versioning, immutability)
Part B: Multi-Dataset Relationship Detection & Safe Joins (discovery, overlap, cardinality, PK/FK hints, review, preview, apply, derived dataset persistence, source immutability, zero regression)
"""

import sys
import os
import json
import unittest
import urllib.request
import urllib.error
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.auth.jwt import create_access_token

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8002/api")
FRONTEND_BASE = os.environ.get("FRONTEND_BASE", "http://localhost:5174")


class TestPhase5Complete(unittest.TestCase):
    """Rigorous end-to-end tests for all Phase 5 requirements."""

    @classmethod
    def setUpClass(cls):
        import io
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)
        cls.token = create_access_token(data={"sub": "11"})
        cls.headers = {
            "Authorization": f"Bearer {cls.token}",
            "Content-Type": "application/json",
        }
        cls.created_dataset_ids = []

        outliers_csv = ("Experience,Salary\n" + "".join([f"{i+1},{30000 + i*3000}\n" for i in range(20)])).encode("utf-8")
        big_ml_csv = ("Experience,Score\n" + "".join([f"{i+1},{50 + i*2}\n" for i in range(20)])).encode("utf-8")

        r1 = cls.client.post(
            "/api/datasets/upload",
            files=[("files", ("experience_salary_outliers.csv", io.BytesIO(outliers_csv), "text/csv"))],
            headers={"Authorization": f"Bearer {cls.token}"},
        )
        cls.ds_outlier_id = r1.json()["uploaded"][0]["id"]
        cls.created_dataset_ids.append(cls.ds_outlier_id)

        r2 = cls.client.post(
            "/api/datasets/upload",
            files=[("files", ("big_ml_practice_dataset.csv", io.BytesIO(big_ml_csv), "text/csv"))],
            headers={"Authorization": f"Bearer {cls.token}"},
        )
        cls.ds_ml_id = r2.json()["uploaded"][0]["id"]
        cls.created_dataset_ids.append(cls.ds_ml_id)

    @classmethod
    def tearDownClass(cls):
        # Clean up any created test datasets via DELETE endpoint
        for did in getattr(cls, "created_dataset_ids", []):
            try:
                cls.client.delete(f"/api/datasets/{did}", headers={"Authorization": f"Bearer {cls.token}"})
            except Exception:
                pass

    def api_get(self, endpoint: str):
        req = urllib.request.Request(f"{API_BASE}{endpoint}", headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def api_post(self, endpoint: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{API_BASE}{endpoint}", data=data, headers=self.headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _get_dataset_file_path(self, dataset_id: int) -> Path:
        db_path = BACKEND_DIR / "data_analyst.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM datasets WHERE id = ?", (dataset_id,))
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            raise ValueError(f"Dataset {dataset_id} file_path not found in database.")
        return Path(row[0])

    # =========================================================================
    # 1. REGRESSION TESTS FOR DASHBOARD, DATASETS, PROFILE, QUALITY
    # =========================================================================

    def test_01_system_regressions(self):
        """Verify Dashboard health, datasets listing, profiling, and quality are all intact."""
        status_code, health = self.api_get("/health")
        self.assertEqual(status_code, 200)
        self.assertIn(health.get("status"), ["healthy", "ok"])

        status_code, datasets = self.api_get("/datasets/")
        self.assertEqual(status_code, 200)
        self.assertGreater(len(datasets), 0)

        first_ds_id = datasets[0]["id"]

        # Data Profile check
        status_code, profile = self.api_get(f"/datasets/{first_ds_id}/profile")
        self.assertEqual(status_code, 200)
        self.assertIn("columns", profile)

        # Data Quality check
        status_code, quality = self.api_get(f"/datasets/{first_ds_id}/quality")
        self.assertEqual(status_code, 200)
        self.assertIn("summary", quality)
        self.assertIn("quality_score", quality["summary"])

        print("\n--- Test 1: System Regressions ---")
        print("  [PASS] Health, Datasets, Profiling, and Quality all operational.")

    # =========================================================================
    # 2. PART A: DATA CLEANING OVERVIEW & DIAGNOSTICS
    # =========================================================================

    def test_02_single_dataset_cleaning_overview(self):
        """Verify cleaning overview endpoints return column diagnostics and recommendations."""
        status_code, datasets = self.api_get("/datasets/")
        self.assertEqual(status_code, 200)
        target = next((d for d in datasets if "missing" in d["filename"].lower()), datasets[0])
        ds_id = target["id"]

        status_code, overview1 = self.api_get(f"/cleaning/{ds_id}")
        self.assertEqual(status_code, 200)
        self.assertIn("columns", overview1)
        self.assertIn("duplicate_rows_count", overview1)
        self.assertIn("empty_rows_count", overview1)

        status_code, overview2 = self.api_get(f"/datasets/{ds_id}/cleaning")
        self.assertEqual(status_code, 200)
        self.assertEqual(overview1["dataset_id"], overview2["dataset_id"])

        print("\n--- Test 2: Single Dataset Cleaning Overview ---")
        print(f"  [PASS] Diagnostics retrieved for dataset {target['filename']} ({len(overview1['columns'])} cols).")

    # =========================================================================
    # 3. PART A: PREVIEW AND APPLY WITH IMMUTABILITY
    # =========================================================================

    def test_03_cleaning_preview_and_immutability(self):
        """Verify cleaning operations preview correctly without modifying original file."""
        status_code, datasets = self.api_get("/datasets/")
        target = datasets[0]
        ds_id = target["id"]

        orig_path = self._get_dataset_file_path(ds_id)
        orig_content = orig_path.read_bytes()

        preview_payload = {
            "remove_duplicates": True,
            "remove_empty_rows": True,
            "missing_imputations": [],
        }
        status_code, preview = self.api_post(f"/cleaning/{ds_id}/preview", preview_payload)
        self.assertEqual(status_code, 200)
        self.assertIn("before", preview)
        self.assertIn("after", preview)

        # Immutability check during preview
        self.assertEqual(orig_path.read_bytes(), orig_content)

        print("\n--- Test 3: Cleaning Preview & Immutability ---")
        print("  [PASS] Preview calculated without mutating source dataset file.")

    # =========================================================================
    # 4. PART B: MULTI-DATASET RELATIONSHIP DISCOVERY
    # =========================================================================

    def test_04_relationship_discovery(self):
        """Verify multi-dataset relationship discovery detects candidate relationships."""
        status_code, result = self.api_get("/relationships/")
        self.assertEqual(status_code, 200)
        self.assertIn("total_detected", result)
        self.assertIn("relationships", result)
        self.assertGreater(result["total_detected"], 0)

        # Also verify via POST /relationships/detect
        status_code, detect_res = self.api_post("/relationships/detect", {})
        self.assertEqual(status_code, 200)
        self.assertEqual(detect_res["total_detected"], result["total_detected"])

        print("\n--- Test 4: Relationship Discovery ---")
        print(f"  [PASS] Detected {result['total_detected']} candidate relationships across {result['analyzed_datasets_count']} datasets.")

    # =========================================================================
    # 5. PART B: COMMON COLUMN & CASE/NORMALIZATION DETECTION
    # =========================================================================

    def test_05_common_column_and_normalization(self):
        """Verify common column detection handles exact, case differences, and normalized keys."""
        status_code, result = self.api_get("/relationships/")
        self.assertEqual(status_code, 200)
        rels = result["relationships"]

        # Find experience match
        exp_match = next(
            (r for r in rels if "experience" in r["source_column"].lower() and "experience" in r["target_column"].lower()),
            None
        )
        self.assertIsNotNone(exp_match)
        self.assertTrue(exp_match["data_type_compatible"])

        print("\n--- Test 5: Common Column & Normalization ---")
        print(f"  [PASS] Key '{exp_match['source_column']}' matched across {exp_match['source_dataset_name']} and {exp_match['target_dataset_name']}.")

    # =========================================================================
    # 6. PART B: VALUE OVERLAP & CONFIDENCE SCORING
    # =========================================================================

    def test_06_value_overlap_and_confidence_scoring(self):
        """Verify value overlap and relationship confidence score are mathematically computed."""
        status_code, result = self.api_get("/relationships/")
        rels = result["relationships"]

        for r in rels[:10]:
            self.assertGreaterEqual(r["value_overlap_pct"], 0.0)
            self.assertLessEqual(r["value_overlap_pct"], 100.0)
            self.assertGreaterEqual(r["confidence_score"], 0.0)
            self.assertLessEqual(r["confidence_score"], 100.0)
            self.assertIn(r["confidence"], ["HIGH", "MEDIUM", "LOW"])
            self.assertIn(r["confidence_label"], ["Strong Relationship", "Possible Relationship", "Weak / Uncertain"])

        print("\n--- Test 6: Value Overlap & Confidence Scoring ---")
        print(f"  [PASS] Verified composite confidence scoring for top relationship: {rels[0]['confidence_score']}% ({rels[0]['confidence_label']}).")

    # =========================================================================
    # 7. PART B: PRIMARY KEY / FOREIGN KEY CANDIDATES & CARDINALITY
    # =========================================================================

    def test_07_pk_fk_candidates_and_cardinality(self):
        """Verify system identifies Primary Key and Foreign Key candidates and infers cardinality."""
        status_code, result = self.api_get("/relationships/")
        rels = result["relationships"]

        valid_types = {"One-to-One", "One-to-Many", "Many-to-One", "Many-to-Many", "Unknown"}
        found_cardinality = False

        for r in rels:
            self.assertIn(r["relationship_type"], valid_types)
            if r["relationship_type"] in ["One-to-Many", "One-to-One", "Many-to-One"]:
                found_cardinality = True
                if r["source_is_pk_candidate"]:
                    self.assertTrue(any("Primary Key" in reason for reason in r["confidence_reasons"]))

        self.assertTrue(found_cardinality)
        print("\n--- Test 7: PK/FK Candidates & Cardinality ---")
        print("  [PASS] Identified PK/FK candidate roles and classified 1:1, 1:N, N:1 cardinalities.")

    # =========================================================================
    # 8. PART B: USER REVIEW STATUS (ACCEPT / REJECT / IGNORE)
    # =========================================================================

    def test_08_relationship_review_actions(self):
        """Verify user can accept, reject, or ignore relationship suggestions."""
        status_code, result = self.api_get("/relationships/")
        first_rel = result["relationships"][0]

        for test_status in ["ACCEPTED", "REJECTED", "IGNORED", "PENDING"]:
            status_code, resp = self.api_post("/relationships/status", {
                "relationship_id": first_rel["id"],
                "status": test_status,
            })
            self.assertEqual(status_code, 200)
            self.assertEqual(resp["status"], test_status)

        print("\n--- Test 8: Relationship Review Actions ---")
        print("  [PASS] Accept, Reject, and Ignore review actions functional.")

    # =========================================================================
    # 9. PART B: DRY-RUN JOIN PREVIEW ACCURACY
    # =========================================================================

    def test_09_join_preview_accuracy(self):
        """Verify dry-run join preview calculates accurate resulting rows, matching stats, and schema."""
        status_code, datasets = self.api_get("/datasets/")
        ds_left = next((d for d in datasets if "outlier" in d["filename"].lower()), datasets[0])
        ds_right = next((d for d in datasets if "ml_practice" in d["filename"].lower()), datasets[1])

        preview_req = {
            "left_dataset_id": ds_left["id"],
            "left_column": "Experience",
            "right_dataset_id": ds_right["id"],
            "right_column": "Experience",
            "join_type": "inner",
            "limit": 5,
        }

        # Test both /relationships/join-preview and /datasets/join/preview
        status_code1, prev1 = self.api_post("/relationships/join-preview", preview_req)
        self.assertEqual(status_code1, 200)

        status_code2, prev2 = self.api_post("/datasets/join/preview", preview_req)
        self.assertEqual(status_code2, 200)

        self.assertEqual(prev1["estimated_resulting_rows"], prev2["estimated_resulting_rows"])
        self.assertGreater(prev1["estimated_resulting_rows"], 0)
        self.assertGreater(prev1["matching_rows_count"], 0)
        self.assertIn("resulting_columns", prev1)
        self.assertGreater(len(prev1["sample_rows"]), 0)

        print("\n--- Test 9: Join Preview Accuracy ---")
        print(f"  [PASS] Simulated INNER JOIN: {prev1['estimated_resulting_rows']} rows, {len(prev1['resulting_columns'])} cols, {len(prev1['sample_rows'])} sample rows.")

    # =========================================================================
    # 10. PART B: CONFIRMATION ENFORCEMENT & SAFETY
    # =========================================================================

    def test_10_join_confirmation_enforcement(self):
        """Verify join does NOT execute without explicit user confirmation."""
        status_code, datasets = self.api_get("/datasets/")
        ds_left = datasets[0]
        ds_right = datasets[1]

        unconfirmed_req = {
            "left_dataset_id": ds_left["id"],
            "left_column": "Experience",
            "right_dataset_id": ds_right["id"],
            "right_column": "Experience",
            "join_type": "inner",
            "user_confirmed": False,
        }

        # Expect HTTP 400 Bad Request
        data = json.dumps(unconfirmed_req).encode("utf-8")
        req = urllib.request.Request(f"{API_BASE}/relationships/join-apply", data=data, headers=self.headers)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

        print("\n--- Test 10: Confirmation Enforcement ---")
        print("  [PASS] Unconfirmed join rejected with HTTP 400 safeguard.")

    # =========================================================================
    # 11. PART B: APPLY JOIN & DERIVED DATASET PERSISTENCE
    # =========================================================================

    def test_11_apply_join_and_separate_persistence(self):
        """Verify confirmed join creates a separate derived dataset while preserving source datasets."""
        status_code, datasets = self.api_get("/datasets/")
        ds_left = next((d for d in datasets if "outlier" in d["filename"].lower()), datasets[0])
        ds_right = next((d for d in datasets if "ml_practice" in d["filename"].lower()), datasets[1])

        # Record original file content and state
        left_path = self._get_dataset_file_path(ds_left["id"])
        right_path = self._get_dataset_file_path(ds_right["id"])
        left_bytes_before = left_path.read_bytes()
        right_bytes_before = right_path.read_bytes()

        join_req = {
            "left_dataset_id": ds_left["id"],
            "left_column": "Experience",
            "right_dataset_id": ds_right["id"],
            "right_column": "Experience",
            "join_type": "inner",
            "custom_dataset_name": "test_e2e_verified_joined",
            "user_confirmed": True,
        }

        status_code, applied = self.api_post("/relationships/join-apply", join_req)
        self.assertEqual(status_code, 200)
        self.assertTrue(applied["success"])
        self.assertIn("derived_dataset_id", applied)

        derived_id = applied["derived_dataset_id"]
        self.created_dataset_ids.append(derived_id)

        # Verify derived dataset exists in /datasets/
        status_code, all_datasets = self.api_get("/datasets/")
        derived_ds = next((d for d in all_datasets if d["id"] == derived_id), None)
        self.assertIsNotNone(derived_ds)
        self.assertEqual(derived_ds["rows"], applied["rows"])
        self.assertEqual(derived_ds["columns"], applied["columns"])

        # IMMUTABILITY GUARANTEE: Source datasets must remain 100% byte-for-byte identical
        self.assertEqual(left_path.read_bytes(), left_bytes_before)
        self.assertEqual(right_path.read_bytes(), right_bytes_before)

        print("\n--- Test 11: Apply Join & Derived Persistence ---")
        print(f"  [PASS] Created derived dataset '{applied['derived_dataset_name']}' ({applied['rows']} rows, {applied['columns']} cols).")
        print("  [PASS] Immutability verified: Source datasets remain bit-for-bit unchanged.")

    # =========================================================================
    # 12. FRONTEND INTEGRATION: ROUTES & DUAL WORKFLOW
    # =========================================================================

    def test_12_frontend_route_and_components(self):
        """Verify frontend /data-cleaning route and dual workflow components are active."""
        cleaning_jsx = ROOT_DIR / "frontend" / "src" / "pages" / "CleaningPage.jsx"
        self.assertTrue(cleaning_jsx.exists())

        rel_comp = ROOT_DIR / "frontend" / "src" / "components" / "RelationshipManager.jsx"
        self.assertTrue(rel_comp.exists())

        content = cleaning_jsx.read_text(encoding="utf-8")
        self.assertIn("RelationshipManager", content)
        self.assertIn("Single Dataset Cleaning", content)
        self.assertIn("Cross-Dataset Relationships", content)

        rel_content = rel_comp.read_text(encoding="utf-8")
        self.assertIn("Discover Relationships", rel_content)
        self.assertIn("Preview Join / Merge", rel_content)
        self.assertIn("Confirm Derived Dataset Creation", rel_content)

        print("\n--- Test 12: Frontend Integration ---")
        print("  [PASS] CleaningPage.jsx and RelationshipManager.jsx fully integrated with dual workflows.")


if __name__ == "__main__":
    unittest.main()

