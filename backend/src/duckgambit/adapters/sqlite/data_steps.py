"""Python data steps that run inside a migration's transaction (ADR-0004).

Some migrations need values SQL cannot compute, such as a chess position key. A data step
runs right after its migration's SQL, in the same transaction, so the schema change and
the backfill commit together or not at all. Every step must be idempotent: it only
touches rows that still lack the value, so running it twice changes nothing.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable

from duckgambit.domain.chessutil import board_from, parse_move, position_key
from duckgambit.domain.errors import DomainError

log = logging.getLogger(__name__)


def backfill_move_position_keys(connection: sqlite3.Connection) -> int:
    """Fill `moves.position_key` by replaying each game from its initial FEN.

    Returns the number of rows filled. A game that cannot be replayed (bad FEN, an illegal
    or missing ply) keeps NULL keys from that ply on and is logged; it is not an error,
    because the rest of the database is still correct and nothing reads the key for play.
    """
    games = connection.execute(
        "SELECT DISTINCT g.id, g.initial_fen FROM moves m JOIN games g ON g.id = m.game_id"
        " WHERE m.position_key IS NULL ORDER BY g.id"
    ).fetchall()
    filled = 0
    for game_id, initial_fen in games:
        moves = connection.execute(
            "SELECT ply, uci, position_key FROM moves WHERE game_id = ? ORDER BY ply",
            (game_id,),
        ).fetchall()
        updates: list[tuple[str, str, int]] = []
        try:
            board = board_from(initial_fen)
            for expected, (ply, uci, existing) in enumerate(moves, start=1):
                if ply != expected:
                    raise DomainError("chess.missing_ply", f"ply {expected} is missing")
                move = parse_move(board, uci)  # an unplayable row keeps NULL, like the rest
                if existing is None:
                    updates.append((position_key(board), game_id, ply))
                board.push(move)
        except DomainError as exc:
            log.warning("Cannot replay game %s for position keys: %s", game_id, exc.code)
        connection.executemany(
            "UPDATE moves SET position_key = ? WHERE game_id = ? AND ply = ?", updates
        )
        filled += len(updates)
    if filled:
        log.info("Backfilled position keys for %d moves in %d games", filled, len(games))
    return filled


DataStep = Callable[[sqlite3.Connection], object]

# Migration version -> the step that runs after its SQL, inside the same transaction.
DATA_STEPS: dict[int, DataStep] = {
    2: backfill_move_position_keys,
}
