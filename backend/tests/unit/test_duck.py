import pytest

from duckgambit.domain.duck import Avatar, default_stats, hatch
from duckgambit.domain.errors import DomainError

NOW = "2026-11-21T12:00:00Z"


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
