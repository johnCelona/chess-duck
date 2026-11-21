"""The virtual clock (spec 6.2, ADR-0006).

A duck's think time is a budget in virtual milliseconds that converts to engine
nodes through a fixed nodes-per-second constant. No wall-clock time is involved, so
a bullet game plays out identically on any machine. Integers only.
"""

from __future__ import annotations

from dataclasses import dataclass

from duckgambit.domain.balance import DEFAULT_CLOCK_POLICY, ClockPolicy, MindParams


def think_budget_ms(
    remaining_ms: int,
    increment_ms: int,
    fullmove_number: int,
    mind: MindParams,
    policy: ClockPolicy = DEFAULT_CLOCK_POLICY,
) -> int:
    """How long the duck decides to think, from the time it has left and its speed."""
    moves_left = max(policy.min_moves_left, policy.expected_game_moves - fullmove_number + 1)
    share = remaining_ms // moves_left + increment_ms * policy.increment_share_permille // 1000
    clamped = max(policy.min_think_ms, min(policy.max_think_ms, share))
    return max(policy.min_think_ms, clamped * mind.speed_factor_permille // 1000)


def nodes_for(
    think_ms: int,
    virtual_nps: int,
    node_multiplier_milli: int,
    max_nodes: int,
    policy: ClockPolicy = DEFAULT_CLOCK_POLICY,
) -> int:
    """Convert think time to a node budget. `node_multiplier_milli` is 1000 for 1.0x."""
    nodes = think_ms * virtual_nps // 1000 * node_multiplier_milli // 1000
    return max(policy.min_nodes, min(max_nodes, nodes))


def scale_nodes(
    nodes: int,
    node_multiplier_milli: int,
    max_nodes: int,
    policy: ClockPolicy = DEFAULT_CLOCK_POLICY,
) -> int:
    """Clock-free matches: a fixed node count scaled by the duck's calculation."""
    return max(policy.min_nodes, min(max_nodes, nodes * node_multiplier_milli // 1000))


@dataclass(frozen=True)
class ClockCharge:
    remaining_ms: int
    flagged: bool


def charge(
    remaining_ms: int,
    think_ms: int,
    increment_ms: int,
    policy: ClockPolicy = DEFAULT_CLOCK_POLICY,
) -> ClockCharge:
    """Deduct the budgeted time. Running out loses on time; the increment comes after."""
    spent = think_ms + policy.move_overhead_ms
    if spent >= remaining_ms:
        return ClockCharge(0, True)
    return ClockCharge(remaining_ms - spent + increment_ms, False)
