import copy

import pytest

from duckgambit.domain.duck import default_stats, hatch
from duckgambit.domain.duckfile import export_duck, import_duck
from duckgambit.domain.errors import DomainError
from duckgambit.domain.knowledge import Knowledge, PuzzleMemoryEntry, RepertoireEntry

NOW = "2026-11-21T12:00:00Z"


@pytest.fixture
def exported():
    duck, _ = hatch(duck_id="duck_orig", profile_id="prof_a", name="Sir Quackalot", now=NOW)
    duck = duck.with_knowledge(
        Knowledge(
            repertoire=(
                RepertoireEntry("white", "start w KQkq -", "e2e4", 3),
                RepertoireEntry("black", "after-e4 b KQkq -", "c7c5", 1),
            ),
            principles=("castle_early",),
            motifs={"fork": 60},
            puzzle_memory=(PuzzleMemoryEntry("tactic w - -", "d1h5"),),
        )
    )
    ratings = [{"contextId": "ctx_1", "kind": "game", "value": 2100.0, "deviation": 60.0}]
    return duck, export_duck(duck, ratings, NOW, "0.1.0")


def load(data):
    return import_duck(data, duck_id="duck_new", profile_id="prof_b", now=NOW)


def test_export_has_the_format_marker_and_version(exported):
    _, data = exported

    assert data["format"] == "duck-gambit.duck"
    assert data["schemaVersion"] == 1
    assert data["duck"]["knowledge"]["repertoire"]["white"][0]["move"] == "e2e4"


def test_import_keeps_knowledge_and_stats_but_gives_a_new_identity(exported):
    duck, data = exported

    imported = load(data)

    assert imported.id == "duck_new"
    assert imported.profile_id == "prof_b"
    assert imported.origin == "duck_orig"
    assert imported.name == duck.name
    assert imported.stats == duck.stats
    assert {(e.color, e.move) for e in imported.knowledge.repertoire} == {
        ("white", "e2e4"),
        ("black", "c7c5"),
    }
    assert imported.knowledge.taught_move("tactic w - -") == "d1h5"
    assert imported.knowledge.motifs == {"fork": 60}


def test_a_hand_edited_file_cannot_exceed_the_stat_budget(exported):
    _, data = exported
    cheat = copy.deepcopy(data)
    cheat["duck"]["stats"] = dict.fromkeys(default_stats(), 60)

    with pytest.raises(DomainError) as error:
        load(cheat)

    assert error.value.code == "duck.stat_budget_exceeded"


def test_level_comes_from_xp_not_from_the_claimed_level(exported):
    _, data = exported
    cheat = copy.deepcopy(data)
    cheat["duck"]["growth"] = {"stage": "champion", "level": 50, "xp": 0}

    imported = load(cheat)

    assert (imported.growth.level, imported.growth.stage) == (1, "hatchling")


@pytest.mark.parametrize(
    "damage",
    [
        lambda d: d.update(format="something-else"),
        lambda d: d.update(schemaVersion="1"),
        lambda d: d.pop("duck"),
        lambda d: d["duck"].update(name=5),
        lambda d: d["duck"]["knowledge"]["repertoire"]["white"].append({"fen": "x", "move": "zz"}),
        lambda d: d["duck"]["knowledge"].update(puzzleMemory="nope"),
        lambda d: d["duck"]["growth"].update(xp=-1),
    ],
)
def test_malformed_files_are_rejected(exported, damage):
    _, data = exported
    broken = copy.deepcopy(data)
    damage(broken)

    with pytest.raises(DomainError):
        load(broken)


def test_a_file_from_a_newer_version_is_refused_clearly(exported):
    _, data = exported
    future = {**data, "schemaVersion": 2}

    with pytest.raises(DomainError) as error:
        load(future)

    assert error.value.code == "duckfile.too_new"
