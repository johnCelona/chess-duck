"""Pawn Race: first to bring a pawn to the far side wins."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    BoardView,
    Choice,
    Frame,
    Info,
    Level,
    Minigame,
    Tone,
    View,
    deal,
    moved,
    pick,
    squares,
)
from duckgambit.domain.minigames.pawn_races import EASY, HARD_LOSING, HARD_WINNING

# Start positions: pawns alone, then all eight, then with kings.
LEVELS = [
    "8/2ppp3/8/8/8/8/2PPP3/8 w - - 0 1",
    "8/pppppppp/8/8/8/8/PPPPPPPP/8 w - - 0 1",
    "4k3/1pppppp1/8/8/8/8/1PPPPPP1/4K3 w - - 0 1",
]
DEPTH = 3  # [PH] how far the rival looks ahead, in single moves
EASY_DEPTH = 1  # [PH] the easy rival
HARD_DEPTH = 5  # [PH] the hard rival
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


def rival_move(board: chess.Board, depth: int = DEPTH) -> chess.Move:
    scored = [
        (-search(moved(board, m.uci()), depth - 1, -2 * WIN, 2 * WIN), m.uci())
        for m in race_moves(board)
    ]
    return chess.Move.from_uci(max(scored)[1])


class PawnRace(Minigame):
    info = Info(
        "pawn-race",
        "Pawn Race",
        "Just pawns. First to the other side wins.",
        "Pawn endings: passed pawns, blocking, and forcing a move they do not want to make",
        "You are White. Win by reaching the far side first or by eating every black pawn. If "
        "somebody cannot move, or after 40 moves, the race is a tie and starts again for free. "
        "On Hard, when you start in a losing position, a tie counts as a win.",
        (
            Level("easy", "Easy", "Always winnable, with many good first moves"),
            Level("medium", "Medium", "The classic three races; the last adds kings"),
            Level("hard", "Hard", "Dealt positions, some of them losing, and a sharper rival"),
        ),
        "medium",
    )

    def __init__(self, seed: int, level: str = "") -> None:
        self.rounds = len(LEVELS) if (level or self.info.level) == "medium" else 5
        super().__init__(seed, level)

    def start_round(self, rng: random.Random) -> None:
        self.losing = False
        self.depth = {"easy": EASY_DEPTH, "hard": HARD_DEPTH}.get(self.level, DEPTH)
        if self.level == "medium":
            self.start = chess.Board(LEVELS[self.round])
        else:
            deck = EASY
            if self.level == "hard":
                # Three winning and two losing starts, in a shuffled order.
                sides = [False, False, False, True, True]
                self.losing = deal(self.seed, "sides", sides, self.round)
                deck = HARD_LOSING if self.losing else HARD_WINNING
            self.start = chess.Board(deal(self.seed, self.level, deck, self.round))
            if not self.losing and pick(rng, [False, True]):
                # Mirrored, a race is just as winnable. A losing one is not touched: it was
                # checked against this rival's exact replies.
                self.start = self.start.transform(chess.flip_horizontal)
        self.board, self.last = self.start, ""

    def on_move(self, uci: str) -> None:
        self.feedback = None
        self._push(uci)
        if not race_over(self.board):
            # No animation frame: the reply just appears, so the player can move at once.
            self._push(rival_move(self.board, self.depth).uci())
        over = race_over(self.board)
        if not over and self.board.fullmove_number > MAX_MOVES:
            over = "stuck"
        if over == "white":
            text = "You won a losing race! Brilliant." if self.losing else "You won the race!"
            self.win_round(5 if self.losing else 3, text)
        elif over == "stuck" and self.losing:
            self.win_round(4, "A tie from a losing position counts as a win. Well held!")
        elif over == "black":
            self.lose_heart("Black won this race.")
            self._again("Black won this race.", "bad")
        elif over == "stuck":
            self._again("Nobody can get through: a tie.", "info")

    def _push(self, uci: str) -> None:
        self.board, self.last = moved(self.board, uci), uci

    def _again(self, text: str, tone: Tone) -> None:
        if self.phase == "play":
            if self.last:  # show how it ended before the board resets
                self.frames.append(Frame(self.board.fen(), squares(self.last), text))
            self.say(tone, f"{text} Race again.")
            self.board, self.last = self.start, ""

    def on_choice(self, choice: str) -> None:
        self.lose_heart("You gave up.")
        self._again("You gave up.", "bad")

    def view(self) -> View:
        prompt, notes = "Race a pawn to the far side.", []
        if self.losing:
            prompt = "You are losing this one! Hold a tie, or somehow win."
            notes = ["A tie counts as a win here"]
        elif self.level != "medium":
            notes = ["Proven: White can win this one"]
        return View(
            prompt,
            BoardView(
                self.board.fen(),
                check=self.board.is_check(),
                last_move=squares(self.last) if self.last else None,
            ),
            moves=[m.uci() for m in race_moves(self.board)],
            choices=[Choice("restart", "Start this race again", "Costs a heart")],
            notes=notes,
        )
