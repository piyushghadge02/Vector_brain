"""Unit tests for the error envelope."""

from fastapi.testclient import TestClient

from app.core.errors import (
    AppError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
    error_envelope,
)
from app.main import create_app


def test_error_envelope_shape():
    body = error_envelope("SOME_CODE", "some message", "req123")
    assert body == {
        "code": "SOME_CODE",
        "message": "some message",
        "request_id": "req123",
    }


def test_builtin_error_attributes():
    assert (NotFoundError.code, NotFoundError.status_code) == ("NOT_FOUND", 404)
    assert (ValidationError.code, ValidationError.status_code) == (
        "VALIDATION_ERROR",
        422,
    )
    assert (ServiceUnavailableError.code, ServiceUnavailableError.status_code) == (
        "SERVICE_UNAVAILABLE",
        503,
    )


def test_app_error_maps_to_json_response():
    app = create_app()

    @app.get("/boom")
    async def boom():  # pragma: no cover - test route
        raise AppError("kaput", code="TEST_CODE", status_code=418)

    resp = TestClient(app).get("/boom")
    assert resp.status_code == 418
    body = resp.json()
    assert body["code"] == "TEST_CODE"
    assert body["message"] == "kaput"
    assert body["request_id"]  # middleware always sets one
    assert resp.headers["X-Request-ID"] == body["request_id"]


def test_404_uses_error_envelope():
    resp = TestClient(create_app()).get("/api/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert body["request_id"]


def test_unhandled_exception_does_not_leak_details():
    app = create_app()

    @app.get("/kaboom")
    async def kaboom():  # pragma: no cover - test route
        raise RuntimeError("super secret traceback content")

    # raise_server_exceptions=False so the 500 handler runs instead of
    # the exception propagating to the test.
    resp = TestClient(app, raise_server_exceptions=False).get("/kaboom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert "super secret" not in body["message"]


def test_request_validation_error_uses_envelope(client):
    # Invalid body (question too short) → 422 in the standard envelope,
    # not FastAPI's default {"detail": [...]} shape. Uses the lifespan
    # client because the endpoint's dependencies read app.state.
    resp = client.post("/api/v1/chat/query", json={"question": "hi"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "The request was invalid."
    assert body["request_id"]
    assert body["details"]["errors"]
