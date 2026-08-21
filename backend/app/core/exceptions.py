"""
Global exception handling for the API.

Standardized error response schema consumed by the frontend:

    {
        "error_code": "<machine readable code>",
        "message":    "<human readable description>",
        "details":    { ...optional context... }
    }

The ``detail`` field from FastAPI's default responses is also preserved
(mirroring ``message``) so that existing clients continue to work.
"""

from __future__ import annotations

import http
import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.i18n import get_locale_from_request, translate

logger = logging.getLogger(__name__)


class AppException(Exception):
    """
    Base application exception that maps directly onto the standardized
    error response schema.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if error_code is not None:
            self.error_code = error_code
        if status_code is not None:
            self.status_code = status_code
        self.details: dict[str, Any] = details or {}
        super().__init__(self.message)


def _build_error_payload(
    *,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the canonical error payload."""
    return {
        "error_code": error_code,
        "message": message,
        "details": details or {},
        # Preserve FastAPI's default ``detail`` key for backwards compatibility.
        "detail": message,
    }


def _error_code_from_status(status_code: int) -> str:
    """Derive a snake_case error code from an HTTP status code."""
    try:
        phrase = http.HTTPStatus(status_code).phrase
    except ValueError:
        return "http_error"
    return phrase.lower().replace(" ", "_").replace("-", "_")


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    locale = get_locale_from_request(request)
    translated = translate(exc.error_code, locale)
    message = translated if translated != exc.error_code else exc.message
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload(
            error_code=exc.error_code,
            message=message,
            details=exc.details,
        ),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    locale = get_locale_from_request(request)
    detail = exc.detail
    details: dict[str, Any] = {}
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or detail)
        error_code = str(
            detail.get("error_code") or _error_code_from_status(exc.status_code)
        )
        extra = detail.get("details")
        if isinstance(extra, dict):
            details = extra
    else:
        message = (
            str(detail)
            if detail is not None
            else translate(_error_code_from_status(exc.status_code), locale)
        )
        error_code = _error_code_from_status(exc.status_code)

    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload(
            error_code=error_code,
            message=message,
            details=details,
        ),
        headers=headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    locale = get_locale_from_request(request)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_build_error_payload(
            error_code="validation_error",
            message=translate("validation_error", locale),
            details={"errors": exc.errors()},
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    locale = get_locale_from_request(request)
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_build_error_payload(
            error_code="internal_error",
            message=translate("internal_error", locale),
            details={},
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the global exception handlers on the FastAPI ``app``."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
