"""Integration tests for GET /api/health (requires real PostgreSQL)."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_health_reports_database_and_pgvector(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "VectorBrain"
    assert body["database"] == "connected"
    assert body["pgvector"] == "available"
    assert body["groq_configured"] is False  # no key in test env
    assert "x-request-id" in resp.headers  # request ID echoed back


@pytest.mark.integration
def test_health_response_matches_schema(client: TestClient):
    from app.schemas.health import HealthResponse

    body = client.get("/api/health").json()
    parsed = HealthResponse.model_validate(body)  # raises on schema drift
    assert parsed.status == "ok"
