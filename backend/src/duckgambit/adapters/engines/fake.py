"""A deterministic in-process engine for tests and for demos without Stockfish.

It plays nonsense chess, but reproducibly: a move's score is a hash of the position and
the move, and it always sees mate in one. Nothing here starts a process.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import chess

from duckgambit.domain.chessutil import board_from, position_key
from duckgambit.domain.engine_types import (
    Candidate,
    EngineIdentity,
    EngineInfo,
    EngineOption,
    SearchRequest,
    SearchResult,
)
from duckgambit.services.engines import EngineListing
from duckgambit.services.ports import Engine, EngineError

FAKE_IDENTITY = EngineIdentity("fake", "Fake engine", "1", "fake")
MAX_NODES = 5_000_000


def fake_score(board: chess.Board, move: chess.Move) -> int:
    digest = hashlib.sha256(f"{position_key(board)}|{move.uci()}".encode()).digest()
    return int.from_bytes(digest[:2], "big") % 201 - 100


def fake_candidates(board: chess.Board, multipv: int) -> tuple[Candidate, ...]:
    scored = []
    for move in board.legal_moves:
        after = board.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            scored.append((10_000, Candidate(move.uci(), None, 1, (1000, 0, 0), 1, (move.uci(),))))
            continue
        cp = fake_score(board, move)
        win = max(0, min(1000, 500 + cp * 2))
        wdl = (win, 0, 1000 - win)
        scored.append((cp, Candidate(move.uci(), cp, None, wdl, 1, (move.uci(),))))
    scored.sort(key=lambda item: (-item[0], item[1].move))
    return tuple(candidate for _, candidate in scored[:multipv])


class FakeEngine:
    def __init__(self) -> None:
        self.searches: list[SearchRequest] = []

    async def describe(self) -> EngineInfo:
        return EngineInfo(
            "Fake engine 1",
            (
                EngineOption("Hash", "spin", 16, 1, 1024, ()),
                EngineOption("Threads", "spin", 1, 1, 1, ()),
            ),
        )

    async def search(self, request: SearchRequest) -> SearchResult:
        request.validate(MAX_NODES)
        self.searches.append(request)
        board = board_from(request.initial_fen, request.moves)
        candidates = fake_candidates(board, request.multipv)
        if not candidates:
            raise EngineError("engine.no_result", "No legal moves to search")
        return SearchResult(candidates, nodes=request.nodes or 0, depth=1)


class FakeEnginePool:
    """An EnginePool that hands out fake engines. Any engine id is 'installed'."""

    def __init__(self) -> None:
        self.leases = 0

    @asynccontextmanager
    async def lease(self, engine_id: str, hash_mb: int = 16) -> AsyncIterator[Engine]:
        self.leases += 1
        yield FakeEngine()

    async def identity(self, engine_id: str) -> EngineIdentity | None:
        return EngineIdentity(engine_id, FAKE_IDENTITY.name, FAKE_IDENTITY.version, "fake")

    async def release_engine(self, engine_id: str) -> None:
        return None

    async def close(self) -> None:
        return None


class FakeEngineAdmin:
    """Lists one always-installed fake engine (DG_FAKE_ENGINE=true)."""

    def known(self, engine_id: str) -> bool:
        return engine_id == FAKE_IDENTITY.id

    def listings(self) -> list[EngineListing]:
        return [
            EngineListing(
                id=FAKE_IDENTITY.id,
                name=FAKE_IDENTITY.name,
                version=FAKE_IDENTITY.version,
                license="GPL-3.0-or-later",
                homepage="https://github.com/",
                source_url="https://github.com/",
                status="installed",
                fingerprint=FAKE_IDENTITY.fingerprint,
            )
        ]

    async def install(self, engine_id: str) -> None:
        return None

    async def remove(self, engine_id: str) -> None:
        raise EngineError("engine.builtin", "The fake engine cannot be removed")
