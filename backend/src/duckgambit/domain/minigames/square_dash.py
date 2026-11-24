"""Square Dash: tap the named square, as many as you can in 45 seconds."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import BoardView, Info, Mark, Minigame, View, pick

FLIP_AFTER = 8  # squares before the board turns around, and again


class SquareDash(Minigame):
    info = Info(
        "square-dash",
        "Square Dash",
        "45 seconds. Tap the named square!",
        "Knowing the board by its square names",
        "The board has no labels. Columns are letters a to h from White's left, rows are numbers "
        "1 to 8 from White's side. After eight squares you see it from Black's side. A miss "
        "shows where you tapped and ends your streak.",
    )
    rounds = 100
    start_hearts = None
    time_limit_ms = 45_000
    streak = 0
    target = -1

    def start_round(self, rng: random.Random) -> None:
        # Never the same square twice running.
        self.target = pick(rng, [s for s in chess.SQUARES if s != self.target])
        self.missed = ""

    def on_square(self, square: str) -> None:
        if chess.parse_square(square) != self.target:
            self.streak, self.missed = 0, square
            self.say("bad", f"That is {square}.")
            return
        self.streak += 1
        self.score += 1
        # Straight on to the next square: no result to read.
        self._advance()
        if self.phase == "play":
            self.say("good", f"Yes! Streak {self.streak}.")

    def view(self) -> View:
        from_black = (self.round // FLIP_AFTER) % 2 == 1
        return View(
            f"Tap {chess.square_name(self.target)}",
            BoardView(
                "8/8/8/8/8/8/8/8 w - - 0 1",
                "black" if from_black else "white",
                coordinates=False,
            ),
            squares=list(chess.SQUARE_NAMES),
            marks=[Mark(self.missed, "bad")] if self.missed else [],
            notes=[f"Seen from {'Black' if from_black else 'White'}", f"Streak: {self.streak}"],
        )
