"""The Beginner Duck: a full game against a duck with blind spots (design 06, experiment)."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.chessutil import position_key
from duckgambit.domain.minigames.base import (
    BoardView,
    Choice,
    Info,
    Level,
    Minigame,
    View,
    legal_ucis,
    moved,
    squares,
)
from duckgambit.domain.minigames.beginner_eyes import CONCEPTS, LOOSE, MATE, Thought, think

KNOWN = {
    "hatched": frozenset[str](),
    "loose": frozenset({LOOSE}),
    "mate": frozenset({MATE}),
    "both": frozenset(CONCEPTS),
}
MAX_PLIES = 300


class BeginnerDuck(Minigame):
    info = Info(
        "beginner-duck",
        "The Beginner Duck",
        "Play a whole game against a duck that has only just started learning.",
        "Nothing yet: this tests how a beginner duck should feel to play",
        "You are White, with no clock. The duck plays the best move it can see, but it is blind "
        "to ideas it has not learned. Press Hint to read what it was thinking on its last move.",
        (
            Level("hatched", "Just hatched", "Has learned nothing yet"),
            Level("loose", "Learned loose pieces", "Notices when its pieces can be won"),
            Level("mate", "Learned mate in one", "Sees checkmate in one, for both sides"),
            Level("both", "Learned both", "Loose pieces and mate in one"),
        ),
        "hatched",
    )
    rounds = 1
    start_hearts = None

    def start_round(self, rng: random.Random) -> None:
        self.known = KNOWN[self.level]
        self.board, self.last = chess.Board(), ""
        self.seen = [position_key(self.board)]
        self.thought: Thought | None = None
        self.told = False
        self.missed_total = self.learned_total = 0

    def on_move(self, uci: str) -> None:
        self.feedback, self.told, self.thought = None, False, None
        self._push(uci)
        if self._over():
            return
        self.thought = think(self.board, self.known, self.seed)
        self.missed_total += len(self.thought.missed)
        self.learned_total += len(self.thought.learned)
        self._push(self.thought.move)
        self._over()

    def _push(self, uci: str) -> None:
        self.board, self.last = moved(self.board, uci), uci
        self.seen.append(position_key(self.board))

    def _over(self) -> bool:
        board = self.board
        if board.is_checkmate():
            if board.turn == chess.WHITE:
                self._finish(0, "Checkmate. Your duck won!")
            else:
                self._finish(3, "Checkmate! You won.")
        elif board.is_stalemate():
            self._finish(1, "Stalemate: a draw.")
        elif board.is_insufficient_material():
            self._finish(1, "Nobody can checkmate any more: a draw.")
        elif self.seen.count(self.seen[-1]) >= 3:
            self._finish(1, "The same position three times: a draw.")
        elif board.halfmove_clock >= 100 or len(self.seen) > MAX_PLIES:
            self._finish(1, "Nothing is happening any more: a draw.")
        return self.phase != "play"

    def _finish(self, points: int, text: str) -> None:
        self.score += points
        self.say("good" if points == 3 else "info", text)
        self.phase = "review"

    def on_choice(self, choice: str) -> None:
        self._finish(0, "You resigned.")

    def on_hint(self) -> None:
        self.told = True

    def view(self) -> View:
        notes = []
        if self.told and self.thought:
            notes.append(f"Why {self.thought.san}?")
            notes += self.thought.learned + self.thought.missed or ("It just liked that move.",)
        if self.phase != "play":
            notes = [
                f"Things it did not notice: {self.missed_total}",
                f"Times a lesson changed its move: {self.learned_total}",
            ]
        return View(
            "Your move against the beginner duck.",
            BoardView(
                self.board.fen(),
                check=self.board.is_check(),
                last_move=squares(self.last) if self.last else None,
            ),
            moves=legal_ucis(self.board),
            choices=[Choice("resign", "Resign")],
            notes=notes,
            can_hint=self.thought is not None and not self.told,
        )
