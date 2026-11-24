"""In-memory stand-ins for Lichess and the secret store. The only adapters until M6."""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import urlencode

from duckgambit.services.lichess import (
    GameQuery,
    ImportedGame,
    LichessAccount,
    LichessError,
)

FAKE_TOKEN = "fake-token"  # noqa: S105 - a test value, not a credential


class FakeLichess:
    """Behaves like the parts of Lichess we will use, without any network."""

    def __init__(self, username: str = "duck_trainer", games: tuple[str, ...] = ()) -> None:
        self.username = username
        self.games = list(games)
        self.imported: list[str] = []
        self.revoked: list[str] = []
        self._codes: dict[str, str] = {}

    def authorization_url(self, state: str, code_challenge: str, redirect_uri: str) -> str:
        self._codes["fake-code"] = code_challenge
        query = urlencode(
            {
                "response_type": "code",
                "client_id": "duck-gambit",
                "redirect_uri": redirect_uri,
                "code_challenge_method": "S256",
                "code_challenge": code_challenge,
                "state": state,
            }
        )
        return f"https://lichess.invalid/oauth?{query}"

    async def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> str:
        if code not in self._codes or not code_verifier:
            raise LichessError("lichess.bad_code", "The authorization code is not valid")
        return FAKE_TOKEN

    def _check(self, token: str | None) -> None:
        if token is not None and (token != FAKE_TOKEN or token in self.revoked):
            raise LichessError("lichess.unauthorised", "The Lichess link has expired")

    async def account(self, token: str) -> LichessAccount:
        self._check(token)
        return LichessAccount(self.username.lower(), self.username)

    async def export_games(
        self, username: str, query: GameQuery, token: str | None = None
    ) -> AsyncIterator[str]:
        self._check(token)
        if username.lower() != self.username.lower():
            raise LichessError("lichess.user_not_found", "No such Lichess user")
        for pgn in self.games[: query.max_games]:
            yield pgn

    async def import_game(self, pgn: str, token: str | None = None) -> ImportedGame:
        self._check(token)
        if pgn not in self.imported:  # Lichess deduplicates identical PGNs
            self.imported.append(pgn)
        game_id = f"fake{self.imported.index(pgn):04d}"
        return ImportedGame(game_id, f"https://lichess.invalid/{game_id}")

    async def revoke(self, token: str) -> None:
        self.revoked.append(token)


class MemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self._values.get(name)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value

    def delete(self, name: str) -> None:
        self._values.pop(name, None)
