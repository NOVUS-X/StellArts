"""
Global exception handlers for the FastAPI application.

Ensures every error response follows the unified schema:
    {
        "error_code": str,
        "message": str,
        "details": object
    }
"""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _error_code_from_status(status_code: int) -> str:
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return f"HTTP_{status_code}"
    return phrase.upper().replace(" ", "_").replace("-", "_")


def _build_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    if details is None:
        details_payload: Any = {}
    elif isinstance(details, dict):
        details_payload = details
    else:
        details_payload = {"info": details}

    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "details": jsonable_encoder(details_payload),
        },
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    message: str
    details: Any = {}

    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("msg") or "HTTP error")
        error_code = str(
            detail.get("error_code") or _error_code_from_status(exc.status_code)
        )
        details = detail.get("details", {k: v for k, v in detail.items()
                                          if k not in {"message", "msg", "error_code", "details"}})
    else:
        message = str(detail) if detail is not None else _error_code_from_status(
            exc.status_code
        ).replace("_", " ").title()
        error_code = _error_code_from_status(exc.status_code)

    return _build_error_response(exc.status_code, error_code, message, details)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        details={"type": exc.__class__.__name__},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the given FastAPI app."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
