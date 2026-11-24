"""Small chess helpers shared across the domain."""

from __future__ import annotations

import re
from dataclasses import dataclass

import chess

from duckgambit.domain.errors import DomainError

UCI_MOVE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


def position_key(board: chess.Board) -> str:
    """Pieces, side to move, castling rights and en passant (only when a capture is legal).

    This is the key for repertoire and puzzle memory: move counters are ignored so the
    same position reached by different move orders matches.
    """
    return str(board.epd(en_passant="legal"))


def board_from(initial_fen: str, moves: tuple[str, ...] = ()) -> chess.Board:
    try:
        board = chess.Board(initial_fen)
    except ValueError as exc:
        raise DomainError("chess.invalid_fen", f"Invalid FEN: {exc}") from exc
    if not board.is_valid():
        raise DomainError("chess.invalid_position", "The position is not legal")
    for uci in moves:
        board.push(parse_move(board, uci))
    return board


def parse_move(board: chess.Board, uci: str) -> chess.Move:
    if not UCI_MOVE.match(uci):
        raise DomainError("chess.invalid_move", f"Not a UCI move: {uci!r}")
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        raise DomainError("chess.illegal_move", f"Illegal move {uci} in {board.fen()}")
    return move


@dataclass(frozen=True)
class MoveFlags:
    capture: bool
    en_passant: bool
    check: bool
    checkmate: bool
    castle: str | None
    promotion: str | None


def move_flags(board: chess.Board, move: chess.Move) -> MoveFlags:
    """Describe a move so that a client without chess rules can animate it."""
    castle = None
    if board.is_kingside_castling(move):
        castle = "kingside"
    elif board.is_queenside_castling(move):
        castle = "queenside"
    after = board.copy(stack=False)
    after.push(move)
    return MoveFlags(
        capture=board.is_capture(move),
        en_passant=board.is_en_passant(move),
        check=after.is_check(),
        checkmate=after.is_checkmate(),
        castle=castle,
        promotion=chess.piece_symbol(move.promotion) if move.promotion else None,
    )


def legal_destinations(board: chess.Board) -> dict[str, list[str]]:
    """Origin square to destination squares, the shape board UIs want."""
    result: dict[str, list[str]] = {}
    for move in board.legal_moves:
        result.setdefault(chess.square_name(move.from_square), []).append(
            chess.square_name(move.to_square)
        )
    return {origin: sorted(set(targets)) for origin, targets in sorted(result.items())}
