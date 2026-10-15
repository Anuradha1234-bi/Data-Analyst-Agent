"""Comprehensive automated test suite for Phase 2: FastAPI Backend + Database + Authentication."""

import unittest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.auth.security import create_access_token, hash_password, verify_password, validate_password_strength

# Shared in-memory SQLite for isolated test execution using StaticPool
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class TestPhase2Authentication(unittest.TestCase):
    """Test suite covering all requirements from Phase 2 Section 22."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.clear()

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db

    # =========================================================================
    # 1. REGISTRATION TESTS
    # =========================================================================

    def test_01_valid_registration(self):
        """Valid registration -> 201 Created and safe response structure."""
        payload = {
            "full_name": "Alice Analyst",
            "email": "alice@analytics.io",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["message"], "Registration successful")
        self.assertEqual(data["user"]["full_name"], "Alice Analyst")
        self.assertEqual(data["user"]["email"], "alice@analytics.io")
        self.assertNotIn("password", data["user"])
        self.assertNotIn("password_hash", data["user"])

    def test_02_duplicate_email_registration(self):
        """Duplicate email -> 400 Bad Request with 'Email is already registered.'"""
        payload = {
            "full_name": "Alice Duplicate",
            "email": "ALICE@analytics.io",  # Test case normalization
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Email is already registered", res.json()["detail"])

    def test_03_invalid_email_format(self):
        """Invalid email -> 422 Unprocessable Entity."""
        payload = {
            "full_name": "Invalid Email User",
            "email": "not-an-email",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 422)

    def test_04_weak_password_rejected(self):
        """Password shorter than 8 characters -> rejected."""
        payload = {
            "full_name": "Short Pass User",
            "email": "short@analytics.io",
            "password": "pass",
            "confirm_password": "pass",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertIn(res.status_code, [400, 422])

    def test_05_password_mismatch_rejected(self):
        """Password mismatch -> rejected."""
        payload = {
            "full_name": "Mismatch User",
            "email": "mismatch@analytics.io",
            "password": "StrongPassword123!",
            "confirm_password": "DifferentPassword456!",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertIn(res.status_code, [400, 422])

    # =========================================================================
    # 2. LOGIN TESTS
    # =========================================================================

    def test_06_correct_credentials_login(self):
        """Correct credentials -> 200 OK, valid JWT, and user info."""
        payload = {
            "email": "alice@analytics.io",
            "password": "StrongPassword123!",
        }
        res = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertEqual(data["user"]["email"], "alice@analytics.io")
        self.assertNotIn("password", data["user"])
        self.assertNotIn("password_hash", data["user"])

    def test_07_wrong_password_rejected(self):
        """Wrong password -> 401 Unauthorized with generic message."""
        payload = {
            "email": "alice@analytics.io",
            "password": "WrongPassword999!",
        }
        res = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    def test_08_unknown_email_rejected(self):
        """Unknown email -> 401 Unauthorized with generic message."""
        payload = {
            "email": "nonexistent@analytics.io",
            "password": "StrongPassword123!",
        }
        res = self.client.post("/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid email or password.")

    # =========================================================================
    # 3. AUTHENTICATION & PROTECTED ROUTE TESTS
    # =========================================================================

    def test_09_valid_jwt_access_me(self):
        """Valid JWT -> /api/auth/me returns current user profile."""
        login_res = self.client.post("/api/auth/login", json={
            "email": "alice@analytics.io",
            "password": "StrongPassword123!",
        })
        token = login_res.json()["access_token"]

        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        user = res.json()
        self.assertEqual(user["email"], "alice@analytics.io")
        self.assertEqual(user["full_name"], "Alice Analyst")
        self.assertTrue(user["is_active"])
        self.assertNotIn("password", user)
        self.assertNotIn("password_hash", user)

    def test_10_no_jwt_rejected(self):
        """No JWT -> 401 Unauthorized."""
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)

    def test_11_invalid_jwt_rejected(self):
        """Malformed or tampered JWT -> 401 Unauthorized."""
        res = self.client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
        self.assertEqual(res.status_code, 401)

    def test_12_expired_jwt_rejected(self):
        """Expired JWT -> 401 Unauthorized."""
        expired_token = create_access_token(
            {"sub": "1", "email": "alice@analytics.io"},
            expires_delta=timedelta(hours=-1),
        )
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        self.assertEqual(res.status_code, 401)

    def test_13_logout_endpoint(self):
        """Logout endpoint -> 200 OK with confirmation message."""
        login_res = self.client.post("/api/auth/login", json={
            "email": "alice@analytics.io",
            "password": "StrongPassword123!",
        })
        token = login_res.json()["access_token"]

        res = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Successfully logged out", res.json()["message"])


    # =========================================================================
    # 4. ADVANCED REGISTRATION & USERNAME HANDLING TESTS
    # =========================================================================

    def test_14_registration_with_custom_username(self):
        """Registration with explicit custom username -> saved and returned properly."""
        payload = {
            "username": "bob_analyst",
            "full_name": "Bob Analyst",
            "email": "bob@analytics.io",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["user"]["username"], "bob_analyst")
        self.assertEqual(data["user"]["email"], "bob@analytics.io")
        self.assertEqual(data["user"]["full_name"], "Bob Analyst")

    def test_15_duplicate_username_registration(self):
        """Duplicate username registration -> 400 Bad Request with username error."""
        payload = {
            "username": "bob_analyst",
            "full_name": "Bob Imposter",
            "email": "another_bob@analytics.io",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Username is already taken", res.json()["detail"])

    def test_16_username_auto_derivation_and_collision_handling(self):
        """Registration without username auto-derives unique usernames without collision."""
        payload1 = {
            "full_name": "Carol Analyst 1",
            "email": "carol@analytics.io",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        res1 = self.client.post("/api/auth/register", json=payload1)
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.json()["user"]["username"], "carol")

        # Second user with same prefix but different domain
        payload2 = {
            "full_name": "Carol Analyst 2",
            "email": "carol@domain2.io",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        }
        res2 = self.client.post("/api/auth/register", json=payload2)
        self.assertEqual(res2.status_code, 201)
        self.assertTrue(res2.json()["user"]["username"].startswith("carol_"))

    def test_17_login_using_username(self):
        """Login using username instead of email -> 200 OK and valid JWT token."""
        res = self.client.post("/api/auth/login", json={
            "username": "bob_analyst",
            "password": "StrongPassword123!",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["username"], "bob_analyst")

    def test_18_persisted_user_has_all_required_columns(self):
        """Direct database verification that all NOT NULL columns are populated."""
        from app.models.user import User
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == "bob@analytics.io").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.username, "bob_analyst")
            self.assertEqual(user.role, "user")
            self.assertTrue(user.is_active)
            self.assertIsNotNone(user.hashed_password)
            self.assertIsNotNone(user.password_hash)
            self.assertIsNotNone(user.created_at)
            self.assertIsNotNone(user.updated_at)
        finally:
            db.close()

    def test_19_transaction_rollback_on_failed_registration(self):
        """Failed registration rolls back transaction and keeps session clean."""
        # Attempt duplicate registration
        res = self.client.post("/api/auth/register", json={
            "email": "alice@analytics.io",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        })
        self.assertEqual(res.status_code, 400)

        # Subsequent valid registration immediately succeeds
        res_valid = self.client.post("/api/auth/register", json={
            "full_name": "Dave Analyst",
            "email": "dave@analytics.io",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        })
        self.assertEqual(res_valid.status_code, 201)
        self.assertEqual(res_valid.json()["user"]["email"], "dave@analytics.io")


if __name__ == "__main__":
    unittest.main()
