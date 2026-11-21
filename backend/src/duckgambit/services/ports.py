"""Ports: what the services need from the outside world. Adapters implement these.

Everything here is a Protocol, so tests can substitute fakes and no service imports
a database driver, a subprocess or an HTTP client.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from datetime import datetime
from typing import Any, Protocol

from duckgambit.domain.arena import RatingContext
from duckgambit.domain.duck import Duck
from duckgambit.domain.engine_types import (
    EngineIdentity,
    EngineInfo,
    SearchRequest,
    SearchResult,
)
from duckgambit.domain.rating import Rating
from duckgambit.services.records import (
    EngineProfile,
    Envelope,
    GameRecord,
    JobRecord,
    MatchRecord,
    MoveRecord,
    RatingRecord,
)


class EngineError(Exception):
    """An engine could not do what was asked. `code` is stable and reaches clients."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Engine(Protocol):
    """One exclusive engine. Duck search, Judge and Defender are leases with different settings."""

    async def describe(self) -> EngineInfo: ...

    async def search(self, request: SearchRequest) -> SearchResult:
        """A stateless search: the engine is reset first, so only the request matters."""
        ...


class EnginePool(Protocol):
    def lease(self, engine_id: str, hash_mb: int = 16) -> AbstractAsyncContextManager[Engine]:
        """Borrow an engine. Waits when the process budget is used up."""
        ...

    async def identity(self, engine_id: str) -> EngineIdentity | None:
        """Which binary would serve this engine id, or None when it is not installed."""
        ...

    async def release_engine(self, engine_id: str) -> None:
        """Stop every idle process of this engine (before reinstalling or removing it)."""
        ...

    async def close(self) -> None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def new(self, prefix: str) -> str: ...


class ProfileRepository(Protocol):
    def ensure_default(self, now: str) -> str: ...


class DuckRepository(Protocol):
    def add(self, duck: Duck) -> None: ...
    def get(self, duck_id: str) -> Duck | None: ...
    def list_for(self, profile_id: str) -> list[Duck]: ...


class EventStore(Protocol):
    def append(
        self, stream: str, events: Sequence[tuple[str, dict[str, Any]]], recorded_at: str
    ) -> list[Envelope]: ...

    def read(self, streams: Sequence[str], after: int, limit: int) -> list[Envelope]: ...


class MatchRepository(Protocol):
    def add_match(self, match: MatchRecord) -> None: ...
    def get_match(self, match_id: str) -> MatchRecord | None: ...
    def list_matches(self, profile_id: str, limit: int) -> list[MatchRecord]: ...
    def set_match_state(
        self,
        match_id: str,
        state: str,
        finished_at: str | None = None,
        scores: dict[str, float] | None = None,
    ) -> None: ...

    def add_game(self, game: GameRecord) -> None: ...
    def get_game(self, game_id: str) -> GameRecord | None: ...
    def list_games(self, match_id: str) -> list[GameRecord]: ...
    def add_move(
        self, move: MoveRecord, white_clock_ms: int | None, black_clock_ms: int | None
    ) -> None: ...
    def list_moves(self, game_id: str) -> list[MoveRecord]: ...
    def finish_game(
        self, game_id: str, result: str, termination: str, pgn: str, finished_at: str
    ) -> None: ...


class JobRepository(Protocol):
    def add(self, job: JobRecord) -> None: ...
    def get(self, job_id: str) -> JobRecord | None: ...
    def save(self, job: JobRecord) -> None: ...
    def list_unfinished(self) -> list[JobRecord]: ...


class RatingRepository(Protocol):
    def save_context(self, context: RatingContext, now: str) -> None: ...
    def get(self, duck_id: str, context_id: str, kind: str) -> Rating | None: ...
    def save(self, record: RatingRecord, game_id: str | None) -> None: ...
    def list_for_duck(self, duck_id: str) -> list[RatingRecord]: ...


class EngineProfileRepository(Protocol):
    def list_for(self, engine_id: str) -> list[EngineProfile]: ...
    def save(self, profile: EngineProfile, now: str) -> None: ...


class Store(Protocol):
    """All repositories plus a way to make several writes atomic."""

    @property
    def profiles(self) -> ProfileRepository: ...
    @property
    def ducks(self) -> DuckRepository: ...
    @property
    def events(self) -> EventStore: ...
    @property
    def matches(self) -> MatchRepository: ...
    @property
    def jobs(self) -> JobRepository: ...
    @property
    def ratings(self) -> RatingRepository: ...
    @property
    def engine_profiles(self) -> EngineProfileRepository: ...

    def atomic(self) -> AbstractContextManager[None]:
        """Everything written inside the block commits together or not at all."""
        ...
