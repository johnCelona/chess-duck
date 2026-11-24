"""Crack the Shell: every mate in one cracks the egg a little more."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
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
    squares,
)
from duckgambit.domain.minigames.content import MATES


class CrackTheShell(Minigame):
    info = Info(
        "crack-the-shell",
        "Crack the Shell",
        "Checkmate in one move cracks the egg.",
        "Spotting checkmate in one",
        "White has a checkmate in one move. Every mate cracks the shell; five mates hatch it.",
    )

    def start_round(self, rng: random.Random) -> None:
        self.card = deal(self.seed, self.info.id, MATES, self.round)
        self.board = chess.Board(self.card["fen"])
        self.played = ""
        self.hint = False
        self.misses = 0

    def on_move(self, uci: str) -> None:
        after = moved(self.board, uci)
        if after.is_checkmate():
            self.played = uci
            self.win_round(1 if self.hint or self.misses else 3, "Checkmate! Crack!")
            return
        self.misses += 1
        if after.is_check():
            reply = next(iter(after.legal_moves)).uci()
            self.lose_heart(f"Check, but not mate: Black has {san(after, reply)}.")
        elif after.is_stalemate():
            self.lose_heart("Stalemate! Black cannot move but is not in check: a draw.")
        else:
            self.lose_heart("That is not even check, and mate is always check.")

    def on_hint(self) -> None:
        self.hint = True
        self.say("info", "Move the marked piece.")

    def view(self) -> View:
        board, marks = BoardView(self.board.fen(), check=self.board.is_check()), list[Mark]()
        mate = self.card["mates"][0]
        if self.played:
            board = board_after(self.board, self.played)
        elif self.phase != "play":
            marks = [Mark(square, "good") for square in squares(mate)]
        elif self.hint:
            marks = [Mark(mate[:2], "hint")]
        return View(
            "White to move: checkmate in one!",
            board,
            moves=legal_ucis(self.board),
            marks=marks,
            can_hint=not self.hint,
        )
