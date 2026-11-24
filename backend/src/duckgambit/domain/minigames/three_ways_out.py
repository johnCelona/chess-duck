"""Three Ways Out: your king is in check. Run, block and capture: find one of each."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    Arrow,
    BoardView,
    Info,
    Minigame,
    View,
    board_after,
    pick,
    san,
)

WAYS = ("run", "block", "capture")


def way_out(board: chess.Board, move: chess.Move) -> str:
    """Taking the checker is `capture`, also with the king. Any other king move is `run`."""
    if move.to_square in board.checkers() or board.is_en_passant(move):
        return "capture"
    if board.piece_type_at(move.from_square) == chess.KING:
        return "run"
    return "block"


class ThreeWaysOut(Minigame):
    info = Info(
        "three-ways-out",
        "Three Ways Out",
        "Check! Find every kind of escape.",
        "The three answers to check: move the king, block, or capture the checker",
        "White is in check. Find one way to run, one way to block and one way to capture the "
        "checking piece. The board resets after each find. A move that leaves you in check "
        "costs a heart.",
    )

    def start_round(self, rng: random.Random) -> None:
        while True:
            board = self._random_check(rng)
            if board and {way_out(board, m) for m in board.legal_moves} == set(WAYS):
                break
        self.board = board
        self.found: dict[str, str] = {}
        self.hinted = False

    def _random_check(self, rng: random.Random) -> chess.Board | None:
        board = chess.Board(None)
        white, black = chess.WHITE, chess.BLACK
        men = [
            (chess.KING, white),
            (chess.KING, black),
            (pick(rng, [chess.ROOK, chess.BISHOP, chess.QUEEN]), black),
            (pick(rng, [chess.KNIGHT, chess.ROOK]), black),
            (chess.KNIGHT, white),
            (pick(rng, [chess.ROOK, chess.BISHOP]), white),
            (chess.PAWN, white),
            (chess.PAWN, white),
            (chess.PAWN, black),
        ]
        for kind, color in men:
            free = [s for s in chess.SQUARES if not board.piece_at(s)]
            if kind == chess.PAWN:
                free = [s for s in free if 1 <= chess.square_rank(s) <= 6]
            elif kind == chess.KING:
                free = [s for s in free if (chess.square_rank(s) < 3) == color]
            board.set_piece_at(pick(rng, free), chess.Piece(kind, color))
        return board if board.is_valid() and len(board.checkers()) == 1 else None

    def on_move(self, uci: str) -> None:
        move = chess.Move.from_uci(uci)
        if not self.board.is_legal(move):
            self.lose_heart("Still in check after that! Try something else.")
            return
        way = way_out(self.board, move)
        if way in self.found:
            self.say("info", f"True, but you already found a way to {way}.")
            return
        self.found[way] = uci
        self.last = uci
        left = [w for w in WAYS if w not in self.found]
        if left:
            self.say("good", f"You can {way}! Still to find: {' and '.join(left)}.")
        else:
            self.win_round(3, "Run, block, capture: all three ways out!")

    def on_hint(self) -> None:
        self.hinted = True
        self.say("info", "The arrow shows who is giving check.")

    def _note(self, way: str) -> str:
        return san(self.board, self.found[way]) if way in self.found else "?"

    def view(self) -> View:
        checker = next(iter(self.board.checkers()))
        king = self.board.king(chess.WHITE)
        assert king is not None
        board, arrows = BoardView(self.board.fen(), check=True), list[Arrow]()
        if self.phase == "play" and self.hinted:
            arrows = [Arrow(chess.square_name(checker), chess.square_name(king), "bad")]
        elif self.phase == "review" and len(self.found) == len(WAYS):
            board = board_after(self.board, self.last)
        elif self.phase == "review":
            for move in self.board.legal_moves:  # show what was missed
                if way_out(self.board, move) not in self.found:
                    origin, target = move.uci()[:2], move.uci()[2:4]
                    arrows.append(Arrow(origin, target, "good"))
        # Every pseudo-legal move is offered: noticing which ones fail is the lesson.
        return View(
            "Check! Find a way to run, a way to block and a way to capture.",
            board,
            moves=sorted(m.uci() for m in self.board.pseudo_legal_moves),
            arrows=arrows,
            notes=[f"{way.capitalize()}: {self._note(way)}" for way in WAYS],
            can_hint=not self.hinted,
        )
