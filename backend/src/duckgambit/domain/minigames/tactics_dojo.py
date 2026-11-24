"""Tactics Dojo: forks first, then pins. One move wins material; find it."""

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
    board_after,
    deal,
    legal_ucis,
    moved,
    san,
)
from duckgambit.domain.minigames.content import FORKS, PINS

FORK_ROUNDS = 4


class TacticsDojo(Minigame):
    info = Info(
        "tactics-dojo",
        "Tactics Dojo",
        "Forks, then pins. One move wins material.",
        "Forks (attack two things at once) and pins (freeze a piece to its king)",
        "Every position has one clearly best move. Rounds 1 to 4 are forks, 5 and 6 are pins. "
        "Afterwards you see how the tactic plays out.",
    )
    rounds = 6

    def start_round(self, rng: random.Random) -> None:
        self.theme = "fork" if self.round < FORK_ROUNDS else "pin"
        deck = FORKS if self.theme == "fork" else PINS
        self.card = deal(self.seed, self.theme, deck, self.round)
        self.board = chess.Board(self.card["fen"])
        self.misses, self.hint = 0, 0

    def on_move(self, uci: str) -> None:
        played = san(self.board, uci)
        if uci == self.card["best"]:
            self.add_frames(self.board, self.card["line"][:5], "Here is how it plays out")
            points = 1 if self.misses or self.hint else 3
            self.win_round(points, f"{played} is the {self.theme}!")
        else:
            self.misses += 1
            self.lose_heart(f"{played} misses the {self.theme}.")

    def on_hint(self) -> None:
        self.hint += 1
        self.say("info", "Move the marked piece." if self.hint == 1 else "Move it to the target.")

    def view(self) -> View:
        best = self.card["best"]
        board, marks = BoardView(self.board.fen(), check=self.board.is_check()), list[Mark]()
        arrows: list[Arrow] = []
        if self.phase != "play":
            board, arrows = board_after(self.board, best), self._targets()
        else:
            if self.hint > 0:
                marks.append(Mark(best[:2], "hint"))
            if self.hint > 1:
                marks.append(Mark(best[2:4], "target"))
        goal = "fork: attack two things at once" if self.theme == "fork" else "pin"
        return View(
            f"White to move. Find the {goal}.",
            board,
            moves=legal_ucis(self.board),
            marks=marks,
            arrows=arrows,
            can_hint=self.hint < 2,
        )

    def _targets(self) -> list[Arrow]:
        """The pieces the tactic hits."""
        after, origin = moved(self.board, self.card["best"]), self.card["best"][2:4]
        return [
            Arrow(origin, chess.square_name(s), "good")
            for s in after.attacks(chess.parse_square(origin))
            if after.color_at(s) == chess.BLACK and after.piece_type_at(s) != chess.PAWN
        ]
