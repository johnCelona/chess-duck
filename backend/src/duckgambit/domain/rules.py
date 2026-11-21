"""Style rules: small, pure tests on (board, move) that nudge a candidate's score.

A rule can misfire, and that is intended (spec 5.2): a duck trained to love checks
will sometimes check when it should not. Principles (M2) and motifs (M4) are added
to this registry; nothing else in the decision layer changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import chess

from duckgambit.domain.balance import MindParams


@dataclass(frozen=True)
class StyleRule:
    id: str
    kind: str  # "aggression" | "solidity" | "principle" | "motif"
    base_cp: int
    label: str
    applies: Callable[[chess.Board, chess.Move], bool]


@dataclass(frozen=True)
class Adjustment:
    rule_id: str
    kind: str
    delta_cp: int
    label: str


def _is_capture(board: chess.Board, move: chess.Move) -> bool:
    return bool(board.is_capture(move))


def _gives_check(board: chess.Board, move: chess.Move) -> bool:
    return bool(board.gives_check(move))


def _is_castling(board: chess.Board, move: chess.Move) -> bool:
    return bool(board.is_castling(move))


def _is_retreat(board: chess.Board, move: chess.Move) -> bool:
    piece = board.piece_at(move.from_square)
    if piece is None or piece.piece_type in (chess.PAWN, chess.KING) or board.is_capture(move):
        return False
    before, after = chess.square_rank(move.from_square), chess.square_rank(move.to_square)
    return bool(after < before if board.turn == chess.WHITE else after > before)


RULES: tuple[StyleRule, ...] = (
    StyleRule("capture", "aggression", 20, "likes captures", _is_capture),
    StyleRule("check", "aggression", 25, "likes giving check", _gives_check),
    StyleRule("castle", "solidity", 30, "likes a safe king", _is_castling),
    StyleRule("retreat", "solidity", 10, "likes regrouping", _is_retreat),
)


def weight_for(kind: str, mind: MindParams) -> int:
    if kind == "aggression":
        return mind.aggression_weight
    if kind == "solidity":
        return mind.solidity_weight
    return 0


def adjustments_for(
    board: chess.Board,
    move: chess.Move,
    mind: MindParams,
    rules: tuple[StyleRule, ...] = RULES,
) -> tuple[Adjustment, ...]:
    result = []
    for rule in rules:
        delta = rule.base_cp * weight_for(rule.kind, mind) // 100
        if delta != 0 and rule.applies(board, move):
            result.append(Adjustment(rule.id, rule.kind, delta, rule.label))
    return tuple(result)
