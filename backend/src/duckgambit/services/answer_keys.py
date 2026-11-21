"""Answer-key generation for puzzle packs (spec 7.4, ADR-0009).

SKELETON FOR M4. It scores every legal move of every puzzle with a fixed Judge and
writes the verdicts into the pack. This version is sequential and has no resume;
parallel leases, checkpoints after each puzzle and pack building from the Lichess
database are the M4 session.

One Judge search per legal move, on the position after that move, so every move gets
the same effort. Scores are stored from the solver's point of view.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from duckgambit.domain.chessutil import board_from
from duckgambit.domain.engine_types import Candidate, SearchRequest
from duckgambit.services.ports import EnginePool


@dataclass(frozen=True)
class JudgeConfig:
    engine_id: str
    nodes: int = 2_000_000
    hash_mb: int = 64


def _from_solver_side(reply: Candidate | None, solver_delivered_mate: bool) -> dict[str, Any]:
    """Flip the opponent's best reply into the solver's point of view."""
    if solver_delivered_mate or reply is None:
        return {"wdl": [1000, 0, 0], "cp": None, "mate": 1}
    wdl = list(reversed(reply.wdl)) if reply.wdl is not None else [0, 1000, 0]
    mate = None
    if reply.mate is not None:
        # The opponent is mated in N: the solver mates in N + 1. The opponent mates: negative.
        mate = -reply.mate + 1 if reply.mate < 0 else -reply.mate
    return {"wdl": wdl, "cp": None if reply.cp is None else -reply.cp, "mate": mate}


async def build_answer_keys(
    pack: dict[str, Any], pool: EnginePool, judge: JudgeConfig
) -> dict[str, Any]:
    """Return a copy of the pack document with an answer key for every puzzle."""
    identity = await pool.identity(judge.engine_id)
    puzzles = []
    async with pool.lease(judge.engine_id, judge.hash_mb) as engine:
        for puzzle in pack["puzzles"]:
            board = board_from(puzzle["fen"])
            key: dict[str, Any] = {}
            for move in sorted(board.legal_moves, key=lambda m: m.uci()):
                after = board.copy(stack=False)
                after.push(move)
                if after.is_checkmate():
                    key[move.uci()] = _from_solver_side(None, solver_delivered_mate=True)
                elif after.is_game_over(claim_draw=False):
                    key[move.uci()] = {"wdl": [0, 1000, 0], "cp": 0, "mate": None}
                else:
                    result = await engine.search(
                        SearchRequest(board.fen(), (move.uci(),), multipv=1, nodes=judge.nodes)
                    )
                    key[move.uci()] = _from_solver_side(result.candidates[0], False)
            puzzles.append({**puzzle, "fen": board.fen(), "answerKey": key})
    return {
        **pack,
        "judge": {
            "engine": judge.engine_id,
            "version": identity.version if identity else None,
            "fingerprint": identity.fingerprint if identity else None,
            "limit": {"type": "nodes", "value": judge.nodes},
            "wdl": True,
        },
        "puzzles": puzzles,
    }
