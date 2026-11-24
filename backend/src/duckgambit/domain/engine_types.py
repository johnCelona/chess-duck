"""Values exchanged with an engine. The Engine port itself lives in services (ADR-0007)."""

from __future__ import annotations

from dataclasses import dataclass

import chess

from duckgambit.domain.chessutil import UCI_MOVE
from duckgambit.domain.errors import DomainError

MAX_MULTIPV = 10
MATE_SCORE = 30_000
MAX_CP = 20_000


@dataclass(frozen=True)
class SearchRequest:
    """A stateless search: the result depends only on these fields and the engine binary."""

    initial_fen: str
    moves: tuple[str, ...]
    multipv: int
    nodes: int | None = None
    depth: int | None = None

    def validate(self, max_nodes: int, max_depth: int = 100) -> None:
        """Reject anything malformed before it reaches an engine (Stockfish exits on bad input)."""
        if (self.nodes is None) == (self.depth is None):
            raise DomainError("search.limit", "Exactly one of nodes or depth is required")
        if self.nodes is not None and not 1 <= self.nodes <= max_nodes:
            raise DomainError("search.limit", f"nodes must be between 1 and {max_nodes}")
        if self.depth is not None and not 1 <= self.depth <= max_depth:
            raise DomainError("search.limit", f"depth must be between 1 and {max_depth}")
        if not 1 <= self.multipv <= MAX_MULTIPV:
            raise DomainError("search.multipv", f"multipv must be between 1 and {MAX_MULTIPV}")
        if any(not UCI_MOVE.match(move) for move in self.moves):
            raise DomainError("search.moves", "moves must be UCI strings")
        try:
            chess.Board(self.initial_fen)
        except ValueError as exc:
            raise DomainError("chess.invalid_fen", f"Invalid FEN: {exc}") from exc


@dataclass(frozen=True)
class Candidate:
    """One engine line, scored from the side to move's point of view."""

    move: str
    cp: int | None
    mate: int | None
    wdl: tuple[int, int, int] | None
    depth: int
    pv: tuple[str, ...]

    def score(self) -> int:
        """A single comparable integer: centipawns, with mates mapped far outside."""
        if self.mate is not None:
            if self.mate > 0:
                return MATE_SCORE - 10 * self.mate
            return -MATE_SCORE - 10 * self.mate
        return max(-MAX_CP, min(MAX_CP, self.cp or 0))


@dataclass(frozen=True)
class SearchResult:
    """Candidates best first, all from the same completed depth."""

    candidates: tuple[Candidate, ...]
    nodes: int
    depth: int


@dataclass(frozen=True)
class EngineOption:
    name: str
    type: str
    default: str | int | bool | None
    min: int | None
    max: int | None
    choices: tuple[str, ...]


@dataclass(frozen=True)
class EngineInfo:
    name: str
    options: tuple[EngineOption, ...]


@dataclass(frozen=True)
class EngineIdentity:
    """Which engine produced a result. The fingerprint is part of the rating context."""

    id: str
    name: str
    version: str
    fingerprint: str  # first 16 hex digits of the binary's sha256
