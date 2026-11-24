"""Pawn Race: first to bring a pawn to the far side wins."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    BoardView,
    Choice,
    Info,
    Minigame,
    View,
    moved,
    squares,
)

# Start positions: pawns alone, then all eight, then with kings.
LEVELS = [
    "8/2ppp3/8/8/8/8/2PPP3/8 w - - 0 1",
    "8/pppppppp/8/8/8/8/PPPPPPPP/8 w - - 0 1",
    "4k3/1pppppp1/8/8/8/8/1PPPPPP1/4K3 w - - 0 1",
]
DEPTH = 3  # [PH] how far the rival looks ahead, in single moves
MAX_MOVES = 40  # [PH] kings could shuffle forever
WIN = 10_000


def race_moves(board: chess.Board) -> list[chess.Move]:
    """Legal moves; a pawn that arrives always becomes a queen (the race is over anyway)."""
    moves = [m for m in board.legal_moves if m.promotion in (None, chess.QUEEN)]
    return sorted(moves, key=lambda m: (not board.is_capture(m), m.uci()))


def race_over(board: chess.Board) -> str:
    """'white' or 'black' has won, 'stuck' when the side to move cannot, '' to go on."""
    queens = (
        board.pieces_mask(chess.QUEEN, chess.WHITE),
        board.pieces_mask(chess.QUEEN, chess.BLACK),
    )
    if queens[0] or not board.pieces_mask(chess.PAWN, chess.BLACK):
        return "white"
    if queens[1] or not board.pieces_mask(chess.PAWN, chess.WHITE):
        return "black"
    if not any(True for _ in board.legal_moves):
        if board.is_checkmate():
            return "black" if board.turn else "white"
        return "stuck"
    return ""


def worth(board: chess.Board) -> int:
    """For White: pawns count, and the further along the better."""
    total = 0
    for square in board.pieces(chess.PAWN, chess.WHITE):
        total += 10 + chess.square_rank(square) ** 2
    for square in board.pieces(chess.PAWN, chess.BLACK):
        total -= 10 + (7 - chess.square_rank(square)) ** 2
    return total


def search(board: chess.Board, depth: int, low: int, high: int) -> int:
    """Alpha-beta for the side to move, over the race's own rules."""
    over = race_over(board)
    if over == "stuck":
        return 0
    if over:
        return (WIN + depth) * (1 if (over == "white") == board.turn else -1)
    if depth == 0:
        return worth(board) if board.turn else -worth(board)
    for move in race_moves(board):
        low = max(low, -search(moved(board, move.uci()), depth - 1, -high, -low))
        if low >= high:
            break
    return low


def rival_move(board: chess.Board) -> chess.Move:
    scored = [
        (-search(moved(board, m.uci()), DEPTH - 1, -2 * WIN, 2 * WIN), m.uci())
        for m in race_moves(board)
    ]
    return chess.Move.from_uci(max(scored)[1])


class PawnRace(Minigame):
    info = Info(
        "pawn-race",
        "Pawn Race",
        "Just pawns. First to the other side wins.",
        "Pawn moves, captures, blocking, and passed pawns",
        "You are White. Win by reaching the far side first or by eating every black pawn. If "
        "somebody cannot move, or after 40 moves, the race is a tie and starts again for free. "
        "Round 3 adds kings.",
    )
    rounds = len(LEVELS)

    def start_round(self, rng: random.Random) -> None:
        self.board = chess.Board(LEVELS[self.round])
        self.last = ""

    def on_move(self, uci: str) -> None:
        self.feedback = None
        self._push(uci)
        if not race_over(self.board):
            reply = rival_move(self.board).uci()
            self.add_frames(self.board, [reply])
            self._push(reply)
        over = race_over(self.board)
        if not over and self.board.fullmove_number > MAX_MOVES:
            over = "stuck"
        if over == "white":
            self.win_round(3, "You won the race!")
        elif over == "black":
            self._again("Black won this race.", lost=True)
        elif over == "stuck":
            self._again("Nobody can get through: a tie.", lost=False)

    def _push(self, uci: str) -> None:
        self.board, self.last = moved(self.board, uci), uci

    def _again(self, text: str, *, lost: bool) -> None:
        if lost:
            self.lose_heart(text)
        else:
            self.say("info", f"{text} Race again.")
        if self.phase == "play":
            if lost:
                self.say("bad", f"{text} Race again.")
            self.board, self.last = chess.Board(LEVELS[self.round]), ""

    def on_choice(self, choice: str) -> None:
        self._again("You gave up.", lost=True)

    def view(self) -> View:
        return View(
            "Race a pawn to the far side.",
            BoardView(
                self.board.fen(),
                check=self.board.is_check(),
                last_move=squares(self.last) if self.last else None,
            ),
            moves=[m.uci() for m in race_moves(self.board)],
            choices=[Choice("restart", "Start this race again", "Costs a heart")],
        )
