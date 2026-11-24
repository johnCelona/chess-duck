"""Request-boundary checks (ADR-0011).

The service is local and has no accounts, so the browser is the main attack path:
a hostile page must not be able to call the API. Four rules do that:

1. Host allowlist: defeats DNS rebinding.
2. Origin check: a request that names an origin must come from this app or an allowed one.
3. State-changing requests must be JSON: a cross-site form post cannot be.
4. Optional launch token: required on every request when configured (sidecar mode).
"""

from __future__ import annotations

import hmac
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from duckgambit.api.errors import problem
from duckgambit.settings import Settings

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})
MAX_BODY_BYTES = 8 * 1024 * 1024
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH"})


def _hostname(host_header: str) -> str:
    host = host_header.strip().lower()
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if ":" in host else host


class BoundaryMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self._app = app
        self._hosts = LOOPBACK_HOSTS | {host.lower() for host in settings.allowed_hosts}
        self._origins = {origin.rstrip("/").lower() for origin in settings.origins}
        token = settings.api_token.get_secret_value() if settings.api_token else None
        self._token = token.encode() if token else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        method = scope["method"]
        rejection = self._check(method, scope["path"], headers)
        if rejection is not None:
            await rejection(scope, receive, send)
            return
        await self._app(scope, receive, send)

    def _check(self, method: str, path: str, headers: Headers) -> ASGIApp | None:
        host = headers.get("host", "")
        if _hostname(host) not in self._hosts:
            return problem(403, "request.host_not_allowed", "This host name is not allowed")

        origin = headers.get("origin")
        if origin is not None and not self._origin_allowed(origin, host):
            return problem(403, "request.origin_not_allowed", "This origin is not allowed")

        if method == "OPTIONS" or not path.startswith("/api/"):
            return None

        if self._token is not None:
            scheme, _, supplied = headers.get("authorization", "").partition(" ")
            if scheme.lower() != "bearer" or not hmac.compare_digest(
                supplied.strip().encode(), self._token
            ):
                return problem(401, "request.unauthorised", "A valid API token is required")

        if method in UNSAFE_METHODS:
            content_type = headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type != "application/json":
                return problem(415, "request.json_required", "Send Content-Type: application/json")
            length = headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
                return problem(413, "request.too_large", "The request body is too large")
        return None

    def _origin_allowed(self, origin: str, host: str) -> bool:
        normalised = origin.rstrip("/").lower()
        if normalised in self._origins:
            return True
        parts = urlsplit(normalised)
        # Same origin: the page was served from the address it is calling.
        return parts.scheme in {"http", "https"} and parts.netloc == host.strip().lower()
