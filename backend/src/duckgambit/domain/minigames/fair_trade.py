"""Fair Trade?: is this capture a good deal? Count the whole exchange before you take."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    VALUE,
    Arrow,
    BoardView,
    Choice,
    Info,
    Mark,
    Minigame,
    View,
    moved,
    name_at,
    pick,
    squares,
)

VICTIMS = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]
HELPERS = [chess.PAWN, chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]


def exchange(board: chess.Board, target: int) -> tuple[int, list[str]]:
    """Most points the side to move can win on `target`; declining is worth 0."""
    best: tuple[int, list[str]] = (0, [])
    for move in board.legal_moves:
        # No trade promotes: the victims stand on ranks 3 to 6.
        if move.to_square == target:
            offer = capture_value(board, move)
            if offer[0] > best[0]:
                best = offer
    return best


def capture_value(board: chess.Board, move: chess.Move) -> tuple[int, list[str]]:
    """Points won by this capture after the best recaptures on the same square."""
    victim = board.piece_type_at(move.to_square)
    assert victim is not None
    reply, line = exchange(moved(board, move.uci()), move.to_square)
    return VALUE[victim] - reply, [move.uci(), *line]


class FairTrade(Minigame):
    info = Info(
        "fair-trade",
        "Fair Trade?",
        "Take it or leave it: 60 seconds of quick deals.",
        "What pieces are worth, and counting attackers and defenders",
        "The arrow shows a capture White could play. Count who takes back: is it good for "
        "White, an even swap, or a bad deal? Pawn 1, knight 3, bishop 3, rook 5, queen 9. "
        "The clock stops while you read the answer.",
    )
    rounds = 40
    time_limit_ms = 60_000
    streak = 0

    def start_round(self, rng: random.Random) -> None:
        want = pick(rng, ["good", "bad", "bad", "even"])
        while True:
            found = self._random_deal(rng)
            if found is None:
                continue
            self.board, self.move, self.value, self.line = found
            self.answer = "good" if self.value > 0 else "bad" if self.value < 0 else "even"
            if self.answer == want:
                return

    def _random_deal(
        self, rng: random.Random
    ) -> tuple[chess.Board, chess.Move, int, list[str]] | None:
        target = chess.square(pick(rng, list(range(8))), pick(rng, [2, 3, 4, 5]))
        board = chess.Board("6k1/8/8/8/8/8/8/6K1 w - - 0 1")
        board.set_piece_at(target, chess.Piece(pick(rng, VICTIMS), chess.BLACK))
        white, black = pick(rng, [1, 2, 2, 3]), pick(rng, [0, 1, 1, 2])
        for color, count in ((chess.WHITE, white), (chess.BLACK, black)):
            for _ in range(count):
                kind = pick(rng, HELPERS)
                # The squares this piece would capture `target` from, on an empty board.
                probe = chess.Board(None)
                probe.set_piece_at(target, chess.Piece(kind, not color))
                spots = [
                    s
                    for s in probe.attacks(target)
                    if not board.piece_at(s)
                    and (kind != chess.PAWN or 1 <= chess.square_rank(s) <= 6)
                ]
                if spots:
                    board.set_piece_at(pick(rng, spots), chess.Piece(kind, color))
        if not board.is_valid() or board.is_check():
            return None
        takes = [
            m
            for m in board.legal_moves
            if m.to_square == target and board.piece_type_at(m.from_square) != chess.KING
        ]
        if not takes:
            return None
        move = pick(rng, takes)
        return (board, move, *capture_value(board, move))

    def on_choice(self, choice: str) -> None:
        self.add_frames(self.board, self.line)
        worth = f"{self.value:+d}" if self.value else "0"
        if choice == self.answer:
            self.streak += 1
            self.win_round(
                min(self.streak, 5), f"Right! It is worth {worth} to White. Streak {self.streak}."
            )
        else:
            self.streak = 0
            self.lose_heart(f"Not quite: it is worth {worth} to White.", ends_round=True)

    def view(self) -> View:
        origin, target = squares(self.move.uci())
        board, shown = self.board, BoardView(self.board.fen())
        if self.phase == "review":
            after = board
            for uci in self.line:
                after = moved(after, uci)
            shown = BoardView(after.fen(), last_move=squares(self.line[-1]))
        return View(
            f"Your {name_at(board, self.move.from_square)} can take the "
            f"{name_at(board, self.move.to_square)} on {target}. Good deal?",
            shown,
            marks=[Mark(target, "target")],
            arrows=[Arrow(origin, target)] if self.phase == "play" else [],
            choices=[
                Choice("good", "Good deal", "White comes out ahead"),
                Choice("even", "Even swap", "Nobody gains"),
                Choice("bad", "Bad deal", "White loses points"),
            ],
            notes=[f"Streak: {self.streak}"],
        )
