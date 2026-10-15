"""Automated test suite for Anomaly & Outlier Detection Module."""

import io
import json
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.user import User
from tools.anomaly_tool import AnomalyTool


def _create_test_dataset(client: TestClient, df: pd.DataFrame, filename: str = "test_anomaly.csv", token: str = None) -> int:
    """Helper to upload a dataset and return its assigned ID."""
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    files = {"files": (filename, io.BytesIO(csv_bytes), "text/csv")}
    resp = client.post("/api/datasets/upload", files=files, headers=headers)
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    data = resp.json()
    assert len(data["uploaded"]) > 0
    return data["uploaded"][0]["id"]


def test_1_iqr_mathematical_precision():
    """Test 1: Verify Q1, Q3, IQR, and bounds against known mathematical values."""
    # Known dataset: [10, 12, 14, 16, 18, 20, 22, 24, 26, 100]
    # Q1 = 13.5, Q3 = 22.5, IQR = 9.0
    # For 1.5x: Lower = 13.5 - 13.5 = 0.0, Upper = 22.5 + 13.5 = 36.0 -> 100 is outlier
    data = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 100.0]
    df = pd.DataFrame({"metric": data})

    res = AnomalyTool.detect_iqr_outliers(df, columns=["metric"], multiplier=1.5)
    col_res = res.column_results["metric"]

    assert col_res.q1 == pytest.approx(13.5, 0.1)
    assert col_res.q3 == pytest.approx(22.5, 0.1)
    assert col_res.iqr == pytest.approx(9.0, 0.1)
    assert col_res.upper_bound == pytest.approx(36.0, 0.1)
    assert col_res.total_outliers == 1
    assert col_res.outlier_indices == [9]
    assert res.total_outlier_rows == 1


def test_2_iqr_multiplier_1_5x_vs_3_0x():
    """Test 2: Configurable multiplier correctly differentiates moderate and extreme outliers."""
    # Data: normal cluster 10..20, moderate outlier 32.0 (between 28.0 and 37.0), extreme outlier 120.0
    df = pd.DataFrame({
        "val": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 32.0, 120.0]
    })

    # At 1.5x multiplier: both 40 and 120 are flagged
    res_1_5 = AnomalyTool.detect_iqr_outliers(df, columns=["val"], multiplier=1.5)
    # At 3.0x multiplier: only extreme outlier 120 should be flagged
    res_3_0 = AnomalyTool.detect_iqr_outliers(df, columns=["val"], multiplier=3.0)

    assert res_1_5.column_results["val"].total_outliers >= 2
    assert res_3_0.column_results["val"].total_outliers < res_1_5.column_results["val"].total_outliers
    assert 120.0 in [df.loc[i, "val"] for i in res_3_0.column_results["val"].outlier_indices]


def test_3_isolation_forest_multivariate():
    """Test 3: Isolation Forest detects multivariate anomalies on controlled numeric features."""
    np.random.seed(42)
    # Generate 40 normal correlated records and 2 stark multivariate anomalies
    feat1 = np.random.normal(50, 5, 40).tolist() + [50.0, 50.0]
    feat2 = np.random.normal(100, 10, 40).tolist() + [500.0, -100.0]  # Anomaly points at end

    df = pd.DataFrame({"f1": feat1, "f2": feat2})
    res = AnomalyTool.detect_isolation_forest(df, columns=["f1", "f2"], contamination=0.05, random_state=42)

    assert res.anomaly_count >= 1
    assert 40 in res.anomaly_indices or 41 in res.anomaly_indices
    assert len(res.anomaly_scores) == len(df)
    assert all(0.0 <= s <= 1.0 for s in res.anomaly_scores)


