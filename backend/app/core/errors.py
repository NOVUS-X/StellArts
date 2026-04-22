"""Global error handling utilities.

Provides a unified error response schema for the API:

    {
        "error_code": str,
        "message": str,
        "details": object,
    }

All errors raised in FastAPI handlers (``HTTPException``, validation
errors, and unhandled exceptions) are normalized to this schema by the
exception handlers registered in :func:`register_exception_handlers`.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _status_to_error_code(status_code: int) -> str:
    """Derive a machine-readable error code from an HTTP status code."""
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return f"HTTP_{status_code}"
    return phrase.upper().replace(" ", "_").replace("-", "_")


def build_error_response(
    status_code: int,
    message: str,
    error_code: str | None = None,
    details: Any | None = None,
) -> JSONResponse:
    """Build a ``JSONResponse`` conforming to the unified error schema."""
    payload = {
        "error_code": error_code or _status_to_error_code(status_code),
        "message": message,
        "details": details if details is not None else {},
    }
    return JSONResponse(status_code=status_code, content=payload)


class APIError(Exception):
    """Application-level exception carrying the unified error schema."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or _status_to_error_code(status_code)
        self.details = details if details is not None else {}


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return build_error_response(
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.error_code,
        details=exc.details,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    message: str
    details: Any
    error_code: str | None = None

    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or "")
        if not message:
            message = _status_to_error_code(exc.status_code).replace("_", " ").title()
        error_code = detail.get("error_code")
        details = detail.get("details", {})
    elif isinstance(detail, str):
        message = detail
        details = {}
    else:
        message = _status_to_error_code(exc.status_code).replace("_", " ").title()
        details = {"detail": detail} if detail is not None else {}

    return build_error_response(
        status_code=exc.status_code,
        message=message,
        error_code=error_code,
        details=details,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return build_error_response(
        status_code=422,
        message="Validation error",
        error_code="VALIDATION_ERROR",
        details={"errors": exc.errors()},
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return build_error_response(
        status_code=500,
        message="Internal server error",
        error_code="INTERNAL_SERVER_ERROR",
        details={},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the unified exception handlers on a FastAPI application."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
