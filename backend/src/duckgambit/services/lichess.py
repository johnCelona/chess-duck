"""The Lichess port (ADR-0010). Optional, off by default, faked in tests.

STUB FOR M6. Only the seam exists: the Protocols below and a fake adapter. No HTTP
adapter, no OAuth routes, no token is ever stored yet.

Rules any real adapter must follow (Lichess API terms, verified 2026-11-21):
- one request at a time; after HTTP 429 wait at least a minute
- every request carries a User-Agent that names this application
- tokens go through SecretStore only: never the database, logs or any API response
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

LICHESS_SCOPES: tuple[str, ...] = ()  # identity, game export and game import need none


@dataclass(frozen=True)
class LichessAccount:
    id: str
    username: str


@dataclass(frozen=True)
class GameQuery:
    max_games: int = 100
    since_ms: int | None = None
    perf_types: tuple[str, ...] = ()
    color: str | None = None
    rated_only: bool = False


@dataclass(frozen=True)
class ImportedGame:
    id: str
    url: str


class LichessError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LichessPort(Protocol):
    def authorization_url(self, state: str, code_challenge: str, redirect_uri: str) -> str:
        """Where to send the player to approve the link (OAuth2 with PKCE, no client secret)."""
        ...

    async def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> str:
        """Trade the authorization code for an access token."""
        ...

    async def account(self, token: str) -> LichessAccount: ...

    def export_games(
        self, username: str, query: GameQuery, token: str | None = None
    ) -> AsyncIterator[str]:
        """The player's games as PGN, most recent first. Public games need no token."""
        ...

    async def import_game(self, pgn: str, token: str | None = None) -> ImportedGame:
        """Save one game to Lichess. Imported games are public and unrated."""
        ...

    async def revoke(self, token: str) -> None: ...


class SecretStore(Protocol):
    """Where third-party tokens live: the OS credential store, never the database."""

    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...
