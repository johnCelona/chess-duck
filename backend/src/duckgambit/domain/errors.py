"""The one exception type the domain raises. Codes are stable and reach clients."""

from __future__ import annotations


class DomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
