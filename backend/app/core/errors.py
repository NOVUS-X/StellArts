"""Unified API error response handling.

This module provides a standardized error response schema for the API,
so that every error returned to the frontend follows the same shape:

    {
        "error_code": "string",
        "message": "string",
        "details": {...},
        "detail": "string"   # kept for backward compatibility
    }
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _status_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.upper().replace(" ", "_")
    except ValueError:
        return "HTTP_ERROR"


def _build_error_payload(
    *,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }
    # Preserve `detail` for backward compatibility with existing clients/tests.
    payload["detail"] = message
    return payload


class APIError(HTTPException):
    """Base class for application-level errors carrying a stable error code."""

    error_code: str = "APP_ERROR"
    status_code: int = status.HTTP_400_BAD_REQUEST
    message: str = "An application error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
        error_code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.error_code = error_code or self.error_code
        self.message = message or self.message
        self.details = details or {}
        super().__init__(
            status_code=status_code or self.status_code,
            detail=self.message,
            headers=headers,
        )


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload(
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        ),
        headers=exc.headers,
    )


async def http_exception_handler(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    details: dict[str, Any] = {}
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or "HTTP error")
        details = {k: v for k, v in detail.items() if k not in {"message", "detail"}}
    elif isinstance(detail, str):
        message = detail
    else:
        message = str(detail) if detail is not None else "HTTP error"

    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload(
            error_code=_status_phrase(exc.status_code),
            message=message,
            details=details,
        ),
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_build_error_payload(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"errors": exc.errors()},
        ),
    )


async def unhandled_exception_handler(
    _: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_build_error_payload(
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            details={},
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the unified exception handlers on a FastAPI app."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
