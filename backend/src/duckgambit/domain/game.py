"""Game results and how a game ends."""

from __future__ import annotations

from dataclasses import dataclass

import chess

WHITE_WINS = "1-0"
BLACK_WINS = "0-1"
DRAW = "1/2-1/2"

# Every termination a game record may carry. `resignation` and `abandoned` are reserved
# for games with a human participant (sparring, bullet battle); duck-vs-duck never uses them.
TERMINATIONS = (
    "checkmate",
    "stalemate",
    "insufficient_material",
    "threefold_repetition",
    "fifty_move_rule",
    "time_forfeit",
    "ply_cap",
    "resignation",
    "abandoned",
)

_TERMINATION_NAMES = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.THREEFOLD_REPETITION: "threefold_repetition",
    chess.Termination.FIVEFOLD_REPETITION: "threefold_repetition",
    chess.Termination.FIFTY_MOVES: "fifty_move_rule",
    chess.Termination.SEVENTYFIVE_MOVES: "fifty_move_rule",
}


@dataclass(frozen=True)
class Outcome:
    result: str
    termination: str

    @property
    def winner(self) -> str | None:
        """ "white", "black" or None for a draw."""
        if self.result == WHITE_WINS:
            return "white"
        if self.result == BLACK_WINS:
            return "black"
        return None


def outcome_of(board: chess.Board, max_plies: int) -> Outcome | None:
    """The outcome if the game is over. Draw claims are made automatically."""
    outcome = board.outcome(claim_draw=True)
    if outcome is not None:
        if outcome.winner is None:
            result = DRAW
        else:
            result = WHITE_WINS if outcome.winner == chess.WHITE else BLACK_WINS
        return Outcome(result, _TERMINATION_NAMES.get(outcome.termination, "stalemate"))
    if len(board.move_stack) >= max_plies:
        return Outcome(DRAW, "ply_cap")
    return None


def time_forfeit(loser_is_white: bool) -> Outcome:
    return Outcome(BLACK_WINS if loser_is_white else WHITE_WINS, "time_forfeit")


def points(result: str, color: str) -> float:
    if result == DRAW:
        return 0.5
    return 1.0 if (result == WHITE_WINS) == (color == "white") else 0.0


def timeout(board: chess.Board, loser_is_white: bool) -> Outcome:
    """Out of time: a loss, unless the opponent cannot possibly mate, which is a draw."""
    winner = chess.BLACK if loser_is_white else chess.WHITE
    if board.has_insufficient_material(winner):
        return Outcome(DRAW, "timeout_vs_insufficient_material")
    return time_forfeit(loser_is_white)


def resignation(loser_is_white: bool) -> Outcome:
    return Outcome(BLACK_WINS if loser_is_white else WHITE_WINS, "resignation")
