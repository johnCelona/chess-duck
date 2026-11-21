"""Errors the services raise for requests they cannot fulfil."""

from __future__ import annotations


class ServiceError(Exception):
    """`code` is stable and reaches clients; `status` is the HTTP status to report."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def not_found(what: str) -> ServiceError:
    return ServiceError(f"{what}.not_found", f"No such {what}", 404)
