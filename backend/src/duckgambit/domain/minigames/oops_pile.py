"""Oops Pile: watch a blunder get punished, rewind, and find a better move."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    Arrow,
    BoardView,
    Choice,
    Frame,
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
from duckgambit.domain.minigames.content import SLIPS

TOLERANCE_CP = 60  # [PH] a fix may be this far from the best move


class OopsPile(Minigame):
    info = Info(
        "oops-pile",
        "Oops Pile",
        "Somebody blundered. See why, rewind, and fix it.",
        "Checking for blunders: what does the opponent do next?",
        "First the slip and its punishment play out. Then the board rewinds and you find a "
        "better move. Any sound move counts. Misses are free here, and hints help.",
    )
    start_hearts = None

    def start_round(self, rng: random.Random) -> None:
        self.card = deal(self.seed, self.info.id, SLIPS, self.round)
        self.board = chess.Board(self.card["fen"])
        self.key: dict[str, int] = self.card["key"]
        self.best = max(sorted(self.key), key=lambda uci: self.key[uci])
        self.misses, self.hint, self.fix = 0, 0, ""
        self._replay()

    def _replay(self) -> None:
        slip = self.card["slip"]
        self.frames.append(Frame(self.board.fen(), None, "The position"))
        self.add_frames(self.board, [slip], f"The slip: {san(self.board, slip)}")
        self.add_frames(moved(self.board, slip), self.card["line"], "The punishment")
        self.frames.append(Frame(self.board.fen(), None, "Rewind!"))

    def on_choice(self, choice: str) -> None:
        self._replay()

    def on_move(self, uci: str) -> None:
        played = san(self.board, uci)
        loss = self.key[self.best] - self.key[uci]
        if uci == self.card["slip"]:
            self.misses += 1
            self.say("bad", f"{played} is the slip we are fixing!")
        elif loss <= TOLERANCE_CP:
            self.fix = uci
            best = "the best move" if uci == self.best else "a sound fix"
            self.win_round(max(1, 3 - self.misses - self.hint), f"{played} is {best}!")
        else:
            self.misses += 1
            much = "gives away a little" if loss < 150 else "still loses a lot"
            self.say("bad", f"{played} {much}. Try again.")

    def on_hint(self) -> None:
        self.hint += 1
        self.say("info", "Try the marked piece." if self.hint == 1 else "Play the green arrow.")

    def view(self) -> View:
        marks, arrows = list[Mark](), list[Arrow]()
        board = BoardView(self.board.fen(), check=self.board.is_check())
        if self.fix:
            board = board_after(self.board, self.fix)
        else:
            arrows.append(Arrow(*squares(self.card["slip"]), "bad"))
            if self.hint == 1:
                marks.append(Mark(self.best[:2], "hint"))
            elif self.hint > 1:
                arrows.append(Arrow(*squares(self.best), "good"))
        lost = self.card["lost"]
        return View(
            "The red move was a blunder by White. Show the duck something better.",
            board,
            moves=legal_ucis(self.board),
            marks=marks,
            arrows=arrows,
            choices=[Choice("replay", "Watch the slip again")],
            notes=[f"The slip lost {lost} points" if lost > 0 else "The slip allowed checkmate"],
            can_hint=self.hint < 2,
        )
