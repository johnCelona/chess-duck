"""Stuck or Mated?: checkmate, stalemate, or is there still a way out?"""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    Arrow,
    BoardView,
    Choice,
    Info,
    Minigame,
    View,
    pick,
    squares,
)

ANSWERS = ("mate", "stalemate", "check", "free")
ARMIES = [
    [chess.QUEEN],
    [chess.QUEEN, chess.PAWN],
    [chess.ROOK, chess.ROOK],
    [chess.QUEEN, chess.BISHOP],
    [chess.ROOK, chess.BISHOP],
    [chess.QUEEN, chess.KNIGHT],
]


def verdict(board: chess.Board) -> str:
    stuck = not any(True for _ in board.legal_moves)
    if board.is_check():
        return "mate" if stuck else "check"
    return "stalemate" if stuck else "free"


class StuckOrMated(Minigame):
    info = Info(
        "stuck-or-mated",
        "Stuck or Mated?",
        "Checkmate, stalemate, or a way out? 60 seconds.",
        "Telling checkmate from stalemate, and finding the last escape",
        "It is Black's move. Is the king attacked? Can Black move at all? Attacked and stuck is "
        "checkmate; stuck but not attacked is stalemate, a draw. The clock stops while you read.",
    )
    rounds = 15
    time_limit_ms = 60_000

    def start_round(self, rng: random.Random) -> None:
        self.answer = pick(rng, list(ANSWERS))
        while True:
            board = self._random_corner(rng)
            if board.is_valid() and verdict(board) == self.answer:
                break
        self.board = board

    def _random_corner(self, rng: random.Random) -> chess.Board:
        board = chess.Board(None)
        board.turn = chess.BLACK
        # The edge and corners, where stuck kings live.
        goose = pick(rng, [s for s in chess.SQUARES if chess.BB_SQUARES[s] & EDGE])
        board.set_piece_at(goose, chess.Piece(chess.KING, chess.BLACK))
        for kind in (chess.KING, *pick(rng, ARMIES)):
            near = 3 if kind == chess.KING else 7
            free = [
                s
                for s in chess.SQUARES
                if not board.piece_at(s)
                and 2 <= chess.square_distance(s, goose) <= near
                and (kind != chess.PAWN or 1 <= chess.square_rank(s) <= 6)
            ]
            if kind not in (chess.KING, chess.PAWN):
                free += [s for s in board.attacks(goose) if not board.piece_at(s)]
            board.set_piece_at(pick(rng, free), chess.Piece(kind, chess.WHITE))
        return board

    def on_choice(self, choice: str) -> None:
        why = {
            "mate": "Checkmate: attacked, and no way out.",
            "stalemate": "Stalemate: not attacked, but no legal move. A draw!",
            "check": "Only check: the green arrow is a way out.",
            "free": "Not even check, and the green arrow is a legal move.",
        }[self.answer]
        if choice == self.answer:
            self.win_round(1, f"Right! {why}")
        else:
            self.lose_heart(why, ends_round=True)

    def view(self) -> View:
        arrows = []
        if self.phase == "review":
            out = sorted(m.uci() for m in self.board.legal_moves)
            arrows = [Arrow(*squares(uci), "good") for uci in out]
            for attacker in self.board.checkers():
                king = self.board.king(chess.BLACK)
                assert king is not None
                arrows.append(Arrow(chess.square_name(attacker), chess.square_name(king), "bad"))
        return View(
            "Black to move. What is this?",
            BoardView(self.board.fen(), check=self.phase == "review" and self.board.is_check()),
            arrows=arrows,
            choices=[
                Choice("mate", "Checkmate"),
                Choice("stalemate", "Stalemate"),
                Choice("check", "Check, but there is a way out"),
                Choice("free", "Neither: play goes on"),
            ],
        )


EDGE = chess.BB_RANK_1 | chess.BB_RANK_8 | chess.BB_FILE_A | chess.BB_FILE_H
