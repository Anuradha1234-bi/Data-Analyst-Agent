from fastapi.testclient import TestClient


def test_health_check_endpoint(client: TestClient):
    """
    Test 1 - Health API:
    GET /api/health returns HTTP 200 with status == 'ok'.
    """
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "AI Data Analyst Agent"


def test_health_check_headers(client: TestClient):
    """Verify health endpoint returns JSON content type."""
    response = client.get("/api/health")
    assert "application/json" in response.headers.get("content-type", "")


def test_health_swagger_docs(client: TestClient):
    """Verify Swagger UI and OpenAPI docs are available."""
    docs_response = client.get("/docs")
    assert docs_response.status_code == 200

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    openapi_spec = openapi_response.json()
    assert "/api/health" in openapi_spec["paths"]
