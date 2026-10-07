"""Typed application errors → consistent JSON error envelope.

All API errors look like::

    {"code": "DOCUMENT_NOT_FOUND", "message": "...", "request_id": "..."}

Raise ``AppError`` (or a subclass) from services/repositories; the
registered FastAPI handlers turn them into HTTP responses. Stack traces
never reach the client — they go to structured logs only.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("vectorbrain.errors")


class AppError(Exception):
    """Base class for expected, user-facing failures."""

    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."
    status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    code = "NOT_FOUND"
    message = "The requested resource was not found."
    status_code = 404


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    message = "The request was invalid."
    status_code = 422


class ServiceUnavailableError(AppError):
    code = "SERVICE_UNAVAILABLE"
    message = "A required service is currently unavailable."
    status_code = 503


def error_envelope(
    code: str,
    message: str,
    request_id: str | None,
    details: dict | None = None,
) -> dict:
    envelope: dict = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        envelope["details"] = details
    return envelope


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(exc.code, exc.message, request_id, exc.details),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Map framework HTTP errors (404 no-route, 405, …) to the same envelope."""
    request_id = getattr(request.state, "request_id", None)
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
        exc.status_code, f"HTTP_{exc.status_code}"
    )
    message = exc.detail if isinstance(exc.detail, str) else code
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(code, message, request_id),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: never leak tracebacks to the client."""
    request_id = getattr(request.state, "request_id", None)
    # The client gets a generic message; the traceback goes to the logs so
    # production 500s are observable and debuggable.
    logger.exception(
        "unhandled error on %s %s (request_id=%s)",
        request.method,
        request.url.path,
        request_id,
    )
    return JSONResponse(
        status_code=500,
        content=error_envelope(
            "INTERNAL_ERROR", "An unexpected error occurred.", request_id
        ),
    )
