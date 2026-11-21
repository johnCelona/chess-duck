"""Contracts for features built in later milestones: lessons, review, tournaments."""

import pytest

from duckgambit.domain.balance import DEFAULT_BALANCE
from duckgambit.domain.duck import hatch
from duckgambit.domain.engine_types import Candidate
from duckgambit.domain.errors import DomainError
from duckgambit.domain.lessons import Lesson, TaughtMove, apply_lesson
from duckgambit.domain.review import (
    JudgedMove,
    annotate,
    classify,
    critical_moments,
    expected_score_permille,
)
from duckgambit.domain.tournament import RoundRobin, scheduler_for

NOW = "2026-11-21T12:00:00Z"


def a_duck():
    duck, _ = hatch(duck_id="duck_1", profile_id="prof_1", name="Sir Quackalot", now=NOW)
    return duck


# ----- lessons -----------------------------------------------------------------------


def test_an_opening_lesson_adds_repertoire_moves_that_remember_their_lesson():
    lesson = Lesson("les_1", "opening", (TaughtMove("start w KQkq -", "e2e4"),))

    duck, events = apply_lesson(a_duck(), lesson)

    entry = duck.knowledge.repertoire[0]
    assert (entry.move, entry.color, entry.lesson_id, entry.source) == (
        "e2e4",
        "white",
        "les_1",
        "lesson",
    )
    assert [e.type for e in events] == ["LessonCompleted", "KnowledgeAdded"]
    assert duck.growth.xp == DEFAULT_BALANCE.xp_rewards["lesson_completed"]


def test_teaching_the_same_opening_move_twice_adds_it_once():
    lesson = Lesson("les_1", "opening", (TaughtMove("start w KQkq -", "e2e4"),))
    once, _ = apply_lesson(a_duck(), lesson)

    twice, events = apply_lesson(once, Lesson("les_2", "opening", lesson.moves))

    assert len(twice.knowledge.repertoire) == 1
    assert [e.type for e in events] == ["LessonCompleted"]


def test_a_fix_replaces_the_earlier_fix_for_the_same_position():
    first, _ = apply_lesson(a_duck(), Lesson("les_1", "fix", (TaughtMove("pos w - -", "d1h5"),)))

    second, _ = apply_lesson(first, Lesson("les_2", "fix", (TaughtMove("pos w - -", "g1f3"),)))

    assert second.knowledge.taught_move("pos w - -") == "g1f3"
    assert len(second.knowledge.puzzle_memory) == 1


def test_enough_xp_levels_the_duck_up_and_grows_its_stat_budget():
    lesson = Lesson("les_1", "fix", (TaughtMove("pos w - -", "d1h5"),), xp=10_000)

    duck, events = apply_lesson(a_duck(), lesson)

    leveled = next(e for e in events if e.type == "DuckLeveledUp")
    assert duck.growth.level > 1
    assert leveled.level == duck.growth.level
    assert leveled.stat_budget == DEFAULT_BALANCE.stat_budget(duck.growth.level)
    assert leveled.stage_advanced
    assert duck.stats == a_duck().stats  # points are unlocked, never spent for the player


def test_lessons_never_remove_knowledge_or_xp():
    taught, _ = apply_lesson(a_duck(), Lesson("les_1", "opening", (TaughtMove("p w - -", "e2e4"),)))

    after, _ = apply_lesson(
        taught, Lesson("les_2", "fix", (TaughtMove("q w - -", "a2a3"),), xp=-50)
    )

    assert after.knowledge.repertoire == taught.knowledge.repertoire
    assert after.growth.xp == taught.growth.xp


@pytest.mark.parametrize(
    ("lesson", "code"),
    [
        (Lesson("l", "telepathy", (TaughtMove("p", "e2e4"),)), "lesson.unknown_kind"),
        (Lesson("l", "opening", ()), "lesson.empty"),
        (Lesson("l", "opening", (TaughtMove("p", "castle"),)), "lesson.invalid_move"),
    ],
)
def test_malformed_lessons_are_rejected(lesson, code):
    with pytest.raises(DomainError) as error:
        apply_lesson(a_duck(), lesson)

    assert error.value.code == code


