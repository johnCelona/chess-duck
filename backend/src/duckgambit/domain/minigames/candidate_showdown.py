"""Candidate Showdown: you and three ducks each name three moves for one position."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    VALUE,
    Arrow,
    BoardView,
    Choice,
    Info,
    Minigame,
    View,
    deal,
    legal_ucis,
    moved,
    pick,
    san,
    squares,
)
from duckgambit.domain.minigames.content import SHOWDOWNS

PICKS = 3
RIVALS = ("Hungry duck", "Pushy duck", "Wild duck")  # placeholder names (John's)


def move_points(loss: int) -> int:
    """[PH] 5 for the best move, less for a worse one, 0 for a blunder."""
    for limit, points in ((0, 5), (25, 4), (60, 3), (120, 2), (200, 1)):
        if loss <= limit:
            return points
    return 0


class CandidateShowdown(Minigame):
    info = Info(
        "candidate-showdown",
        "Candidate Showdown",
        "Name your three best moves. Out-think three silly ducks.",
        "Looking for several good moves instead of playing the first idea",
        "Play three different moves, best first; the board resets after each. Your first pick "
        "counts double. Afterwards you see the ducks' picks and the engine's order.",
    )
    start_hearts = None
    rounds = 4

    def start_round(self, rng: random.Random) -> None:
        card = deal(self.seed, self.info.id, SHOWDOWNS, self.round)
        self.board = chess.Board(card["fen"])
        self.key: dict[str, int] = card["key"]
        self.best = max(self.key.values())
        self.picks: list[str] = []
        self.rivals = {name: self._rival(name, rng) for name in RIVALS}

    def _rival(self, name: str, rng: random.Random) -> list[str]:
        pool = legal_ucis(self.board)
        if name == "Hungry duck":
            pool.sort(key=lambda uci: (-self._meal(uci), uci))
        elif name == "Pushy duck":
            pool.sort(key=lambda uci: (-self._push(uci), uci))
        else:
            # Wild, but not blind: any moves that do not blunder outright.
            safe = [uci for uci in pool if self.best - self.key[uci] <= 200]
            pool = [pick(rng, safe) for _ in range(40)]
        return list(dict.fromkeys(pool))[:PICKS]

    def _meal(self, uci: str) -> int:
        victim = self.board.piece_type_at(chess.parse_square(uci[2:4]))
        return VALUE[victim] if victim else 0

    def _push(self, uci: str) -> int:
        check = bool(moved(self.board, uci).is_check())
        return 10 * check + int(uci[3]) - int(uci[1])

    def _points(self, uci: str) -> int:
        return move_points(self.best - self.key[uci])

    def _total(self, picks: list[str]) -> int:
        return sum(self._points(uci) for uci in [*picks, *picks[:1]])

    def on_move(self, uci: str) -> None:
        if uci in self.picks:
            self.say("info", "You already named that one.")
            return
        self.picks.append(uci)
        self.feedback = None
        if len(self.picks) < PICKS:
            return
        mine, top = self._total(self.picks), max(self._total(p) for p in self.rivals.values())
        if mine >= top:
            result = "you beat every duck!" if mine > top else "a tie for first!"
            self.win_round(mine, f"{mine} points: {result}")
        else:
            self.score += mine
            self.say("info", f"{mine} points. The best duck got {top}.")
            self.phase = "review"

    def on_choice(self, choice: str) -> None:
        self.picks.pop()

    def _row(self, who: str, picks: list[str]) -> str:
        shown = ", ".join(f"{san(self.board, uci)} ({self._points(uci)})" for uci in picks)
        return f"{who}: {shown}"

    def view(self) -> View:
        arrows = [Arrow(*squares(uci)) for uci in self.picks]
        if self.phase == "play":
            notes = [f"{i}. {san(self.board, uci)}" for i, uci in enumerate(self.picks, 1)]
        else:
            notes = [
                f"{self._row(who, picks)} = {self._total(picks)}"
                for who, picks in [("You", self.picks), *self.rivals.items()]
            ]
            order = sorted(self.key, key=lambda uci: (-self.key[uci], uci))[:PICKS]
            notes.append(self._row("Engine", order))
            arrows.append(Arrow(*squares(order[0]), "good"))
        return View(
            f"White to move. Name move {min(len(self.picks) + 1, PICKS)} of {PICKS}, best first.",
            BoardView(self.board.fen()),
            moves=legal_ucis(self.board),
            arrows=arrows,
            choices=[Choice("undo", "Take back the last pick")] if self.picks else [],
            notes=notes,
        )
