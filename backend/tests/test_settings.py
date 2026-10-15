import io
import pytest
from app.models.user import User


def register_user(client, db_session, username="settings_user", email="user@example.com", role="user"):
    res = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": "Password123!"},
    )
    assert res.status_code == 201, res.text
    if role != "user":
        u = db_session.query(User).filter(User.username == username).first()
        if u:
            u.role = role
            db_session.commit()
    return res.json()


def get_token(client, username="settings_user"):
    res = client.post(
        "/api/auth/login",
        json={"username": username, "password": "Password123!"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_settings_overview_structure(client, db_session):
    register_user(client, db_session, "alice", "alice@example.com", role="user")
    token = get_token(client, "alice")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/settings/", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["username"] == "alice"
    assert data["role"] == "user"
    assert data["is_admin"] is False
    assert "user_preferences" in data
    assert "system_settings" in data
    assert "workspace_storage" in data
    assert "available_providers" in data
    assert "notification_channels" in data

    # Check defaults
    prefs = data["user_preferences"]
    assert prefs["theme"] == "light"
    assert prefs["default_anomaly_method"] == "both"
    assert prefs["default_iqr_multiplier"] == 1.5

    # Storage defaults
    storage = data["workspace_storage"]
    assert storage["used_storage_bytes"] == 0
    assert storage["dataset_count"] == 0
    assert storage["storage_quota_mb"] >= 500


def test_user_preferences_persistence(client, db_session):
    register_user(client, db_session, "bob", "bob@example.com", role="user")
    token = get_token(client, "bob")
    headers = {"Authorization": f"Bearer {token}"}

    # Update preferences
    payload = {
        "email_notifications": True,
        "anomaly_alert_notifications": True,
        "theme": "dark",
        "default_anomaly_method": "iqr",
        "default_iqr_multiplier": 3.0,
    }
    update_res = client.put("/api/settings/user-preferences", json=payload, headers=headers)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["email_notifications"] is True
    assert updated["anomaly_alert_notifications"] is True
    assert updated["theme"] == "dark"
    assert updated["default_anomaly_method"] == "iqr"
    assert updated["default_iqr_multiplier"] == 3.0

    # Verify persistence on overview
    overview_res = client.get("/api/settings/", headers=headers)
    assert overview_res.status_code == 200
    p = overview_res.json()["user_preferences"]
    assert p["theme"] == "dark"
    assert p["default_anomaly_method"] == "iqr"
    assert p["default_iqr_multiplier"] == 3.0


def test_system_settings_rbac_and_secret_masking(client, db_session):
    # Non-admin user cannot edit system settings
    register_user(client, db_session, "charlie", "charlie@example.com", role="user")
    charlie_token = get_token(client, "charlie")

    forbidden_res = client.put(
        "/api/settings/system",
        json={"max_upload_size_mb": 50},
        headers={"Authorization": f"Bearer {charlie_token}"},
    )
    assert forbidden_res.status_code == 403

    # Admin user CAN edit system settings
    register_user(client, db_session, "admin_user", "admin@example.com", role="admin")
    admin_token = get_token(client, "admin_user")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    secret_key = "AIzaSySecretApiKeyForValidation12345"
    admin_res = client.put(
        "/api/settings/system",
        json={
            "max_upload_size_mb": 75,
            "max_user_storage_mb": 250,
            "gemini_api_key": secret_key,
            "gemini_model": "gemini-1.5-pro",
        },
        headers=admin_headers,
    )
    assert admin_res.status_code == 200
    sys_data = admin_res.json()
    assert sys_data["max_upload_size_mb"] == 75
    assert sys_data["max_user_storage_mb"] == 250
    assert sys_data["gemini_model"] == "gemini-1.5-pro"
    assert sys_data["gemini_api_key_configured"] is True

    # Critical security requirement: Key must be masked and never returned in plaintext
    masked_key = sys_data["gemini_api_key_masked"]
    assert masked_key is not None
    assert masked_key != secret_key
    assert masked_key.startswith("AIzaSy")
    assert masked_key.endswith("2345")
    assert "••••" in masked_key


def test_notification_status_no_fake_success(client, db_session):
    register_user(client, db_session, "dave", "dave@example.com", role="user")
    token = get_token(client, "dave")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/settings/test-notification", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # In test/dev environment, SMTP is unconfigured; must honestly state unavailable
    assert data["configured"] is False
    assert data["status"] == "unavailable"
    assert "unavailable" in data["message"].lower() or "not configured" in data["message"].lower()


def test_workspace_storage_quota_enforcement(client, db_session):
    # Admin sets storage quota to 1 MB for testing quota enforcement
    register_user(client, db_session, "storage_admin", "storage_admin@example.com", role="admin")
    admin_token = get_token(client, "storage_admin")
    client.put(
        "/api/settings/system",
        json={"max_user_storage_mb": 1, "max_upload_size_mb": 50},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Normal user attempts to upload a file exceeding 1 MB quota (e.g. 1.3 MB)
    register_user(client, db_session, "eva", "eva@example.com", role="user")
    eva_token = get_token(client, "eva")
    eva_headers = {"Authorization": f"Bearer {eva_token}"}

    # Generate > 1 MB of CSV
    large_csv_lines = ["col_a,col_b,col_c\n"] + [f"{i},{i*2},{i*3}\n" for i in range(75000)]
    large_csv_content = "".join(large_csv_lines).encode("utf-8")
    assert len(large_csv_content) > 1024 * 1024  # > 1 MB

    files = [("files", ("large_test.csv", io.BytesIO(large_csv_content), "text/csv"))]
    upload_res = client.post("/api/datasets/upload", files=files, headers=eva_headers)
    assert upload_res.status_code == 200
    res_data = upload_res.json()

    assert len(res_data["uploaded"]) == 0
    assert len(res_data["failed"]) == 1
    err_msg = res_data["failed"][0]["error"]
    assert "quota exceeded" in err_msg.lower() or "limit is 1 mb" in err_msg.lower()
