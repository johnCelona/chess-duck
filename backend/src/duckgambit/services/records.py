"""Stored shapes that are not domain concepts: envelopes, matches, games, moves, jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from duckgambit.domain.arena import Arena
from duckgambit.domain.rating import Rating


@dataclass(frozen=True)
class Envelope:
    """An event as stored and streamed (ADR-0002). `data` is deterministic; the rest is not."""

    cursor: int
    stream: str
    seq: int
    type: str
    recorded_at: str
    data: dict[str, Any]


@dataclass(frozen=True)
class MatchRecord:
    id: str
    profile_id: str
    duck_ids: tuple[str, ...]
    arena: Arena
    mode: str  # "duck-vs-duck" now; modes with a human participant come later
    rated: bool
    state: str  # created | running | finished | cancelled | failed
    context_id: str
    job_id: str
    created_at: str
    finished_at: str | None = None
    scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class GameRecord:
    id: str
    match_id: str
    index: int
    white_duck_id: str
    black_duck_id: str
    seed: int
    initial_fen: str
    state: str  # running | finished
    white_clock_ms: int | None
    black_clock_ms: int | None
    started_at: str
    result: str | None = None
    termination: str | None = None
    pgn: str | None = None
    finished_at: str | None = None


@dataclass(frozen=True)
class MoveRecord:
    game_id: str
    ply: int
    color: str
    uci: str
    san: str
    source: str
    cp: int | None
    mate: int | None
    nodes: int
    depth: int
    think_ms: int
    clock_ms: int | None
    fen_after: str
    event_seq: int


@dataclass(frozen=True)
class JobRecord:
    id: str
    kind: str
    state: str  # queued | running | succeeded | failed | cancelled | interrupted
    params: dict[str, Any]
    done: int
    total: int
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None
    error_detail: str | None = None

    @property
    def finished(self) -> bool:
        return self.state in {"succeeded", "failed", "cancelled", "interrupted"}

    @property
    def resumable(self) -> bool:
        return self.state in {"failed", "cancelled", "interrupted"}


@dataclass(frozen=True)
class RatingRecord:
    duck_id: str
    context_id: str
    kind: str  # "game" | "puzzle"
    rating: Rating
    updated_at: str


@dataclass(frozen=True)
class EngineProfile:
    engine_id: str
    name: str
    nodes: int
    multipv: int
    hash_mb: int
