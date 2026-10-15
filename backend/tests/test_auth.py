from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth_service import AuthService


def test_1_signup_success(client: TestClient):
    """Test 1: Successful registration creates a user with role 'user'."""
    payload = {
        "username": "anu",
        "email": "anu@example.com",
        "password": "StrongPassword123!",
    }
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code in (200, 201)
    data = response.json()
    assert data["message"] == "User created successfully"
    assert data["user"]["username"] == "anu"
    assert data["user"]["email"] == "anu@example.com"
    assert data["user"]["role"] == "user"
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]


def test_2_duplicate_email(client: TestClient):
    """Test 2: Re-registering with the same email returns HTTP 409 Conflict."""
    payload1 = {
        "username": "user_one",
        "email": "shared@example.com",
        "password": "StrongPassword123!",
    }
    client.post("/api/auth/signup", json=payload1)

    payload2 = {
        "username": "user_two",
        "email": "shared@example.com",
        "password": "StrongPassword123!",
    }
    response = client.post("/api/auth/signup", json=payload2)
    assert response.status_code == 409
    assert "email address already exists" in response.text


def test_3_duplicate_username(client: TestClient):
    """Test 3: Re-registering with the same username returns HTTP 409 Conflict."""
    payload1 = {
        "username": "duplicate_user",
        "email": "user1@example.com",
        "password": "StrongPassword123!",
    }
    client.post("/api/auth/signup", json=payload1)

    payload2 = {
        "username": "duplicate_user",
        "email": "user2@example.com",
        "password": "StrongPassword123!",
    }
    response = client.post("/api/auth/signup", json=payload2)
    assert response.status_code == 409
    assert "username already exists" in response.text


def test_4_login_success(client: TestClient):
    """Test 4: Logging in with valid credentials returns HTTP 200 and access_token."""
    client.post(
        "/api/auth/signup",
        json={
            "username": "logintest",
            "email": "login@example.com",
            "password": "StrongPassword123!",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email_or_username": "login@example.com",
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "logintest"


def test_5_wrong_password(client: TestClient):
    """Test 5: Login with wrong password returns HTTP 401 with generic error."""
    client.post(
        "/api/auth/signup",
        json={
            "username": "wrongpassuser",
            "email": "wrongpass@example.com",
            "password": "StrongPassword123!",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email_or_username": "wrongpass@example.com",
            "password": "IncorrectPassword999!",
        },
    )
    assert response.status_code == 401
    assert "Invalid username/email or password" in response.text


def test_6_invalid_jwt(client: TestClient):
    """Test 6: Request with malformed or invalid JWT returns HTTP 401."""
    headers = {"Authorization": "Bearer invalid.token.value"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401


def test_7_missing_jwt(client: TestClient):
    """Test 7: Accessing protected endpoint without JWT returns HTTP 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_8_current_user(client: TestClient):
    """Test 8: GET /api/auth/me with valid Bearer token returns current user profile."""
    client.post(
        "/api/auth/signup",
        json={
            "username": "anu",
            "email": "anu@example.com",
            "password": "StrongPassword123!",
        },
    )

    login_res = client.post(
        "/api/auth/login",
        json={
            "email_or_username": "anu",
            "password": "StrongPassword123!",
        },
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "anu"
    assert data["email"] == "anu@example.com"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_9_normal_user_accessing_admin_endpoint(client: TestClient):
    """Test 9: Normal user with role 'user' receives HTTP 403 on admin-only route."""
    client.post(
        "/api/auth/signup",
        json={
            "username": "regularuser",
            "email": "regular@example.com",
            "password": "StrongPassword123!",
        },
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email_or_username": "regularuser", "password": "StrongPassword123!"},
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_10_admin_accessing_admin_endpoint(client: TestClient, db_session: Session):
    """Test 10: Admin user receives HTTP 200 on admin endpoint."""
    AuthService.seed_admin_user(
        db=db_session,
        username="superadmin",
        email="superadmin@example.com",
        password="SuperAdminPassword123!",
    )

    login_res = client.post(
        "/api/auth/login",
        json={"email_or_username": "superadmin", "password": "SuperAdminPassword123!"},
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    users_list = response.json()
    assert isinstance(users_list, list)
    assert any(u["username"] == "superadmin" for u in users_list)


def test_11_password_security(client: TestClient, db_session: Session):
    """Test 11: Database stores hashed password and never the plaintext password."""
    raw_password = "SecretPasswordToHash123!"
    client.post(
        "/api/auth/signup",
        json={
            "username": "securitytest",
            "email": "sec@example.com",
            "password": raw_password,
        },
    )

    db_user = db_session.query(User).filter(User.username == "securitytest").first()
    assert db_user is not None
    assert db_user.hashed_password != raw_password
    assert raw_password not in db_user.hashed_password
    # Verify argon2 format prefix
    assert db_user.hashed_password.startswith("$argon2")


def test_12_existing_phase1_health_endpoint(client: TestClient):
    """Test 12: Existing Phase 1 health endpoint still returns HTTP 200."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "AI Data Analyst Agent"