def test_4_edge_cases_constant_null_small(client: TestClient, db_session: Session):
    """Test 4: Handle constant columns, missing values, non-numeric columns, and small datasets safely."""
    # Create user & auth token
    signup_res = client.post("/api/auth/signup", json={
        "username": "anomaly_edge_user",
        "email": "edge@example.com",
        "password": "StrongPassword123!"
    })
    token = client.post("/api/auth/login", json={
        "email_or_username": "edge@example.com",
        "password": "StrongPassword123!"
    }).json()["access_token"]

    # Dataset with constant column, non-numeric column, nulls, and valid column
    df = pd.DataFrame({
        "id_col": [1, 2, 3, 4, 5, 6, 7],
        "category": ["A", "B", "A", "C", "B", "A", "C"],
        "constant_col": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        "with_nulls": [12.0, np.nan, 14.0, 15.0, np.nan, 18.0, 120.0],
    })
    ds_id = _create_test_dataset(client, df, "edge_dataset.csv", token=token)

    # 1. Inspect numeric columns endpoint excludes ID and constant columns
    col_res = client.get(f"/api/anomalies/{ds_id}/columns", headers={"Authorization": f"Bearer {token}"})
    assert col_res.status_code == 200
    cols_data = col_res.json()
    assert "with_nulls" in cols_data["suitable_numeric_columns"]
    # Constant and ID should be excluded from suitable columns
    assert "id_col" not in cols_data["suitable_numeric_columns"]

    # 2. Run detection with IQR - should succeed and handle nulls safely
    detect_res = client.post("/api/anomalies/detect", json={
        "dataset_id": ds_id,
        "method": "iqr",
        "columns": ["with_nulls"],
        "multiplier": 1.5,
    }, headers={"Authorization": f"Bearer {token}"})

    assert detect_res.status_code == 200
    res_data = detect_res.json()
    assert res_data["summary"]["unique_flagged_records"] >= 1
    assert any("with_nulls" in r["flagged_columns"] for r in res_data["flagged_records"])


def test_5_dataset_non_destruction(client: TestClient, db_session: Session):
    """Test 5: Anomaly detection must leave the original dataset records completely unchanged."""
    signup_res = client.post("/api/auth/signup", json={
        "username": "anomaly_safety_user",
        "email": "safety@example.com",
        "password": "StrongPassword123!"
    })
    token = client.post("/api/auth/login", json={
        "email_or_username": "safety@example.com",
        "password": "StrongPassword123!"
    }).json()["access_token"]

    original_rows = [
        {"x": 10.0, "y": 20.0},
        {"x": 12.0, "y": 22.0},
        {"x": 14.0, "y": 24.0},
        {"x": 16.0, "y": 26.0},
        {"x": 18.0, "y": 28.0},
        {"x": 20.0, "y": 30.0},
        {"x": 999.0, "y": 999.0},  # Stark outlier
    ]
    df = pd.DataFrame(original_rows)
    ds_id = _create_test_dataset(client, df, "safety_dataset.csv", token=token)

    # Run detection
    detect_res = client.post("/api/anomalies/detect", json={
        "dataset_id": ds_id,
        "method": "both",
        "multiplier": 1.5,
        "contamination": 0.1,
    }, headers={"Authorization": f"Bearer {token}"})
    assert detect_res.status_code == 200

    # Retrieve dataset row count and verify file on disk still has 7 rows
    dataset_rec = db_session.query(Dataset).filter(Dataset.id == ds_id).first()
    assert dataset_rec is not None
    loaded_df = pd.read_csv(dataset_rec.file_path)
    assert len(loaded_df) == 7
    assert float(loaded_df.loc[6, "x"]) == 999.0
    assert float(loaded_df.loc[6, "y"]) == 999.0


def test_6_authorization_isolation(client: TestClient):
    """Test 6: User cannot run anomaly detection on another user's dataset."""
    # User A
    client.post("/api/auth/signup", json={"username": "user_a", "email": "a@example.com", "password": "StrongPassword123!"})
    token_a = client.post("/api/auth/login", json={"email_or_username": "a@example.com", "password": "StrongPassword123!"}).json()["access_token"]

    # User B
    client.post("/api/auth/signup", json={"username": "user_b", "email": "b@example.com", "password": "StrongPassword123!"})
    token_b = client.post("/api/auth/login", json={"email_or_username": "b@example.com", "password": "StrongPassword123!"}).json()["access_token"]

    # Upload dataset as User A
    df = pd.DataFrame({"val": [1, 2, 3, 4, 5, 100]})
    ds_id = _create_test_dataset(client, df, "usera_data.csv", token=token_a)

    # User B attempts to access User A's dataset
    unauthorized_res = client.post("/api/anomalies/detect", json={
        "dataset_id": ds_id,
        "method": "iqr",
    }, headers={"Authorization": f"Bearer {token_b}"})

    assert unauthorized_res.status_code == 404
    assert "not found or access denied" in unauthorized_res.json()["detail"].lower()
