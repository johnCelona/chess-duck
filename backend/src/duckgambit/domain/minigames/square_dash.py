"""Square Dash: tap the named square, 45 seconds from each side of the board."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import Banner, BoardView, Info, Mark, Minigame, View, pick
from duckgambit.domain.seeds import rng_for

SIDES = ("White", "Black")


class SquareDash(Minigame):
    info = Info(
        "square-dash",
        "Square Dash",
        "Tap the named square! 45 seconds as White, then 45 as Black.",
        "Knowing the board by its square names, from both sides",
        "The board has no labels. Columns are letters a to h from White's left, rows are numbers "
        "1 to 8 from White's side. After 45 seconds the board turns around and you get 45 more "
        "from Black's side. A miss shows where you tapped and ends your streak.",
    )
    rounds = len(SIDES)
    start_hearts = None
    time_limit_ms = 45_000

    def __init__(self, seed: int, level: str = "") -> None:
        self.hits = [0] * len(SIDES)
        super().__init__(seed, level)

    def start_round(self, rng: random.Random) -> None:
        self.used_ms = 0  # each side has its own clock
        self.streak, self.missed = 0, ""
        self.asked, self.target = 0, -1
        self._ask()

    def _ask(self) -> None:
        rng = rng_for(self.seed, self.info.id, self.round, self.asked)
        # Never the same square twice running.
        self.target = pick(rng, [s for s in chess.SQUARES if s != self.target])
        self.asked += 1
        self.missed = ""

    def on_square(self, square: str) -> None:
        if chess.parse_square(square) != self.target:
            self.streak, self.missed = 0, square
            self.say("bad", f"That is {square}.")
            return
        self.streak += 1
        self.score += 1
        self.hits[self.round] += 1
        self.say("good", f"Yes! Streak {self.streak}.")
        self._ask()

    def on_time_up(self) -> None:
        if self.round + 1 < self.rounds:
            self.phase = "review"
        else:
            super().on_time_up()

    def view(self) -> View:
        shown = self.round + 1 if self.phase == "done" else self.round
        notes = [f"{side}'s side: {self.hits[i]}" for i, side in enumerate(SIDES[: shown + 1])]
        banner = None
        if self.phase == "review":
            banner = Banner(
                "Switching to Black",
                f"You found {self.hits[0]} from White's side. Now the board turns around.",
                "Start Black's side",
                turns_board=True,
            )
        if self.phase == "play":
            notes.append(f"Streak: {self.streak}")
        return View(
            # The next square stays secret until its clock runs.
            f"Tap {chess.square_name(self.target)}" if self.phase == "play" else "Square Dash",
            BoardView(
                "8/8/8/8/8/8/8/8 w - - 0 1",
                "black" if self.round == 1 else "white",
                coordinates=False,
            ),
            squares=list(chess.SQUARE_NAMES),
            marks=[Mark(self.missed, "bad")] if self.missed else [],
            notes=notes,
            banner=banner,
            headline=chess.square_name(self.target) if self.phase == "play" else "",
        )
