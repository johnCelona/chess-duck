import pytest

from duckgambit.domain.balance import DEFAULT_BALANCE
from duckgambit.domain.duck import (
    Avatar,
    default_stats,
    grant_xp,
    hatch,
    stats_from_egg,
    validate_stats,
)
from duckgambit.domain.errors import DomainError

NOW = "2026-11-21T12:00:00Z"
EXPECTED_EGG_42 = {
    "calculation": 30,
    "memory": 40,
    "aggression": 45,
    "solidity": 40,
    "creativity": 45,
    "speed": 40,
}


def hatch_duck(**overrides):
    values = {"duck_id": "duck_1", "profile_id": "prof_1", "name": "Sir Quackalot", "now": NOW}
    return hatch(**{**values, **overrides})


def test_hatching_gives_a_level_one_hatchling_with_the_default_spread():
    duck, events = hatch_duck()

    assert duck.growth.level == 1
    assert duck.growth.stage == "hatchling"
    assert duck.stats == default_stats()
    assert duck.knowledge.repertoire == ()
    assert [event.type for event in events] == ["DuckHatched"]
    assert events[0].data()["duck_id"] == "duck_1"


def test_name_is_trimmed_and_must_not_be_empty():
    duck, _ = hatch_duck(name="  Sir   Quackalot ")
    assert duck.name == "Sir Quackalot"

    with pytest.raises(DomainError) as error:
        hatch_duck(name="   ")
    assert error.value.code == "duck.invalid_name"


def test_stats_cannot_exceed_the_level_budget():
    greedy = {**default_stats(), "calculation": 60, "memory": 60}

    with pytest.raises(DomainError) as error:
        hatch_duck(stats=greedy)

    assert error.value.code == "duck.stat_budget_exceeded"


def test_a_stat_cannot_exceed_the_stage_cap():
    lopsided = {**default_stats(), "calculation": 61, "memory": 0}

    with pytest.raises(DomainError) as error:
        hatch_duck(stats=lopsided)

    assert error.value.code == "duck.stat_out_of_range"


def test_a_custom_spread_within_budget_is_accepted():
    spread = {**default_stats(), "aggression": 60, "solidity": 20}

    duck, _ = hatch_duck(stats=spread)

    assert duck.stats["aggression"] == 60
    assert duck.mind().aggression_weight == 60


def test_unknown_or_missing_stats_are_rejected():
    with pytest.raises(DomainError) as error:
        hatch_duck(stats={"calculation": 40})

    assert error.value.code == "duck.invalid_stats"


def test_avatar_ids_must_be_asset_slugs():
    with pytest.raises(DomainError) as error:
        hatch_duck(avatar=Avatar(species="../etc"))

    assert error.value.code == "duck.invalid_avatar"


def test_the_same_egg_always_hatches_the_same_stats():
    first, _ = hatch_duck(egg_seed=42)
    again, _ = hatch_duck(duck_id="duck_2", name="Twin", egg_seed=42)

    assert first.stats == again.stats == stats_from_egg(42)
    assert first.egg_seed == 42


def test_an_egg_tilts_the_even_spread_by_whole_transfers():
    # Pinned so a change to the tilt (or to seed derivation) is noticed; bump
    # Balance.version with it.
    assert stats_from_egg(42) == EXPECTED_EGG_42


def test_every_egg_hatches_valid_stats_and_eggs_differ():
    balance = DEFAULT_BALANCE
    spreads = set()
    for seed in range(1000):
        stats = stats_from_egg(seed)
        validate_stats(stats, 1, balance)
        assert sum(stats.values()) == sum(default_stats().values())
        assert all(value % balance.egg_shift_size == 0 for value in stats.values())
        spreads.add(tuple(stats.values()))
    assert len(spreads) > 50


def test_the_hatch_event_names_the_egg():
    _, events = hatch_duck(egg_seed=7)

    assert events[0].data()["egg_seed"] == 7


def test_an_egg_and_chosen_stats_cannot_be_combined():
    with pytest.raises(DomainError) as error:
        hatch_duck(egg_seed=1, stats=default_stats())
    assert error.value.code == "duck.egg_and_stats"


@pytest.mark.parametrize("seed", [-1, 2**53, True, "7"])
def test_an_egg_seed_must_be_a_53_bit_whole_number(seed):
    with pytest.raises(DomainError) as error:
        hatch_duck(egg_seed=seed)
    assert error.value.code == "duck.invalid_egg_seed"


def test_xp_adds_up_and_levels_follow_from_the_total():
    duck, _ = hatch_duck()
    needed = DEFAULT_BALANCE.xp_needed(2)

    same_level, events = grant_xp(duck, needed - 1, "match")
    assert (same_level.growth.level, same_level.growth.xp) == (1, needed - 1)
    assert [e.type for e in events] == ["XpGained"]
    assert events[0].data()["xp_for_next_level"] == needed

    grown, events = grant_xp(duck, DEFAULT_BALANCE.xp_needed(3), "match")
    assert grown.growth.level == 3
    assert [e.type for e in events] == ["XpGained", "DuckLeveledUp"]
    assert events[1].data()["stat_budget"] == DEFAULT_BALANCE.stat_budget(3)


def test_reaching_a_new_stage_is_announced_and_xp_never_goes_down():
    duck, _ = hatch_duck()
    duckling = next(s for s in DEFAULT_BALANCE.stages if s.name == "duckling")

    grown, events = grant_xp(duck, DEFAULT_BALANCE.xp_needed(duckling.min_level), "match")
    assert grown.growth.stage == "duckling"
    assert events[-1].data()["stage_advanced"] is True
    assert grant_xp(duck, -50, "match")[0].growth.xp == 0


def test_the_top_level_has_no_next_level():
    duck, _ = hatch_duck()
    top, events = grant_xp(duck, 10**9, "match")

    assert top.growth.level == DEFAULT_BALANCE.max_level
    assert events[0].data()["xp_for_next_level"] is None
