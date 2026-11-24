"""PGN export with per-move metadata (ADR-0007).

Uses the standard `[%eval ...]` and `[%clk ...]` comment annotations so the file opens
cleanly in other tools, plus a short note on where the move came from.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess
import chess.pgn

from duckgambit.domain.chessutil import board_from, parse_move


@dataclass(frozen=True)
class PgnMove:
    uci: str
    source: str
    cp: int | None  # from the mover's point of view
    mate: int | None
    clock_ms: int | None
    note: str | None = None


@dataclass(frozen=True)
class PgnGame:
    event: str
    site: str
    date: str  # YYYY.MM.DD
    round: str
    white: str
    black: str
    result: str
    termination: str
    time_control: str
    initial_fen: str
    seed: int
    rating_context: str
    engine: str
    moves: tuple[PgnMove, ...]


_TERMINATION_TEXT = {
    "time_forfeit": "Time forfeit",
    "ply_cap": "Adjudication",
    "abandoned": "Abandoned",
}


def _clock(clock_ms: int) -> str:
    seconds = max(0, clock_ms) // 1000
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _eval(cp: int | None, mate: int | None, white_to_move: bool) -> str | None:
    sign = 1 if white_to_move else -1
    if mate is not None:
        return f"#{sign * mate}"
    if cp is not None:
        return f"{sign * cp / 100:.2f}"
    return None


def export_pgn(game: PgnGame) -> str:
    board = board_from(game.initial_fen)
    pgn = chess.pgn.Game()
    pgn.headers.clear()
    headers = {
        "Event": game.event,
        "Site": game.site,
        "Date": game.date,
        "Round": game.round,
        "White": game.white,
        "Black": game.black,
        "Result": game.result,
        "TimeControl": game.time_control,
        "Termination": _TERMINATION_TEXT.get(game.termination, "Normal"),
        "Annotator": game.engine,
        "Seed": str(game.seed),
        "RatingContext": game.rating_context,
    }
    if game.initial_fen != chess.STARTING_FEN:
        headers["SetUp"] = "1"
        headers["FEN"] = game.initial_fen
        pgn.setup(board)
    for key, value in headers.items():
        pgn.headers[key] = value

    node: chess.pgn.GameNode = pgn
    for move in game.moves:
        white_to_move = board.turn == chess.WHITE
        parsed = parse_move(board, move.uci)
        parts = []
        evaluation = _eval(move.cp, move.mate, white_to_move)
        if evaluation is not None:
            parts.append(f"[%eval {evaluation}]")
        if move.clock_ms is not None:
            parts.append(f"[%clk {_clock(move.clock_ms)}]")
        if move.source != "engine":
            parts.append(move.source)
        if move.note:
            parts.append(move.note)
        node = node.add_variation(parsed, comment=" ".join(parts))
        board.push(parsed)

    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True, columns=80)
    return str(pgn.accept(exporter)) + "\n"
