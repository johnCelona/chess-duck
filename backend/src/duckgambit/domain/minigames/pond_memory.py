"""Pond Memory: the pieces dive underwater. Where was each one?"""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    BoardView,
    Choice,
    Frame,
    Info,
    Mark,
    Minigame,
    View,
    deal,
    name_at,
    pick,
)
from duckgambit.domain.minigames.content import SHOWDOWNS, SLIPS

PIECES = [3, 4, 5, 6, 7]  # how many pieces dive, round by round
LOOKS = 5  # animation frames the pieces stay visible


class PondMemory(Minigame):
    info = Info(
        "pond-memory",
        "Pond Memory",
        "Look, then remember where every piece stood.",
        "Seeing the board in your head",
        "Pieces from a real position show for a few seconds, then dive. Tap where each one was "
        "when asked. Found pieces come back up. Each round has one more.",
    )
    rounds = len(PIECES)

    def start_round(self, rng: random.Random) -> None:
        # Real positions, because real patterns are what chess memory is made of.
        source = chess.Board(deal(self.seed, self.info.id, SHOWDOWNS + SLIPS, self.round)["fen"])
        kings = [s for s in chess.SQUARES if source.piece_type_at(s) == chess.KING]
        others = [
            s
            for s in chess.SQUARES
            if source.piece_type_at(s) not in (None, chess.PAWN, chess.KING)
        ]
        kept = list(kings)
        while len(kept) < PIECES[self.round] and others:
            square = pick(rng, others)
            others.remove(square)
            kept.append(square)
        self.hidden = chess.Board(None)
        for square in kept:
            self.hidden.set_piece_at(square, source.piece_at(square))
        self.todo: list[int] = []
        while kept:
            square = pick(rng, kept)
            kept.remove(square)
            self.todo.append(square)
        self.up = chess.Board(None)
        self.misses, self.missed = 0, ""
        self._show()

    def _show(self) -> None:
        for left in range(LOOKS, 0, -1):
            self.frames.append(Frame(self.hidden.fen(), None, f"Remember! {left}"))

    def on_square(self, square: str) -> None:
        tapped, wanted = chess.parse_square(square), self.hidden.piece_at(self.todo[0])
        # Two of the same kind? Either one counts.
        if self.hidden.piece_at(tapped) != wanted or tapped not in self.todo:
            self.misses, self.missed = self.misses + 1, square
            self.lose_heart("Not there.")
            return
        self.todo.remove(tapped)
        self.up.set_piece_at(tapped, wanted)
        self.missed = ""
        if self.todo:
            self.say("good", "There it is!")
        else:
            self.win_round(max(1, 5 - self.misses), "All back above water!")

    def on_choice(self, choice: str) -> None:
        self.misses += 1
        self.say("info", "That look cost a point.")
        self._show()

    def view(self) -> View:
        prompt, board = "All the pieces are back.", self.up
        if self.todo:
            color = "white" if self.hidden.color_at(self.todo[0]) else "black"
            prompt = f"Where was the {color} {name_at(self.hidden, self.todo[0])}?"
        if self.phase != "play":
            board = self.hidden
        marks = [Mark(self.missed, "bad")] if self.missed else []
        if self.phase != "play":
            marks += [Mark(chess.square_name(s), "target") for s in self.todo]
        return View(
            prompt,
            BoardView(board.fen()),
            squares=[n for n in chess.SQUARE_NAMES if not board.piece_at(chess.parse_square(n))],
            marks=marks,
            choices=[Choice("look", "Look again", "Costs a point")],
            notes=[f"Still underwater: {len(self.todo)}"],
        )
