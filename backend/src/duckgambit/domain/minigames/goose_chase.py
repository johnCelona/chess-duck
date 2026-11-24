"""Goose Chase: a lone king runs. Corner it and checkmate before the moves run out."""

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
    legal_ucis,
    moved,
    pick,
    squares,
)

# Your pieces, and how many moves you get [PH].
LEVELS: list[tuple[list[int], int]] = [
    ([chess.ROOK, chess.ROOK], 16),
    ([chess.QUEEN], 20),
    ([chess.ROOK], 35),
]


def runaway(board: chess.Board) -> chess.Move:
    """The goose's move: eat a loose piece, else stay central with room to run.

    A fixed rule, not an engine search, so it costs nothing and always replays the same.
    """

    def appeal(move: chess.Move) -> tuple[bool, int, int, str]:
        file, rank = chess.square_file(move.to_square), chess.square_rank(move.to_square)
        from_edge = min(file, 7 - file) + min(rank, 7 - rank)
        after = moved(board, move.uci())
        return board.is_capture(move), from_edge, len(free_squares(after)), move.uci()

    return max(board.legal_moves, key=appeal)


def free_squares(board: chess.Board) -> list[int]:
    """Where the lone king could step. Seen without its own body, which shields nothing."""
    goose = board.king(chess.BLACK)
    assert goose is not None
    bare = board.copy(stack=False)
    bare.remove_piece_at(goose)
    return [s for s in board.attacks(goose) if not bare.is_attacked_by(chess.WHITE, s)]


class GooseChase(Minigame):
    info = Info(
        "goose-chase",
        "Goose Chase",
        "Herd a runaway king to the edge and checkmate it.",
        "The basic mates: two rooks, a queen, one rook. And not stalemating!",
        "You are White. Checkmate the lone king before your moves run out. The marked squares "
        "are where it can still run: shrink its space. Stalemate lets it escape.",
    )
    rounds = len(LEVELS)

    def start_round(self, rng: random.Random) -> None:
        pieces, self.budget = LEVELS[self.round]
        while True:
            board = chess.Board(None)
            goose = chess.square(pick(rng, [2, 3, 4, 5]), pick(rng, [3, 4, 5]))
            board.set_piece_at(goose, chess.Piece(chess.KING, chess.BLACK))
            for kind in (chess.KING, *pieces):
                free = [s for s in chess.SQUARES if not board.piece_at(s)]
                board.set_piece_at(pick(rng, free), chess.Piece(kind, chess.WHITE))
            near = [s for s in board.attacks(goose) if board.piece_at(s)]
            if board.is_valid() and not near:
                break
        self.board = self.start = board
        self.used, self.last = 0, ""

    def on_move(self, uci: str) -> None:
        self.board, self.last, self.used = moved(self.board, uci), uci, self.used + 1
        self.feedback = None
        if self.board.is_checkmate():
            spare = self.budget - self.used
            self.win_round(2 + spare // 2, f"Checkmate with {spare} moves to spare!")
        elif self.board.is_stalemate():
            self._fail("Stalemate! It cannot move but is not in check: a draw.")
        else:
            reply = runaway(self.board)
            eaten = self.board.is_capture(reply)
            self.board, self.last = moved(self.board, reply.uci()), reply.uci()
            if eaten:
                self._fail("It ate your piece!")
            elif self.used >= self.budget:
                self._fail("Out of moves. It got away.")

    def _fail(self, text: str) -> None:
        self.lose_heart(text)
        if self.phase == "play":
            if self.last:  # show how it ended before the board resets
                self.frames.append(Frame(self.board.fen(), squares(self.last), text))
            self.board, self.used, self.last = self.start, 0, ""
            self.say("bad", f"{text} Try the same chase again.")

    def on_choice(self, choice: str) -> None:
        self._fail("You let it go.")

    def view(self) -> View:
        board = self.board
        run = free_squares(board)
        return View(
            "Checkmate the runaway king!",
            BoardView(
                board.fen(),
                check=board.is_check(),
                last_move=squares(self.last) if self.last else None,
            ),
            moves=legal_ucis(board),
            marks=[Mark(chess.square_name(s), "target") for s in run],
            choices=[Choice("restart", "Start this chase again", "Costs a heart")],
            notes=[f"Moves left: {self.budget - self.used}", f"Squares it can run to: {len(run)}"],
        )
