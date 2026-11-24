"""One duck move: plan → (search) → choose, under a node or virtual-clock limit.

Shared by the match runner and by interactive games against a human (ADR-0015), so a
duck decides the same way everywhere. The result depends only on the board (its move
history), the duck, the limit and the seed: never on wall-clock time.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from duckgambit.domain.arena import Limit, VirtualClockLimit
from duckgambit.domain.balance import Balance
from duckgambit.domain.chessutil import position_key
from duckgambit.domain.clock import nodes_for, scale_nodes, think_budget_ms
from duckgambit.domain.decision import Decision, SearchBudget, choose, plan
from duckgambit.domain.duck import Duck
from duckgambit.services.ports import Engine


@dataclass(frozen=True)
class DuckTurn:
    decision: Decision
    think_ms: int  # virtual think time to charge to the duck's clock (0 without a clock)
    nodes_budget: int
    position_key: str  # of the board before the move


async def decide_duck_move(
    engine: Engine,
    board: chess.Board,
    duck: Duck,
    *,
    color: str,
    limit: Limit,
    remaining_ms: int | None,
    multipv: int,
    equal_engine: bool,
    seed: int,
    balance: Balance,
    max_nodes: int,
) -> DuckTurn:
    policy = balance.clock
    mind = duck.mind(balance)
    multiplier = 1000 if equal_engine else mind.node_multiplier_milli
    if isinstance(limit, VirtualClockLimit) and remaining_ms is not None:
        think_ms = think_budget_ms(
            remaining_ms, limit.increment_ms, board.fullmove_number, mind, policy
        )
        nodes = nodes_for(think_ms, limit.virtual_nps, multiplier, max_nodes, policy)
    else:
        think_ms = 0
        nodes = scale_nodes(getattr(limit, "nodes", 0), multiplier, max_nodes, policy)

    key = position_key(board)
    planned = plan(
        board,
        mind,
        duck.knowledge.book_moves(color, key),
        SearchBudget(nodes, multipv),
        seed,
        duck.knowledge.taught_move(key),
    )
    if planned.decision is not None:
        decision = planned.decision
        nodes = 0
        if isinstance(limit, VirtualClockLimit):
            think_ms = policy.instant_move_ms
    else:
        assert planned.request is not None
        result = await engine.search(planned.request)
        decision = choose(board, mind, result, seed, planned.notes)
    return DuckTurn(decision, think_ms, nodes, key)
