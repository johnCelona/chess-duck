"""Loose Feathers: tap every black piece that nothing defends."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    Arrow,
    BoardView,
    Info,
    Mark,
    Minigame,
    View,
    deal,
    name_at,
)
from duckgambit.domain.minigames.content import SHOWDOWNS, SLIPS


def loose(board: chess.Board) -> list[int]:
    """Black pieces, kings aside, that no black piece defends."""
    return [
        square
        for square in chess.SquareSet(board.occupied_co[chess.BLACK])
        if board.piece_type_at(square) != chess.KING and not board.attackers(chess.BLACK, square)
    ]


DECK = [card["fen"] for card in SHOWDOWNS + SLIPS if 2 <= len(loose(chess.Board(card["fen"]))) <= 6]


class LooseFeathers(Minigame):
    info = Info(
        "loose-feathers",
        "Loose Feathers",
        "Tap every undefended black piece.",
        "Spotting loose pieces, where most tactics start",
        "A piece is loose when no other black piece defends its square. Tap all the loose ones, "
        "pawns too. You have 90 seconds; the clock stops between rounds. Tapping a defended "
        "piece costs a heart and shows its defender.",
    )
    rounds = 6
    time_limit_ms = 90_000

    def start_round(self, rng: random.Random) -> None:
        self.board = chess.Board(deal(self.seed, self.info.id, DECK, self.round))
        self.targets = loose(self.board)
        self.found: list[int] = []
        self.defender: tuple[str, str] | None = None

    def on_square(self, square: str) -> None:
        tapped = chess.parse_square(square)
        self.defender = None
        if tapped in self.targets:
            self.found.append(tapped)
            left = len(self.targets) - len(self.found)
            if left:
                self.say("good", f"Loose! {left} to go.")
            else:
                self.win_round(len(self.targets), "Every loose feather found!")
            return
        guard = min(self.board.attackers(chess.BLACK, tapped))
        self.defender = chess.square_name(guard), square
        self.lose_heart(
            f"The {name_at(self.board, tapped)} on {square} is defended by the "
            f"{name_at(self.board, guard)} on {chess.square_name(guard)}."
        )

    def view(self) -> View:
        marks = [Mark(chess.square_name(s), "good") for s in self.found]
        if self.phase != "play":
            missed = [s for s in self.targets if s not in self.found]
            marks += [Mark(chess.square_name(s), "target") for s in missed]
        black = chess.SquareSet(self.board.occupied_co[chess.BLACK])
        return View(
            "Tap every black piece that nothing defends.",
            BoardView(self.board.fen()),
            squares=[
                chess.square_name(s)
                for s in black
                if s not in self.found and self.board.piece_type_at(s) != chess.KING
            ],
            marks=marks,
            arrows=[Arrow(*self.defender, "bad")] if self.defender else [],
            notes=[f"Found {len(self.found)} of {len(self.targets)}"],
        )
