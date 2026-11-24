"""Balance table and the mapping from a duck's stats to play parameters (ADR-0006).

EVERY NUMBER HERE IS A PLACEHOLDER until the calibration harness (M3) measures it.
Changing any value changes how ducks play, so bump `version`: it is part of the
rating context and ratings from different versions are never mixed.

All arithmetic is integer so that results are identical on every platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STAT_NAMES = ("calculation", "memory", "aggression", "solidity", "creativity", "speed")

# round(1000 * 2 ** (k / 10)) for k in 0..9
_POW2_TENTHS = (1000, 1072, 1149, 1231, 1320, 1414, 1516, 1625, 1741, 1866)


@dataclass(frozen=True)
class Stage:
    name: str
    min_level: int
    stat_cap: int


@dataclass(frozen=True)
class ClockPolicy:
    """How a duck spends a virtual clock. Placeholders until calibration (M3)."""

    expected_game_moves: int = 60
    min_moves_left: int = 30
    increment_share_permille: int = 800
    min_think_ms: int = 50
    max_think_ms: int = 10_000
    move_overhead_ms: int = 20
    instant_move_ms: int = 100  # book, memory and forced moves
    min_nodes: int = 100


DEFAULT_CLOCK_POLICY = ClockPolicy()


@dataclass(frozen=True)
class Balance:
    version: str = "balance-0.3-placeholder"
    clock: ClockPolicy = DEFAULT_CLOCK_POLICY

    # Growth
    stages: tuple[Stage, ...] = (
        Stage("hatchling", 1, 60),
        Stage("duckling", 5, 75),
        Stage("duck", 15, 90),
        Stage("champion", 30, 100),
    )
    max_level: int = 50
    xp_per_level_step: int = 50  # cumulative xp for level L is step * (L-1) * L
    base_stat_budget: int = 240
    stat_budget_per_level: int = 6
    default_stat: int = 40

    # The egg seed tilts a new duck's starting stats off the even spread (design 03 §1):
    # this many transfers of this many points from one stat to another.
    egg_stat_shifts: int = 3
    egg_shift_size: int = 5

    # Calculation -> node multiplier: every 10 "tenths" doubles the nodes.
    calculation_tenths_span: int = 30  # stat 0 is 1/8x, stat 100 is 8x

    # Memory -> chance to recall a taught move, per mille.
    recall_base_permille: int = 500
    recall_per_point_permille: int = 5

    # Creativity -> softmax half-life in centipawns (0 means always the top move).
    temperature_cp_per_point: int = 1

    # Speed -> share of the per-move time budget actually used, per mille.
    speed_factor_slow_permille: int = 1300
    speed_factor_per_point_permille: int = 6

    # Blunder tolerance comes from level, not from a stat (John, 2026-11-21).
    tolerance_base_cp: int = 300
    tolerance_per_level_cp: int = 8
    tolerance_min_cp: int = 20

    # Starting rating shown before any games (calibration stub, ADR-0006).
    provisional_rating: int = 1500

    xp_rewards: dict[str, int] = field(
        default_factory=lambda: {"game_played": 10, "game_won": 15, "lesson_completed": 20}
    )

    def stage_for(self, level: int) -> Stage:
        current = self.stages[0]
        for stage in self.stages:
            if level >= stage.min_level:
                current = stage
        return current

    def stat_budget(self, level: int) -> int:
        return self.base_stat_budget + self.stat_budget_per_level * (level - 1)

    def xp_needed(self, level: int) -> int:
        """Cumulative XP required to reach `level`."""
        return self.xp_per_level_step * (level - 1) * level

    def xp_for_next_level(self, level: int) -> int | None:
        """Cumulative XP at which the next level starts; None at the maximum level."""
        return None if level >= self.max_level else self.xp_needed(level + 1)

    def level_for_xp(self, xp: int) -> int:
        level = 1
        while level < self.max_level and xp >= self.xp_needed(level + 1):
            level += 1
        return level


DEFAULT_BALANCE = Balance()


@dataclass(frozen=True)
class MindParams:
    """How a duck plays, derived from stats and growth. Integers only."""

    node_multiplier_milli: int
    book_recall_permille: int
    blunder_tolerance_cp: int
    temperature_cp: int
    aggression_weight: int
    solidity_weight: int
    speed_factor_permille: int


def pow2_milli(tenths: int) -> int:
    """1000 * 2 ** (tenths / 10), computed with integers."""
    whole, fraction = divmod(tenths, 10)
    value = _POW2_TENTHS[fraction]
    return value << whole if whole >= 0 else value >> -whole


def derive_mind(
    stats: dict[str, int], level: int, balance: Balance = DEFAULT_BALANCE
) -> MindParams:
    calculation = stats["calculation"]
    tenths = (calculation - 50) * balance.calculation_tenths_span // 50
    return MindParams(
        node_multiplier_milli=max(1, pow2_milli(tenths)),
        book_recall_permille=min(
            1000, balance.recall_base_permille + balance.recall_per_point_permille * stats["memory"]
        ),
        blunder_tolerance_cp=max(
            balance.tolerance_min_cp,
            balance.tolerance_base_cp - balance.tolerance_per_level_cp * (level - 1),
        ),
        temperature_cp=balance.temperature_cp_per_point * stats["creativity"],
        aggression_weight=stats["aggression"],
        solidity_weight=stats["solidity"],
        speed_factor_permille=balance.speed_factor_slow_permille
        - balance.speed_factor_per_point_permille * stats["speed"],
    )
