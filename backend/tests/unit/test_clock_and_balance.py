from duckgambit.domain.balance import DEFAULT_BALANCE, derive_mind, pow2_milli
from duckgambit.domain.clock import charge, nodes_for, scale_nodes, think_budget_ms
from duckgambit.domain.duck import default_stats


def mind_with(**stats):
    return derive_mind({**default_stats(), **stats}, level=1)


def test_think_budget_is_a_share_of_the_remaining_time():
    budget = think_budget_ms(60_000, 0, fullmove_number=1, mind=mind_with(speed=50))

    assert budget == 60_000 // 40


def test_a_fast_duck_thinks_less_than_a_slow_duck():
    fast = think_budget_ms(60_000, 0, 1, mind_with(speed=60))
    slow = think_budget_ms(60_000, 0, 1, mind_with(speed=0))

    assert fast < slow


def test_think_budget_never_drops_below_the_minimum():
    assert think_budget_ms(30, 0, 60, mind_with(speed=60)) == 50


def test_increment_adds_to_the_budget():
    without = think_budget_ms(60_000, 0, 1, mind_with(speed=50))
    with_increment = think_budget_ms(60_000, 1_000, 1, mind_with(speed=50))

    assert with_increment == without + 800


def test_nodes_scale_with_time_speed_constant_and_calculation():
    assert nodes_for(1_000, 200_000, 1000, max_nodes=5_000_000) == 200_000
    assert nodes_for(1_000, 200_000, 2000, max_nodes=5_000_000) == 400_000
    assert nodes_for(500, 200_000, 1000, max_nodes=5_000_000) == 100_000


def test_nodes_are_clamped_to_the_server_cap_and_a_floor():
    assert nodes_for(10_000, 5_000_000, 8000, max_nodes=5_000_000) == 5_000_000
    assert nodes_for(1, 1_000, 125, max_nodes=5_000_000) == 100
    assert scale_nodes(50_000, 2000, max_nodes=60_000) == 60_000


def test_charging_deducts_think_time_and_overhead_then_adds_increment():
    result = charge(60_000, 1_500, increment_ms=1_000)

    assert result.remaining_ms == 60_000 - 1_500 - 20 + 1_000
    assert not result.flagged


def test_running_out_of_time_flags():
    result = charge(60, 50, increment_ms=5_000)

    assert result.flagged
    assert result.remaining_ms == 0


def test_calculation_doubles_nodes_in_even_steps():
    assert pow2_milli(0) == 1000
    assert pow2_milli(10) == 2000
    assert pow2_milli(-10) == 500
    assert pow2_milli(5) == 1414
    assert mind_with(calculation=50).node_multiplier_milli == 1000
    assert mind_with(calculation=0).node_multiplier_milli == 125
    assert (
        mind_with(calculation=60).node_multiplier_milli
        > mind_with(calculation=40).node_multiplier_milli
    )


def test_blunder_tolerance_narrows_with_level_not_with_stats():
    stats = default_stats()

    assert derive_mind(stats, 1).blunder_tolerance_cp > derive_mind(stats, 20).blunder_tolerance_cp
    assert derive_mind(stats, 200).blunder_tolerance_cp == DEFAULT_BALANCE.tolerance_min_cp


def test_stat_budget_and_stage_grow_with_level():
    assert DEFAULT_BALANCE.stat_budget(1) == 240
    assert DEFAULT_BALANCE.stat_budget(11) == 300
    assert DEFAULT_BALANCE.stage_for(1).name == "hatchling"
    assert DEFAULT_BALANCE.stage_for(15).name == "duck"
    assert DEFAULT_BALANCE.level_for_xp(0) == 1
    assert DEFAULT_BALANCE.level_for_xp(DEFAULT_BALANCE.xp_needed(3)) == 3
