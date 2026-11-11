"""The project's error catalog. THE ONLY place exception classes may be defined.

Rules (full guide: docs/errors.md; enforced by tests/test_error_policy.py):
- Raise only the concrete classes below: never built-ins (ValueError…) or HTTPException.
  Exception: Pydantic validators raise ValueError, which Pydantic turns into a validation error.
- Every class has a stable `code` (ErrorCode). The frontend switches on the code, not the message.
- `message`: plain English, safe to show. No secrets, no URLs with keys, no stack traces.
- `details` is a small JSON-serializable dict with machine-readable context (ids, values, limits).
- Wrapping another exception? Always `raise NewError(...) from e`.

This module is pure stdlib with no HTTP knowledge, so every layer (domain included) can import it.
HTTP status codes live in app/api/errors.py.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, ClassVar


class ErrorCode(StrEnum):
    """Stable machine-readable codes. New code = new class + docs/errors.md row + contract enum."""

    # Client errors (the request can be fixed by the caller)
    VALIDATION_FAILED = "validation_failed"
    OUT_OF_REGION = "out_of_region"
    UNKNOWN_CROP = "unknown_crop"
    INVALID_PRIORITIES = "invalid_priorities"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    HTTP_ERROR = "http_error"
    # Data source errors (an upstream dependency failed)
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_BAD_DATA = "source_bad_data"
    CACHE_MISS = "cache_miss"
    # Server errors (a bug or bad deployment; the caller can't fix it)
    CONFIG_INVALID = "config_invalid"
    DOMAIN_INVARIANT = "domain_invariant"
    INTERNAL_ERROR = "internal_error"


class AppError(Exception):
    """Base of every project error. Abstract: raise a subclass."""

    code: ClassVar[ErrorCode]

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details or {})

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# ---------------------------------------------------------------- client errors (abstract base)
class InvalidInputError(AppError):
    """The request is well-formed but not acceptable for the MVP scope. Abstract."""


class OutOfRegionError(InvalidInputError):
    code = ErrorCode.OUT_OF_REGION


class UnknownCropError(InvalidInputError):
    code = ErrorCode.UNKNOWN_CROP


class InvalidPrioritiesError(InvalidInputError):
    code = ErrorCode.INVALID_PRIORITIES


# ---------------------------------------------- data source errors (abstract base)
class SourceError(AppError):
    """An external data source failed. Abstract. Catch this to handle any source failure."""


class SourceUnavailableError(SourceError):
    """Network error, timeout or non-2xx status from the source."""

    code = ErrorCode.SOURCE_UNAVAILABLE


class SourceDataError(SourceError):
    """The source answered, but the payload is unusable (wrong shape, fill values, bad rows)."""

    code = ErrorCode.SOURCE_BAD_DATA


class CacheMissError(SourceError):
    """data_mode=cached and the requested data was never fetched."""

    code = ErrorCode.CACHE_MISS


# ---------------------------------------------------------------- server errors
class ConfigError(AppError):
    """config/mvp.yaml, .env or a local data file is invalid. Raised at startup."""

    code = ErrorCode.CONFIG_INVALID


class DomainInvariantError(AppError):
    """Domain logic received impossible inputs (a bug upstream, not a user mistake)."""

    code = ErrorCode.DOMAIN_INVARIANT


ABSTRACT_ERRORS: tuple[type[AppError], ...] = (AppError, InvalidInputError, SourceError)
