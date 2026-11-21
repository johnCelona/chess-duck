"""Puzzle Arena: pack format and scoring (spec 7.4, ADR-0009).

STUB FOR M4. The pack schema and the pure scoring functions are here and tested.
Pack building, the Defender modes and puzzle ratings are built in their sessions.

In play, grading is a lookup: every legal move of a puzzle already has a Judge
verdict in its answer key, so only the ducks search.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from duckgambit.domain.chessutil import UCI_MOVE, board_from
from duckgambit.domain.errors import DomainError

PACK_FORMAT = "duck-gambit.puzzle-pack"
PACK_VERSION = 1


@dataclass(frozen=True)
class AnswerEntry:
    """The Judge's verdict on one legal move, from the solver's point of view."""

    move: str
    win: int  # per mille
    draw: int
    loss: int
    cp: int | None
    mate: int | None  # positive: the solver mates in this many moves

    @property
    def win_chance_permille(self) -> int:
        return 1000 if self.mate is not None and self.mate > 0 else self.win

    def order(self) -> tuple[int, int, int]:
        """Sort key, best first: forced mates by distance, then win chance, then score."""
        if self.mate is not None and self.mate > 0:
            return (0, self.mate, 0)
        return (1, -self.win, -(self.cp or 0))


@dataclass(frozen=True)
class Puzzle:
    id: str
    fen: str  # the position shown to the solver
    goal: str
    themes: tuple[str, ...]
    rating: int | None
    answer_key: dict[str, AnswerEntry]

    @property
    def keyed(self) -> bool:
        return bool(self.answer_key)


@dataclass(frozen=True)
class PuzzlePack:
    id: str
    title: str
    license: str
    judge: dict[str, Any]
    puzzles: tuple[Puzzle, ...]


@dataclass(frozen=True)
class ShowdownRules:
    """Candidate Showdown points from spec 7.4. Placeholders until M4."""

    keep_win_permille: int = 900
    top_pick_best: int = 3
    best_in_top: int = 2
    still_holding: int = 1
    blunder_penalty: int = -1
    blunder_loss_cp: int = 200


DEFAULT_SHOWDOWN_RULES = ShowdownRules()


@dataclass(frozen=True)
class ShowdownScore:
    points: int
    top_pick_is_best: bool
    best_in_list: bool
    traps: int  # how many of the duck's ideas throw the position away


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DomainError("puzzlepack.invalid", message)


def load_pack(data: Any) -> PuzzlePack:
    """Validate a pack document (already parsed from JSON)."""
    _require(isinstance(data, dict) and data.get("format") == PACK_FORMAT, "Not a puzzle pack")
    version = data.get("schemaVersion")
    _require(version == PACK_VERSION, f"Unsupported puzzle pack version: {version!r}")
    for field in ("id", "title", "license"):
        _require(isinstance(data.get(field), str) and data[field], f"Pack is missing {field}")
    raw_puzzles = data.get("puzzles")
    _require(
        isinstance(raw_puzzles, list) and len(raw_puzzles) > 0, "A pack needs at least one puzzle"
    )

    puzzles = []
    for raw in raw_puzzles:
        _require(isinstance(raw, dict) and isinstance(raw.get("id"), str), "Puzzle without an id")
        board = board_from(str(raw.get("fen", "")))
        legal = {move.uci() for move in board.legal_moves}
        _require(bool(legal), f"Puzzle {raw['id']} has no legal moves")
        key: dict[str, AnswerEntry] = {}
        for move, entry in (raw.get("answerKey") or {}).items():
            _require(bool(UCI_MOVE.match(move)) and move in legal, f"{raw['id']}: illegal {move}")
            wdl = entry.get("wdl")
            _require(
                isinstance(wdl, list) and len(wdl) == 3 and sum(wdl) == 1000,
                f"{raw['id']} {move}: wdl must be three per-mille values summing to 1000",
            )
            key[move] = AnswerEntry(
                move, wdl[0], wdl[1], wdl[2], entry.get("cp"), entry.get("mate")
            )
        _require(
            not key or set(key) == legal,
            f"Puzzle {raw['id']}: the answer key must cover every legal move",
        )
        goal = raw.get("goal") or {}
        puzzles.append(
            Puzzle(
                id=raw["id"],
                fen=board.fen(),
                goal=str(goal.get("type", "find-best")),
                themes=tuple(raw.get("themes") or ()),
                rating=raw.get("rating"),
                answer_key=key,
            )
        )
    return PuzzlePack(
        id=data["id"],
        title=data["title"],
        license=data["license"],
        judge=dict(data.get("judge") or {}),
        puzzles=tuple(puzzles),
    )


def best_entries(puzzle: Puzzle) -> list[AnswerEntry]:
    """Every move that ties the Judge's best result (any of them is a correct answer)."""
    ordered = sorted(puzzle.answer_key.values(), key=AnswerEntry.order)
    top = ordered[0].order()
    return [entry for entry in ordered if entry.order() == top]


def score_showdown(
    ranked: list[str], puzzle: Puzzle, rules: ShowdownRules = DEFAULT_SHOWDOWN_RULES
) -> ShowdownScore:
    """Points for a duck's ranked ideas (its top 5) on one puzzle."""
    if not puzzle.keyed:
        raise DomainError("puzzle.no_answer_key", f"Puzzle {puzzle.id} has no answer key yet")
    ideas = [move for move in ranked if move in puzzle.answer_key]
    if not ideas:
        return ShowdownScore(0, False, False, 0)
    best = {entry.move for entry in best_entries(puzzle)}
    best_cp = max((entry.cp or 0) for entry in puzzle.answer_key.values())
    first = puzzle.answer_key[ideas[0]]

    def is_trap(move: str) -> bool:
        entry = puzzle.answer_key[move]
        return entry.mate is None and best_cp - (entry.cp or 0) >= rules.blunder_loss_cp

    top_is_best = ideas[0] in best
    best_listed = any(move in best for move in ideas)
    if top_is_best:
        points = rules.top_pick_best
    elif best_listed:
        points = rules.best_in_top
    elif any(
        puzzle.answer_key[move].win_chance_permille >= rules.keep_win_permille for move in ideas
    ):
        points = rules.still_holding
    else:
        points = 0
    if not top_is_best and first.mate is None and is_trap(ideas[0]):
        points += rules.blunder_penalty
    return ShowdownScore(
        points, top_is_best, best_listed, sum(1 for move in ideas if is_trap(move))
    )


def agreement(first: list[str], second: list[str]) -> int:
    """How many ideas two ducks share."""
    return len(set(first) & set(second))


def original_ideas(ranked: list[str], others: list[list[str]], puzzle: Puzzle) -> list[str]:
    """Judge top-3 moves that this duck listed and no other duck did."""
    top_three = [
        entry.move for entry in sorted(puzzle.answer_key.values(), key=AnswerEntry.order)[:3]
    ]
    seen_elsewhere = {move for other in others for move in other}
    return [move for move in ranked if move in top_three and move not in seen_elsewhere]
