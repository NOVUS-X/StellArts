"""Tests for the standardized API error response schema."""

from fastapi.testclient import TestClient


def _assert_error_schema(payload: dict) -> None:
    assert "error_code" in payload, payload
    assert "message" in payload, payload
    assert "details" in payload, payload
    assert isinstance(payload["error_code"], str)
    assert isinstance(payload["message"], str)
    assert isinstance(payload["details"], dict)


def test_http_exception_uses_standard_schema(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "WrongPass1!"},
    )
    assert response.status_code in (400, 401)
    _assert_error_schema(response.json())


def test_validation_error_uses_standard_schema(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email"},
    )
    assert response.status_code == 422
    body = response.json()
    _assert_error_schema(body)
    assert body["error_code"] == "validation_error"
    assert "errors" in body["details"]


def test_not_found_route_uses_standard_schema(client: TestClient):
    response = client.get("/api/v1/this-route-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    _assert_error_schema(body)
    assert body["error_code"] == "not_found"
