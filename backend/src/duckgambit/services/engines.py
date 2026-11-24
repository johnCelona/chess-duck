"""Engine management and diagnostics (spec section 9).

Safety rules (ADR-0011): no raw UCI ever reaches an engine; the only option a user can
set is Hash, clamped by the pool's budget; options that take file paths or write files
are never settable.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Protocol

from duckgambit.domain.chessutil import board_from, parse_move
from duckgambit.domain.engine_types import MAX_MULTIPV, EngineOption, SearchRequest
from duckgambit.services.errors import ServiceError, not_found
from duckgambit.services.events import iso
from duckgambit.services.ports import Clock, EnginePool, Store
from duckgambit.services.records import EngineProfile

USER_SETTABLE_OPTIONS = frozenset({"Hash"})
PROFILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,39}$")
MAX_DIAGNOSTIC_NODES = 5_000_000
MAX_HASH_MB = 1024


@dataclass(frozen=True)
class EngineListing:
    id: str
    name: str
    version: str
    license: str
    homepage: str
    source_url: str
    status: str  # installed | not_installed | installing | unavailable
    fingerprint: str | None


class EngineAdmin(Protocol):
    """Install, remove and list engines. Implemented over the manifest and the data directory."""

    def listings(self) -> list[EngineListing]: ...
    def known(self, engine_id: str) -> bool: ...
    async def install(self, engine_id: str) -> None: ...
    async def remove(self, engine_id: str) -> None: ...


@dataclass(frozen=True)
class DescribedOption:
    option: EngineOption
    user_settable: bool


@dataclass(frozen=True)
class AnalysisLine:
    move: str
    san: str
    cp: int | None
    mate: int | None
    wdl: tuple[int, int, int] | None
    pv: tuple[str, ...]


@dataclass(frozen=True)
class Analysis:
    engine_name: str
    depth: int
    nodes: int
    lines: tuple[AnalysisLine, ...]


def is_user_settable(option: EngineOption) -> bool:
    """Only allowlisted numeric options. Anything string-typed (paths, files) never is."""
    return option.name in USER_SETTABLE_OPTIONS and option.type == "spin"


class EngineService:
    def __init__(self, admin: EngineAdmin, pool: EnginePool, store: Store, clock: Clock) -> None:
        self._admin = admin
        self._pool = pool
        self._store = store
        self._clock = clock

    def _require(self, engine_id: str) -> None:
        if not self._admin.known(engine_id):
            raise not_found("engine")

    def all(self) -> list[EngineListing]:
        return self._admin.listings()

    def get(self, engine_id: str) -> EngineListing:
        self._require(engine_id)
        return next(listing for listing in self._admin.listings() if listing.id == engine_id)

    async def install(self, engine_id: str) -> EngineListing:
        self._require(engine_id)
        await self._pool.release_engine(engine_id)
        await self._admin.install(engine_id)
        return self.get(engine_id)

    async def remove(self, engine_id: str) -> EngineListing:
        self._require(engine_id)
        await self._pool.release_engine(engine_id)
        await self._admin.remove(engine_id)
        return self.get(engine_id)

    async def options(self, engine_id: str) -> list[DescribedOption]:
        self._require(engine_id)
        async with self._pool.lease(engine_id) as engine:
            info = await engine.describe()
        return [DescribedOption(option, is_user_settable(option)) for option in info.options]

    async def analyse(
        self, engine_id: str, fen: str, nodes: int, multipv: int, hash_mb: int = 16
    ) -> Analysis:
        """A diagnostic search ("Test engine"). Never used for results that count."""
        self._require(engine_id)
        if not 1 <= hash_mb <= MAX_HASH_MB:
            raise ServiceError("engine.hash", f"hashMb must be between 1 and {MAX_HASH_MB}")
        request = SearchRequest(fen, (), multipv=multipv, nodes=nodes)
        request.validate(MAX_DIAGNOSTIC_NODES)
        board = board_from(fen)
        if board.is_game_over():
            raise ServiceError(
                "engine.position_over", "There is nothing to search: the game is over"
            )
        async with self._pool.lease(engine_id, hash_mb) as engine:
            info = await engine.describe()
            result = await engine.search(request)
        lines = tuple(
            AnalysisLine(
                move=candidate.move,
                san=board.san(parse_move(board, candidate.move)),
                cp=candidate.cp,
                mate=candidate.mate,
                wdl=candidate.wdl,
                pv=candidate.pv,
            )
            for candidate in result.candidates
        )
        return Analysis(info.name, result.depth, result.nodes, lines)

    async def profiles(self, engine_id: str) -> list[EngineProfile]:
        self._require(engine_id)
        return await asyncio.to_thread(self._store.engine_profiles.list_for, engine_id)

    async def save_profile(self, profile: EngineProfile) -> EngineProfile:
        self._require(profile.engine_id)
        if not PROFILE_NAME.match(profile.name):
            raise ServiceError(
                "engine.profile_name",
                "Profile names are 1 to 40 letters, digits, spaces, hyphens or underscores",
            )
        if not 1 <= profile.hash_mb <= MAX_HASH_MB:
            raise ServiceError("engine.hash", f"hashMb must be between 1 and {MAX_HASH_MB}")
        if not 1 <= profile.nodes <= MAX_DIAGNOSTIC_NODES:
            raise ServiceError(
                "search.limit", f"nodes must be between 1 and {MAX_DIAGNOSTIC_NODES}"
            )
        if not 1 <= profile.multipv <= MAX_MULTIPV:
            raise ServiceError("search.multipv", f"multiPV must be between 1 and {MAX_MULTIPV}")
        await asyncio.to_thread(self._store.engine_profiles.save, profile, iso(self._clock))
        return profile
