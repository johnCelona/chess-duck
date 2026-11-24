"""What a duck has been taught (spec 4.1): repertoire, principles, motifs, puzzle memory."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RepertoireEntry:
    color: str  # "white" or "black": the side the duck plays
    position_key: str
    move: str
    weight: int = 1
    source: str = "lesson"
    lesson_id: str | None = None


@dataclass(frozen=True)
class PuzzleMemoryEntry:
    position_key: str
    move: str
    lesson_id: str | None = None


@dataclass(frozen=True)
class Knowledge:
    repertoire: tuple[RepertoireEntry, ...] = ()
    principles: tuple[str, ...] = ()
    motifs: dict[str, int] = field(default_factory=dict)
    puzzle_memory: tuple[PuzzleMemoryEntry, ...] = ()

    def book_moves(self, color: str, position_key: str) -> tuple[RepertoireEntry, ...]:
        return tuple(
            entry
            for entry in self.repertoire
            if entry.color == color and entry.position_key == position_key
        )

    def taught_move(self, position_key: str) -> str | None:
        """The fix taught for exactly this position, if any (latest lesson wins)."""
        for entry in reversed(self.puzzle_memory):
            if entry.position_key == position_key:
                return entry.move
        return None
