"""Error → HTTP translation. THE ONLY place that builds error responses (see docs/errors.md).

Every error the API returns, whatever caused it, has the same envelope:
    {"error": {"code": "<ErrorCode>", "message": "...", "details": {...}, "request_id": "..."}}
and an `X-Request-ID` header with the same id, so a bug report can be matched to its log line.

Logging policy: errors are logged once, here. 4xx → INFO (no traceback). 5xx → ERROR with traceback.
Code elsewhere raises; it doesn't log-and-raise.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.schemas import ErrorBody, ErrorResponse
from app.errors import AppError, ErrorCode

log = logging.getLogger("app.errors")

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.OUT_OF_REGION: 422,
    ErrorCode.UNKNOWN_CROP: 422,
    ErrorCode.INVALID_PRIORITIES: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.HTTP_ERROR: 400,  # nominal; the real status comes from the HTTPException
    ErrorCode.SOURCE_UNAVAILABLE: 502,
    ErrorCode.SOURCE_BAD_DATA: 502,
    ErrorCode.CACHE_MISS: 503,
    ErrorCode.CONFIG_INVALID: 500,
    ErrorCode.DOMAIN_INVARIANT: 500,
    ErrorCode.INTERNAL_ERROR: 500,
}

# 5xx codes whose message is safe and useful to show. Others get GENERIC_5XX_MESSAGE.
PUBLIC_SERVER_CODES = {
    ErrorCode.SOURCE_UNAVAILABLE,
    ErrorCode.SOURCE_BAD_DATA,
    ErrorCode.CACHE_MISS,
}
GENERIC_5XX_MESSAGE = "Unexpected server error. Share the request_id with the backend team."

_RESPONSE_DOCS: dict[int, str] = {
    404: "`not_found`: no such route",
    422: "`validation_failed`, `out_of_region`, `unknown_crop`, `invalid_priorities`",
    500: "`internal_error`, `config_invalid`, `domain_invariant`: a backend bug",
    502: "`source_unavailable`, `source_bad_data`: an external data source failed",
    503: "`cache_miss`: data_mode=cached and this location was never fetched",
}


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` for a route. Every route must declare 500; routes with input add 422."""
    return {
        s: {"model": ErrorResponse, "description": _RESPONSE_DOCS[s]}
        for s in sorted({500, *statuses})
    }


# ---------------------------------------------------------------- request id
class RequestIdMiddleware:
    """Gives every request an id (reuses a safe incoming X-Request-ID) and echoes it back."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        rid = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = rid

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).setdefault(REQUEST_ID_HEADER, rid)
            await send(message)

        await self.app(scope, receive, send_with_id)


def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) else uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- envelope
def error_response(
    request: Request,
    *,
    status: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    rid = request_id(request)
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details or {}, request_id=rid)
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers={**(headers or {}), REQUEST_ID_HEADER: rid},
    )


def _log(request: Request, status: int, code: ErrorCode, message: str, exc: BaseException) -> None:
    args = (request.method, request.url.path, status, code.value, request_id(request), message)
    if status >= 500:
        log.error("%s %s -> %s %s request_id=%s: %s", *args, exc_info=exc)
    else:
        log.info("%s %s -> %s %s request_id=%s: %s", *args)


# ---------------------------------------------------------------- handlers
def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        return handle_unexpected(request, exc)
    status = STATUS_BY_CODE[exc.code]
    _log(request, status, exc.code, exc.message, exc)
    if status >= 500 and exc.code not in PUBLIC_SERVER_CODES:
        return error_response(request, status=status, code=exc.code, message=GENERIC_5XX_MESSAGE)
    return error_response(
        request, status=status, code=exc.code, message=exc.message, details=exc.details
    )


def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    errors: Iterable[Any] = exc.errors() if isinstance(exc, RequestValidationError) else []
    fields = [
        {
            "loc": ".".join(str(part) for part in e.get("loc", ())),
            "message": str(e.get("msg", "")),
            "type": str(e.get("type", "")),
        }
        for e in errors
    ]
    code = ErrorCode.VALIDATION_FAILED
    message = "Request is invalid: " + "; ".join(f"{f['loc']}: {f['message']}" for f in fields)
    _log(request, 422, code, message, exc)
    return error_response(
        request, status=422, code=code, message=message, details={"fields": fields}
    )


def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return handle_unexpected(request, exc)
    status = exc.status_code
    if status == 404:
        code, message = ErrorCode.NOT_FOUND, f"No route {request.method} {request.url.path}"
    elif status == 405:
        code, message = ErrorCode.METHOD_NOT_ALLOWED, f"{request.method} is not allowed here"
    else:
        code, message = ErrorCode.HTTP_ERROR, str(exc.detail)
    _log(request, status, code, message, exc)
    return error_response(
        request, status=status, code=code, message=message, headers=dict(exc.headers or {})
    )


def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: a bug. Logs the traceback, returns a generic message (never internals)."""
    code = ErrorCode.INTERNAL_ERROR
    _log(request, 500, code, f"{type(exc).__name__}: {exc}", exc)
    return error_response(request, status=500, code=code, message=GENERIC_5XX_MESSAGE)


class UnhandledErrorMiddleware:
    """Turns any uncaught exception into the standard 500 envelope.

    Why not `add_exception_handler(Exception, ...)`: Starlette runs that handler in its outermost
    ServerErrorMiddleware, i.e. outside CORS (the browser can't read the response), and it re-raises
    afterwards (the traceback gets logged twice). This middleware sits inside CORS and logs once,
    via handle_unexpected.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            if started:  # too late to send an error body; let the server close the connection
                raise
            response = handle_unexpected(Request(scope), exc)
            await response(scope, receive, send)


def install_error_handling(app: FastAPI) -> None:
    """Order matters: add_middleware wraps outward, so call this BEFORE adding CORSMiddleware."""
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
