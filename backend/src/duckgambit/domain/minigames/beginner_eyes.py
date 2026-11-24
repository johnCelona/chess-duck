"""How a beginner duck picks a move: the best one it can see (design 06 §3, experiment).

No engine. Every legal move is scored by simple habits plus the concepts the duck has
learned. A concept it has not learned is a blind spot, so its mistakes have a reason and
are never random. All numbers are placeholders [PH].
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from duckgambit.domain.minigames.base import VALUE, moved, name_at
from duckgambit.domain.seeds import draw_below, rng_for

LOOSE = "loose-pieces"
MATE = "mate-in-one"
CONCEPTS = (LOOSE, MATE)

MATED = 10_000
CENTRE = (chess.D4, chess.E4, chess.D5, chess.E5)


@dataclass(frozen=True)
class Thought:
    move: str
    san: str
    learned: tuple[str, ...]  # what a lesson changed about this move
    missed: tuple[str, ...]  # what it did not notice, and why


def exchange_loss(board: chess.Board, square: int) -> int:
    """Points the side to move wins by capturing on `square`, cheapest piece first."""
    takes = list(board.generate_legal_moves(chess.BB_ALL, chess.BB_SQUARES[square]))
    victim = board.piece_type_at(square)
    if not takes or victim is None:
        return 0
    cheapest = min(takes, key=lambda m: (VALUE[board.piece_type_at(m.from_square) or 1], m.uci()))
    return max(0, VALUE[victim] - exchange_loss(moved(board, cheapest.uci()), square))


def loosest(board: chess.Board) -> tuple[int, int]:
    """The worst piece the side to move can win now: (points, square), or (0, -1)."""
    worst = (0, -1)
    for square in chess.SquareSet(board.occupied_co[not board.turn]):
        if board.piece_type_at(square) == chess.KING or not board.is_attacked_by(
            board.turn, square
        ):
            continue
        worst = max(worst, (exchange_loss(board, square), square))
    return worst


def mate_in_one(board: chess.Board) -> chess.Move | None:
    for move in sorted(board.legal_moves, key=lambda m: m.uci()):
        if board.gives_check(move) and moved(board, move.uci()).is_checkmate():
            return move
    return None


def habits(board: chess.Board, move: chess.Move) -> int:
    """What any beginner likes: taking things, the centre, new pieces, castling, checks."""
    kind = board.piece_type_at(move.from_square)
    score = 0
    if board.is_capture(move):
        score += 80 * VALUE[board.piece_type_at(move.to_square) or chess.PAWN]
    if move.promotion:
        score += 100 * (VALUE[move.promotion] - 1)
    if board.is_castling(move):
        score += 60
    if board.gives_check(move):
        score += 25
    if move.to_square in CENTRE:
        score += 25
    home = 0 if board.turn else 7
    if kind in (chess.KNIGHT, chess.BISHOP):
        score += 40 * (chess.square_rank(move.from_square) == home)
        score -= 30 * (chess.square_rank(move.to_square) == home)
    if kind == chess.KING and not board.is_castling(move):
        score -= 30
    if kind == chess.PAWN:
        score += 10 * (chess.square_file(move.from_square) in (2, 3, 4, 5))
        # A far pawn is exciting.
        rank = chess.square_rank(move.to_square)
        score += 4 * (rank if board.turn else 7 - rank)
    if kind == chess.QUEEN and board.fullmove_number < 6:
        score -= 10
    return score


def scores(board: chess.Board, known: frozenset[str], seed: int) -> dict[str, int]:
    """Each legal move's worth to this duck."""
    rng = rng_for(seed, board.ply(), "beginner")
    result = {}
    for move in sorted(board.legal_moves, key=lambda m: m.uci()):
        # A small seeded taste, so two ducks or two games are not the same.
        score = habits(board, move) + draw_below(rng, 20)
        after = moved(board, move.uci())
        if MATE in known:
            if after.is_checkmate():
                score += MATED
            elif mate_in_one(after):
                score -= MATED
        if LOOSE in known:
            score -= 100 * loosest(after)[0]
        result[move.uci()] = score
    return result


def favourite(scored: dict[str, int]) -> str:
    return max(scored, key=lambda uci: (scored[uci], uci))


def think(board: chess.Board, known: frozenset[str], seed: int) -> Thought:
    move = favourite(scores(board, known, seed))
    after = moved(board, move)
    learned, missed = [], []

    mate = mate_in_one(board)
    if MATE in known:
        without = favourite(scores(board, known - {MATE}, seed))
        if after.is_checkmate() and without != move:
            learned.append("Saw checkmate in one (learned in Crack the Shell).")
        elif without != move and mate_in_one(moved(board, without)):
            learned.append(
                f"Saw that {_san(board, without)} would let you checkmate "
                "(learned in Crack the Shell)."
            )
    else:
        if mate and not after.is_checkmate():
            missed.append(f"Did not notice {board.san(mate)} was checkmate (not learned yet).")
        threat = mate_in_one(after)
        if threat:
            missed.append(
                f"Did not notice you can checkmate with {after.san(threat)} (not learned yet)."
            )

    points, square = loosest(after)
    if LOOSE in known:
        without = favourite(scores(board, known - {LOOSE}, seed))
        loss = loosest(moved(board, without))[0]
        if without != move and loss > points:
            learned.append(
                f"Saw that {_san(board, without)} would let you win {loss} "
                f"point{'s' if loss > 1 else ''} (learned in Loose Feathers)."
            )
    elif points:
        missed.append(
            f"Did not notice its {name_at(after, square)} on {chess.square_name(square)} "
            "can be won (not learned yet)."
        )
    return Thought(move, _san(board, move), tuple(learned), tuple(missed))


def _san(board: chess.Board, uci: str) -> str:
    return str(board.san(chess.Move.from_uci(uci)))
