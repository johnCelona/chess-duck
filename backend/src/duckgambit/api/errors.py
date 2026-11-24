"""One error format for the whole API: RFC 9457 problems with stable codes (ADR-0002).

Internal exception text and filesystem paths never reach a client; they go to the log.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from duckgambit.api.schemas.base import FieldError, Problem
from duckgambit.domain.errors import DomainError
from duckgambit.services.errors import ServiceError
from duckgambit.services.ports import EngineError

log = logging.getLogger(__name__)

PROBLEM_JSON = "application/problem+json"

_ENGINE_STATUS = {
    "engine.not_installed": 409,
    "engine.unknown": 404,
    "engine.unsupported_platform": 409,
    "engine.timeout": 504,
    "engine.failed": 502,
    "engine.start_failed": 502,
    "engine.not_running": 502,
    "engine.no_result": 502,
    "engine.checksum_mismatch": 502,
    "engine.download_failed": 502,
    "engine.download_too_large": 502,
    "engine.unsafe_archive": 502,
    "engine.smoke_test_failed": 502,
    "engine.install_failed": 500,
}

_TITLES = {
    400: "Bad request",
    401: "Not authorised",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    413: "Request too large",
    415: "Unsupported media type",
    422: "Invalid request",
    500: "Internal error",
    502: "Engine problem",
    504: "Engine timed out",
}


def problem(
    status: int,
    code: str,
    detail: str | None = None,
    errors: list[FieldError] | None = None,
    title: str | None = None,
) -> JSONResponse:
    body = Problem(
        title=title or _TITLES.get(status, "Error"),
        status=status,
        code=code,
        detail=detail,
        errors=errors or [],
    )
    return JSONResponse(body.model_dump(by_alias=True), status_code=status, media_type=PROBLEM_JSON)


PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    "default": {"model": Problem, "description": "Any error, as an RFC 9457 problem document"}
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return problem(exc.status, exc.code, exc.message)

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return problem(422, exc.code, exc.message)

    @app.exception_handler(EngineError)
    async def engine_error(_: Request, exc: EngineError) -> JSONResponse:
        return problem(_ENGINE_STATUS.get(exc.code, 422), exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            FieldError(
                location=".".join(str(part) for part in error.get("loc", ())),
                message=str(error.get("msg", "invalid")),
            )
            for error in exc.errors()
        ]
        return problem(422, "request.invalid", "The request is not valid", errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "request.not_found", 405: "request.method_not_allowed"}.get(
            exc.status_code, "request.failed"
        )
        return problem(exc.status_code, code)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return problem(500, "internal", "Something went wrong. The details are in the server log.")
