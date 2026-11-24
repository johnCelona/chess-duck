"""Tuck the Duckling In: may the king castle here, and on which side?"""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    BoardView,
    Choice,
    Info,
    Mark,
    Minigame,
    View,
    pick,
)

CASTLE = {"king": "e1g1", "queen": "e1c1"}
BETWEEN = {"king": [chess.F1, chess.G1], "queen": [chess.D1, chess.C1, chess.B1]}
PATH = {"king": [chess.F1, chess.G1], "queen": [chess.D1, chess.C1]}
ROOK = {"king": chess.H1, "queen": chess.A1}


def may_castle(board: chess.Board, side: str) -> bool:
    return bool(board.is_legal(chess.Move.from_uci(CASTLE[side])))


class TuckIn(Minigame):
    info = Info(
        "tuck-in",
        "Tuck the Duckling In",
        "Can the king castle to safety? Which nest is open?",
        "The castling rules, including the sneaky ones",
        "Decide where White may castle. The king cannot castle out of check, through check or "
        "into check, nothing may stand in between, and neither the king nor that rook may "
        "have moved before.",
    )
    rounds = 8

    def start_round(self, rng: random.Random) -> None:
        want = pick(rng, ["king", "queen", "both", "none", "none"])
        while True:
            self._random_home(rng)
            if not self.board.is_valid():
                continue
            sides = [side for side in CASTLE if may_castle(self.board, side)]
            self.answer = "both" if len(sides) == 2 else sides[0] if sides else "none"
            if self.answer == want:
                return

    def _random_home(self, rng: random.Random) -> None:
        board = chess.Board("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        self.story = ""
        tale = pick(rng, ["", "", "", "", "king-moved", "king", "queen"])
        if tale == "king-moved":
            board.castling_rights = chess.BB_EMPTY
            self.story = " (Your king moved earlier and came back.)"
        elif tale:
            board.castling_rights &= ~chess.BB_SQUARES[ROOK[tale]]
            self.story = f" (Your {tale}side rook moved earlier and came back.)"
        for file in range(8):
            if pick(rng, [True, False]):
                square = chess.square(file, 1)
                board.set_piece_at(square, chess.Piece(chess.PAWN, chess.WHITE))
        if pick(rng, [True, False, False]):
            square = pick(rng, BETWEEN["king"] + BETWEEN["queen"])
            kind = pick(rng, [chess.KNIGHT, chess.BISHOP])
            board.set_piece_at(square, chess.Piece(kind, chess.WHITE))
        for _ in range(pick(rng, [1, 2, 2, 3])):
            free = [s for s in chess.SQUARES if chess.square_rank(s) >= 2 and not board.piece_at(s)]
            kind = pick(rng, [chess.ROOK, chess.BISHOP, chess.BISHOP, chess.KNIGHT, chess.QUEEN])
            board.set_piece_at(pick(rng, free), chess.Piece(kind, chess.BLACK))
        self.board = board

    def _why(self, side: str) -> str:
        board = self.board
        if may_castle(board, side):
            if board.is_attacked_by(chess.BLACK, ROOK[side]):
                return "yes (an attacked rook may still castle)"
            if side == "queen" and board.is_attacked_by(chess.BLACK, chess.B1):
                return "yes (b1 is attacked, but the king never crosses it)"
            return "yes"
        if not board.castling_rights & chess.BB_SQUARES[ROOK[side]]:
            return "no, the king or that rook has moved"
        if board.is_check():
            return "no, the king is in check"
        if any(board.piece_at(square) for square in BETWEEN[side]):
            return "no, a piece is in the way"
        hit = next(s for s in PATH[side] if board.is_attacked_by(chess.BLACK, s))
        return f"no, the king would touch {chess.square_name(hit)}, which is attacked"

    def on_choice(self, choice: str) -> None:
        why = f"Kingside: {self._why('king')}. Queenside: {self._why('queen')}."
        if choice == self.answer:
            self.win_round(2, f"Right! {why}")
        else:
            self.lose_heart(why, ends_round=True)

    def view(self) -> View:
        marks = []
        if self.phase != "play":
            marks = [
                Mark(chess.square_name(square), "danger")
                for square in (chess.C1, chess.D1, chess.E1, chess.F1, chess.G1)
                if self.board.is_attacked_by(chess.BLACK, square)
            ]
        return View(
            f"White to move. Where may the king castle?{self.story}",
            BoardView(self.board.fen(), check=self.phase != "play" and self.board.is_check()),
            marks=marks,
            choices=[
                Choice("king", "Kingside", "O-O"),
                Choice("queen", "Queenside", "O-O-O"),
                Choice("both", "Either side"),
                Choice("none", "Nowhere"),
            ],
        )
