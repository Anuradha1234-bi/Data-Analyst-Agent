"""Tests for Forgot Password and Password Reset workflow."""

import hashlib
import time
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.auth.security import hash_password, verify_password
from app.auth.rate_limiter import auth_rate_limiter


def setup_function():
    """Reset rate limiter before each test."""
    auth_rate_limiter.reset()


def test_forgot_password_existing_email(client: TestClient, db_session: Session):
    """Test 1: Requesting reset for existing email returns generic message and saves hashed token."""
    # Register test user
    email = "reset_user1@example.com"
    client.post(
        "/api/auth/signup",
        json={"username": "reset_user1", "email": email, "password": "OriginalPassword123!"},
    )

    response = client.post("/api/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    data = response.json()
    assert "If an account with that email exists" in data["message"]
    # In dev mode, dev_reset_url is populated for inspection
    assert data["dev_reset_url"] is not None
    assert "token=" in data["dev_reset_url"]

    # Verify DB state: token_hash is 64 hex chars (SHA-256), used is False, user_id is correct
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    token_record = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .first()
    )
    assert token_record is not None
    assert len(token_record.token_hash) == 64
    assert token_record.used is False
    exp = token_record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    assert exp > datetime.now(timezone.utc)


def test_forgot_password_nonexistent_email(client: TestClient, db_session: Session):
    """Test 2: Requesting reset for unregistered email returns identical generic message (no enumeration)."""
    response = client.post("/api/auth/forgot-password", json={"email": "nonexistent@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert "If an account with that email exists" in data["message"]
    # No dev reset URL generated for nonexistent email
    assert data["dev_reset_url"] is None


def test_forgot_password_inactive_user(client: TestClient, db_session: Session):
    """Test 3: Deactivated user account cannot receive active reset tokens."""
    email = "inactive@example.com"
    pwd = hash_password("InactivePassword123!")
    user = User(
        username="inactive_usr",
        email=email,
        hashed_password=pwd,
        password_hash=pwd,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post("/api/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    assert response.json()["dev_reset_url"] is None

    # Verify no active token created in DB
    tokens = db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).all()
    assert len(tokens) == 0


def test_subsequent_request_invalidates_prior_tokens(client: TestClient, db_session: Session):
    """Test 4: Requesting a new token invalidates previously issued unused tokens for the same user."""
    email = "multitoken@example.com"
    client.post(
        "/api/auth/signup",
        json={"username": "multitoken_user", "email": email, "password": "OriginalPassword123!"},
    )

    res1 = client.post("/api/auth/forgot-password", json={"email": email})
    raw_token1 = res1.json()["dev_reset_url"].split("token=")[1]

    res2 = client.post("/api/auth/forgot-password", json={"email": email})
    raw_token2 = res2.json()["dev_reset_url"].split("token=")[1]

    # Verify first token is marked used/invalidated
    hash1 = hashlib.sha256(raw_token1.encode()).hexdigest()
    rec1 = db_session.query(PasswordResetToken).filter(PasswordResetToken.token_hash == hash1).first()
    assert rec1.used is True

    # Verify second token is valid and unconsumed
    hash2 = hashlib.sha256(raw_token2.encode()).hexdigest()
    rec2 = db_session.query(PasswordResetToken).filter(PasswordResetToken.token_hash == hash2).first()
    assert rec2.used is False


def test_verify_reset_token_endpoint(client: TestClient, db_session: Session):
    """Test 5: Token verification endpoint validates active token and rejects invalid/expired tokens."""
    email = "verifytoken@example.com"
    client.post(
        "/api/auth/signup",
        json={"username": "verifytoken_user", "email": email, "password": "OriginalPassword123!"},
    )
    res = client.post("/api/auth/forgot-password", json={"email": email})
    raw_token = res.json()["dev_reset_url"].split("token=")[1]

    # Valid token check
    v_res = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
    assert v_res.status_code == 200
    assert v_res.json()["valid"] is True

    # Tampered / nonexistent token check
    bad_res = client.get("/api/auth/verify-reset-token?token=completely_invalid_random_token_123")
    assert bad_res.status_code == 400
    assert "Invalid or expired" in bad_res.json()["detail"]


def test_verify_reset_token_expired(client: TestClient, db_session: Session):
    """Test 6: Expired token is rejected."""
    email = "expiredtoken@example.com"
    client.post(
        "/api/auth/signup",
        json={"username": "expired_user", "email": email, "password": "OriginalPassword123!"},
    )
    res = client.post("/api/auth/forgot-password", json={"email": email})
    raw_token = res.json()["dev_reset_url"].split("token=")[1]

    # Manually expire token in DB
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    rec = db_session.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    rec.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    v_res = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
    assert v_res.status_code == 400
    assert "expired" in v_res.json()["detail"].lower()


def test_reset_password_workflow_and_subsequent_login(client: TestClient, db_session: Session):
    """Test 7: Full reset workflow: old password rejected, new password verified, token invalidated."""
    email = "fullflow@example.com"
    old_pwd = "OriginalPassword123!"
    new_pwd = "BrandNewSecurePassword456!"

    client.post(
        "/api/auth/signup",
        json={"username": "fullflow_user", "email": email, "password": old_pwd},
    )

    # 1. Request reset
    fp_res = client.post("/api/auth/forgot-password", json={"email": email})
    raw_token = fp_res.json()["dev_reset_url"].split("token=")[1]

    # 2. Reset password
    reset_payload = {
        "token": raw_token,
        "new_password": new_pwd,
        "confirm_password": new_pwd,
    }
    reset_res = client.post("/api/auth/reset-password", json=reset_payload)
    assert reset_res.status_code == 200
    assert "Password has been reset successfully" in reset_res.json()["message"]

    # 3. Old password must be rejected
    old_login_res = client.post(
        "/api/auth/login",
        json={"email_or_username": email, "password": old_pwd},
    )
    assert old_login_res.status_code == 401

    # 4. New password must authenticate successfully
    new_login_res = client.post(
        "/api/auth/login",
        json={"email_or_username": email, "password": new_pwd},
    )
    assert new_login_res.status_code == 200
    assert "access_token" in new_login_res.json()

    # 5. Token cannot be reused
    reuse_res = client.post("/api/auth/reset-password", json=reset_payload)
    assert reuse_res.status_code == 400


def test_reset_password_weak_policy(client: TestClient, db_session: Session):
    """Test 8: New password must conform to complexity policy."""
    email = "weakpwd@example.com"
    client.post(
        "/api/auth/signup",
        json={"username": "weakpwd_user", "email": email, "password": "StrongPassword123!"},
    )
    fp_res = client.post("/api/auth/forgot-password", json={"email": email})
    raw_token = fp_res.json()["dev_reset_url"].split("token=")[1]

    # Password too short (< 8 chars)
    weak_res1 = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "new_password": "short", "confirm_password": "short"},
    )
    assert weak_res1.status_code in (400, 422)

    # Password without digits or symbols
    weak_res2 = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "new_password": "OnlyLettersLongEnough", "confirm_password": "OnlyLettersLongEnough"},
    )
    assert weak_res2.status_code == 400
    assert "digit or special character" in weak_res2.json()["detail"]


def test_rate_limiting_abuse_prevention(client: TestClient):
    """Test 9: Rate limiting triggers HTTP 429 when threshold exceeded."""
    auth_rate_limiter.reset()

    # Hit 10 times (the allowed limit)
    for _ in range(10):
        res = client.post("/api/auth/forgot-password", json={"email": "ratelimit@example.com"})
        assert res.status_code == 200

    # 11th request must trigger 429 Too Many Requests
    blocked_res = client.post("/api/auth/forgot-password", json={"email": "ratelimit@example.com"})
    assert blocked_res.status_code == 429
    assert "Too many password reset requests" in blocked_res.json()["detail"]