# ----- review ------------------------------------------------------------------------


def line(move, cp=None, mate=None, wdl=None) -> Candidate:
    return Candidate(move, cp, mate, wdl, 20, (move,))


def test_expected_score_uses_win_and_half_the_draws():
    assert expected_score_permille(line("e2e4", 30, wdl=(100, 800, 100))) == 500
    assert expected_score_permille(line("e2e4", 900, wdl=(990, 10, 0))) == 995
    assert expected_score_permille(line("e2e4", mate=3)) == 1000
    assert expected_score_permille(line("e2e4", mate=-2)) == 0


def test_winning_by_less_is_not_a_blunder_but_throwing_the_win_is():
    still_winning = JudgedMove(
        20, played=line("a2a3", 900, wdl=(985, 15, 0)), best=line("d1h5", 1400, wdl=(998, 2, 0))
    )
    thrown = JudgedMove(
        30, played=line("h2h3", 0, wdl=(100, 800, 100)), best=line("d1h5", 600, wdl=(950, 50, 0))
    )

    first, second = annotate([still_winning, thrown])

    assert (first.classification, first.loss_permille) == ("ok", 7)
    assert (second.classification, second.loss_permille) == ("blunder", 475)


def test_missing_a_forced_mate_is_flagged():
    judged = JudgedMove(12, played=line("a2a3", 500, wdl=(900, 100, 0)), best=line("d1h5", mate=2))

    assert annotate([judged])[0].missed_mate


def test_classification_thresholds():
    assert [classify(loss) for loss in (0, 49, 50, 100, 200, 900)] == [
        "ok",
        "ok",
        "inaccuracy",
        "mistake",
        "blunder",
        "blunder",
    ]


def test_critical_moments_are_the_three_costliest_in_game_order():
    def judged(ply, loss):
        return JudgedMove(
            ply,
            played=line("a2a3", wdl=(500 - loss, 0, 500 + loss)),
            best=line("e2e4", wdl=(500, 0, 500)),
        )

    annotations = annotate(
        [judged(5, 60), judged(11, 300), judged(19, 10), judged(23, 120), judged(40, 250)]
    )

    assert [a.ply for a in critical_moments(annotations)] == [11, 23, 40]


# ----- tournaments -------------------------------------------------------------------


@pytest.mark.parametrize("count", [2, 3, 4, 5, 8])
def test_round_robin_pairs_everyone_exactly_once(count):
    ducks = tuple(f"duck_{i}" for i in range(count))
    scheduler = RoundRobin()
    met = []

    for round_number in range(1, scheduler.total_rounds(ducks) + 1):
        pairings = scheduler.pair_round(round_number, ducks, (), seed=5)
        playing = [duck for pairing in pairings for duck in (pairing.white, pairing.black)]
        assert len(playing) == len(set(playing))  # nobody plays twice in a round
        met += [frozenset((p.white, p.black)) for p in pairings]

    assert len(met) == len(set(met)) == count * (count - 1) // 2


def test_round_robin_is_seeded_and_swaps_colours_in_the_second_cycle():
    ducks = ("a", "b", "c", "d")
    double = RoundRobin(cycles=2)

    first = double.pair_round(1, ducks, (), seed=9)
    again = double.pair_round(1, ducks, (), seed=9)
    rematch = double.pair_round(4, ducks, (), seed=9)

    assert first == again
    assert double.total_rounds(ducks) == 6
    assert {(p.black, p.white) for p in rematch} == {(p.white, p.black) for p in first}


def test_unbuilt_formats_say_so_clearly():
    assert isinstance(scheduler_for("round-robin"), RoundRobin)
    with pytest.raises(DomainError) as error:
        scheduler_for("swiss")
    assert error.value.code == "tournament.not_built"
    with pytest.raises(DomainError) as error:
        scheduler_for("battle-royale")
    assert error.value.code == "tournament.format"
