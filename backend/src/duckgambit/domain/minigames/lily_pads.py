"""Lily Pads: one piece, every breadcrumb, as few hops as possible."""

from __future__ import annotations

import random
from collections import deque

import chess

from duckgambit.domain.minigames.base import (
    BoardView,
    Choice,
    Info,
    Mark,
    Minigame,
    Squares,
    View,
    pick,
    squares,
)

# One round each: your piece, how many crumbs, which black pieces stand guard.
LEVELS: list[tuple[int, int, list[int]]] = [
    (chess.ROOK, 3, []),
    (chess.BISHOP, 3, []),
    (chess.PAWN, 3, []),
    (chess.KNIGHT, 3, []),
    (chess.KING, 2, [chess.ROOK]),
    (chess.QUEEN, 4, [chess.KNIGHT]),
    (chess.KNIGHT, 3, [chess.BISHOP, chess.PAWN]),
]


class LilyPads(Minigame):
    info = Info(
        "lily-pads",
        "Lily Pads",
        "Hop one piece around the pond and eat every breadcrumb.",
        "How each piece moves, then how to avoid attacked squares",
        "Move the white piece. Eat all the crumbs in as few hops as you can. From round 5, "
        "black pieces stand guard: landing on a square they attack costs a heart.",
    )
    rounds = len(LEVELS)

    def start_round(self, rng: random.Random) -> None:
        self.piece, crumbs, guards = LEVELS[self.round]
        while True:
            if self.piece == chess.PAWN:
                self._lay_pawn_trail(rng)
            else:
                self._scatter(rng, crumbs, guards)
            best = self._solve()
            if best is not None:
                break
        self.par, self.hops = best, 0
        self.start = (self.at, self.crumbs)
        self.last: Squares | None = None

    def _lay_pawn_trail(self, rng: random.Random) -> None:
        file, rank = pick(rng, list(range(8))), 1
        self.at = chess.square(file, rank)
        self.guards: dict[int, int] = {}
        crumbs = set()
        for step in range(5):
            rank += 1
            if step in (1, 3, 4):
                file += pick(rng, [d for d in (-1, 1) if 0 <= file + d <= 7])
                crumbs.add(chess.square(file, rank))
        self.crumbs = frozenset(crumbs)

    def _scatter(self, rng: random.Random, count: int, guards: list[int]) -> None:
        spots: list[int] = []
        while len(spots) < 1 + count + len(guards):
            square = pick(rng, list(chess.SQUARES))
            if square not in spots:
                spots.append(square)
        self.at = spots[0]
        self.crumbs = frozenset(spots[1 : 1 + count])
        self.guards = dict(zip(spots[1 + count :], guards, strict=True))

    def _board(self, at: int) -> chess.Board:
        board = chess.Board(None)
        board.set_piece_at(at, chess.Piece(self.piece, chess.WHITE))
        for square, kind in self.guards.items():
            board.set_piece_at(square, chess.Piece(kind, chess.BLACK))
        return board

    def _hops(self, at: int, crumbs: frozenset[int]) -> list[int]:
        if self.piece != chess.PAWN:
            return [s for s in self._board(at).attacks(at) if s not in self.guards]
        # For the pawn, crumbs act as pieces: they block ahead and are eaten sideways.
        hops = [s for s in self._board(at).attacks(at) if s in crumbs]
        ahead = at + 8
        if ahead < 64 and ahead not in crumbs:
            hops.append(ahead)
            if chess.square_rank(at) == 1 and at + 16 not in crumbs:
                hops.append(at + 16)
        return hops

    def _guarded(self, square: int) -> bool:
        return bool(self._board(square).is_attacked_by(chess.BLACK, square))

    def _solve(self) -> int | None:
        """Fewest hops that eat everything without being snapped (None: impossible)."""
        if self._guarded(self.at):
            return None
        seen = {(self.at, self.crumbs)}
        queue = deque([(self.at, self.crumbs, 0)])
        while queue:
            at, crumbs, hops = queue.popleft()
            if not crumbs:
                return hops
            for to in self._hops(at, crumbs):
                state = (to, crumbs - {to})
                if state not in seen and not self._guarded(to):
                    seen.add(state)
                    queue.append((*state, hops + 1))
        return None

    def on_move(self, uci: str) -> None:
        to = chess.parse_square(uci[2:4])
        if self._guarded(to):
            self.lose_heart(f"Snap! {uci[2:4]} is attacked. Back you go.")
            return
        self.hops += 1
        self.last = squares(uci)
        self.at, self.crumbs = to, self.crumbs - {to}
        self.feedback = None
        if not self.crumbs:
            over = self.hops - self.par
            text = "Perfect: it cannot be done faster!" if over == 0 else f"{over} over par."
            self.win_round(max(1, 5 - over), f"All eaten in {self.hops}. {text}")
        elif not self._hops(self.at, self.crumbs):
            self.say("info", "Stuck! Start this pond again.")

    def on_choice(self, choice: str) -> None:
        self.at, self.crumbs = self.start
        self.hops, self.last = 0, None
        self.say("info", "Back to the first pad.")

    def view(self) -> View:
        name = chess.square_name(self.at)
        hops = self._hops(self.at, self.crumbs) if self.phase == "play" else []
        marks = [Mark(chess.square_name(s), "crumb") for s in sorted(self.crumbs)]
        return View(
            f"Eat every crumb with your {chess.piece_name(self.piece)}.",
            BoardView(self._board(self.at).fen(), last_move=self.last),
            moves=sorted(name + chess.square_name(s) for s in hops),
            marks=marks,
            choices=[Choice("restart", "Start this pond again")],
            notes=[f"Hops: {self.hops}", f"Par: {self.par}"],
        )
