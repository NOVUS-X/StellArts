"""Tests for the unified API error response schema."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, register_exception_handlers


def _assert_unified_schema(body: dict) -> None:
    assert "error_code" in body
    assert "message" in body
    assert "details" in body
    assert isinstance(body["error_code"], str)
    assert isinstance(body["message"], str)
    assert isinstance(body["details"], dict)


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    from fastapi import HTTPException

    @app.get("/http-error")
    def _http_error() -> None:
        raise HTTPException(status_code=404, detail="Thing not found")

    @app.get("/app-error")
    def _app_error() -> None:
        raise AppError(
            status_code=400,
            message="Invalid payload",
            error_code="INVALID_PAYLOAD",
            details={"field": "email"},
        )

    @app.get("/validation-error/{num}")
    def _validation_error(num: int) -> int:
        return num

    @app.get("/crash")
    def _crash() -> None:
        raise RuntimeError("boom")

    return app


def test_http_exception_returns_unified_schema() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/http-error")
    assert resp.status_code == 404
    body = resp.json()
    _assert_unified_schema(body)
    assert body["error_code"] == "NOT_FOUND"
    assert body["message"] == "Thing not found"


def test_app_error_returns_custom_code_and_details() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/app-error")
    assert resp.status_code == 400
    body = resp.json()
    _assert_unified_schema(body)
    assert body["error_code"] == "INVALID_PAYLOAD"
    assert body["message"] == "Invalid payload"
    assert body["details"] == {"field": "email"}


def test_validation_error_returns_unified_schema() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/validation-error/not-an-int")
    assert resp.status_code == 422
    body = resp.json()
    _assert_unified_schema(body)
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "errors" in body["details"]


def test_unhandled_exception_returns_unified_schema() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/crash")
    assert resp.status_code == 500
    body = resp.json()
    _assert_unified_schema(body)
    assert body["error_code"] == "INTERNAL_SERVER_ERROR"
