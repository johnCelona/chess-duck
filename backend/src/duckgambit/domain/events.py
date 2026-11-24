"""Semantic events (ADR-0002). The domain says what happened; clients decide how to show it.

Event data is deterministic for a given seed. The envelope (cursor, seq, recordedAt) is
added by the service layer. Wire schemas in `api/schemas/events.py` mirror these classes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from duckgambit.domain.decision import Reason, ScoredCandidate


@dataclass(frozen=True)
class Event:
    type: ClassVar[str]

    def data(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DuckHatched(Event):
    type: ClassVar[str] = "DuckHatched"
    duck_id: str
    name: str
    species: str
    stage: str
    level: int
    stats: dict[str, int]
    egg_seed: int | None = None


@dataclass(frozen=True)
class MatchCreated(Event):
    type: ClassVar[str] = "MatchCreated"
    match_id: str
    duck_ids: tuple[str, ...]
    games: int
    mode: str
    rated: bool


@dataclass(frozen=True)
class MatchStarted(Event):
    type: ClassVar[str] = "MatchStarted"
    match_id: str


@dataclass(frozen=True)
class GameStarted(Event):
    type: ClassVar[str] = "GameStarted"
    match_id: str
    game_id: str
    index: int
    white_duck_id: str
    black_duck_id: str
    initial_fen: str
    white_clock_ms: int | None
    black_clock_ms: int | None


@dataclass(frozen=True)
class MoveChosen(Event):
    """The thinking panel's data: what the duck considered and why it chose."""

    type: ClassVar[str] = "MoveChosen"
    game_id: str
    ply: int
    duck_id: str
    color: str
    fen_before: str
    move: str
    san: str
    source: str
    candidates: tuple[ScoredCandidate, ...]
    reasons: tuple[Reason, ...]
    think_ms: int
    nodes_budget: int
    nodes: int
    depth: int


@dataclass(frozen=True)
class MoveMade(Event):
    """Everything a client without chess rules needs to show the move."""

    type: ClassVar[str] = "MoveMade"
    game_id: str
    ply: int
    color: str
    by: str  # "duck" now; "human" is reserved for sparring and bullet battle
    duck_id: str | None
    uci: str
    san: str
    fen_after: str
    capture: bool
    en_passant: bool
    check: bool
    checkmate: bool
    castle: str | None
    promotion: str | None
    think_ms: int
    white_clock_ms: int | None
    black_clock_ms: int | None


@dataclass(frozen=True)
class GameFinished(Event):
    type: ClassVar[str] = "GameFinished"
    match_id: str
    game_id: str
    result: str
    termination: str
    winner_duck_id: str | None
    plies: int


@dataclass(frozen=True)
class DuckScore:
    duck_id: str
    points: float


@dataclass(frozen=True)
class MatchFinished(Event):
    type: ClassVar[str] = "MatchFinished"
    match_id: str
    scores: tuple[DuckScore, ...]
    winner_duck_id: str | None


@dataclass(frozen=True)
class SeriesUpdated(Event):
    """Where a best-of series stands. Emitted at the start and after every game of a series
    (never for a plain match). `state` is "armageddon" when the next game is the tie-break."""

    type: ClassVar[str] = "SeriesUpdated"
    match_id: str
    best_of: int
    scores: tuple[DuckScore, ...]
    games_played: int
    state: str  # "playing" | "armageddon" | "decided"
    winner_duck_id: str | None
    decided_by: str | None  # "games" | "armageddon"
    armageddon_white_duck_id: str | None


@dataclass(frozen=True)
class RatingUpdated(Event):
    type: ClassVar[str] = "RatingUpdated"
    duck_id: str
    context_id: str
    kind: str
    before: float
    after: float
    deviation: float
    games: int
    provisional: bool


@dataclass(frozen=True)
class JobProgressed(Event):
    type: ClassVar[str] = "JobProgressed"
    job_id: str
    state: str
    done: int
    total: int


@dataclass(frozen=True)
class JobFinished(Event):
    type: ClassVar[str] = "JobFinished"
    job_id: str
    state: str
    error_code: str | None


# ----- Training (emitted by domain.lessons; services arrive in M2 and M5) -------------


@dataclass(frozen=True)
class LessonCompleted(Event):
    type: ClassVar[str] = "LessonCompleted"
    duck_id: str
    lesson_id: str
    kind: str
    xp: int


@dataclass(frozen=True)
class KnowledgeAdded(Event):
    type: ClassVar[str] = "KnowledgeAdded"
    duck_id: str
    lesson_id: str
    target: str  # "repertoire" | "puzzle_memory"
    entries: int


@dataclass(frozen=True)
class XpGained(Event):
    """A duck earned experience. `source` says from what (e.g. "match")."""

    type: ClassVar[str] = "XpGained"
    duck_id: str
    amount: int
    source: str
    xp_after: int
    level: int
    xp_for_next_level: int | None


@dataclass(frozen=True)
class DuckLeveledUp(Event):
    type: ClassVar[str] = "DuckLeveledUp"
    duck_id: str
    level: int
    stage: str
    stat_budget: int
    stage_advanced: bool


# ----- Games against a human (Practice Pond, "You play"; ADR-0015) --------------------


@dataclass(frozen=True)
class SparringGameStarted(Event):
    type: ClassVar[str] = "SparringGameStarted"
    game_id: str
    duck_id: str
    human_color: str
    initial_fen: str
    white_clock_ms: int | None
    black_clock_ms: int | None
    series_id: str | None


@dataclass(frozen=True)
class SparringGameFinished(Event):
    type: ClassVar[str] = "SparringGameFinished"
    game_id: str
    result: str
    termination: str
    winner: str | None  # "human" | "duck" | None for a draw
    plies: int


@dataclass(frozen=True)
class SparringSeriesUpdated(Event):
    """Where a "You play" series stands, from the player's side."""

    type: ClassVar[str] = "SparringSeriesUpdated"
    series_id: str
    best_of: int
    human_points: float
    duck_points: float
    games_played: int
    state: str  # "playing" | "armageddon" | "decided"
    winner: str | None  # "human" | "duck"
    decided_by: str | None
    armageddon_human_color: str | None
