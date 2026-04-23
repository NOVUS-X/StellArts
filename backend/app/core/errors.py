"""
Unified API error response handling.

Provides a standardized error schema returned by every error response in the
application:

    {
        "error_code": "<machine readable code>",
        "message": "<human readable message>",
        "details": { ... },
    }

A legacy ``detail`` field mirroring ``message`` is also included to preserve
backwards compatibility with existing clients and tests that read the
FastAPI default ``detail`` key.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(HTTPException):
    """Application-level error with an explicit machine-readable error code."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.error_code = error_code
        self.message = message
        self.details: dict[str, Any] = details or {}


def _default_error_code(status_code: int) -> str:
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return f"HTTP_{status_code}"
    return phrase.upper().replace(" ", "_").replace("-", "_")


def _build_response(
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "error_code": error_code,
        "message": message,
        "details": details or {},
        # Legacy field kept for backwards compatibility with existing
        # clients/tests that read FastAPI's default ``detail`` key.
        "detail": message,
    }
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _build_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        headers=getattr(exc, "headers", None),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    details: dict[str, Any] = {}
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or detail)
        error_code = str(
            detail.get("error_code") or _default_error_code(exc.status_code)
        )
        nested = detail.get("details")
        if isinstance(nested, dict):
            details = nested
    else:
        message = str(detail) if detail is not None else HTTPStatus(
            exc.status_code
        ).phrase
        error_code = _default_error_code(exc.status_code)

    return _build_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=message,
        details=details,
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _build_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return _build_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        details={"type": exc.__class__.__name__},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the unified error handlers to a FastAPI application."""

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
