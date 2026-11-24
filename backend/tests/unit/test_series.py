from fractions import Fraction

import pytest

from duckgambit.domain.challengers import ROSTER, challenger_duck
from duckgambit.domain.errors import DomainError
from duckgambit.domain.series import (
    SeriesFormat,
    SeriesGame,
    armageddon_first_is_white,
    series_status,
    validate_format,
)

WIN, DRAW, LOSS = Fraction(1), Fraction(1, 2), Fraction(0)


def games(*results, armageddon=None):
    played = [SeriesGame(result) for result in results]
    if armageddon is not None:
        points, first_is_black = armageddon
        played.append(SeriesGame(points, armageddon=True, first_is_black=first_is_black))
    return played


def test_a_series_stops_as_soon_as_one_side_cannot_be_caught():
    status = series_status(5, games(WIN, WIN, WIN))

    assert (status.state, status.winner, status.decided_by) == ("decided", 0, "games")
    assert status.games_played == 3


def test_draws_count_half_a_point_each():
    # 3 - 1 with one game left: the second duck can reach 2 at most.
    status = series_status(5, games(WIN, DRAW, DRAW, WIN))

    assert (status.state, status.winner) == ("decided", 0)
    assert (status.first_points, status.second_points) == (Fraction(3), Fraction(1))
    assert series_status(5, games(WIN, DRAW, WIN, LOSS)).state == "playing"  # 2.5 - 1.5


def test_an_open_series_keeps_playing():
    assert series_status(3, games(WIN)).state == "playing"
    assert series_status(3, []).state == "playing"


def test_a_tie_after_every_game_goes_to_armageddon():
    assert series_status(3, games(WIN, LOSS, DRAW)).state == "armageddon"


@pytest.mark.parametrize(
    ("armageddon", "winner"),
    [
        ((WIN, False), 0),  # the first duck won it outright
        ((LOSS, True), 1),
        ((DRAW, True), 0),  # a draw is a win for Black, and the first duck was Black
        ((DRAW, False), 1),
    ],
)
def test_armageddon_decides_and_a_draw_wins_for_black(armageddon, winner):
    status = series_status(3, games(WIN, LOSS, DRAW, armageddon=armageddon))

    assert (status.state, status.winner, status.decided_by) == ("decided", winner, "armageddon")
    assert status.games_played == 4


def test_armageddon_colours_come_from_the_seed():
    assert armageddon_first_is_white(7) == armageddon_first_is_white(7)
    assert {armageddon_first_is_white(seed) for seed in range(20)} == {True, False}


@pytest.mark.parametrize("best_of", [1, 2, 4, 9, 16])
def test_only_the_offered_series_lengths_are_allowed(best_of):
    with pytest.raises(DomainError):
        validate_format(SeriesFormat(best_of))


def test_every_challenger_is_a_valid_duck_and_they_get_stronger():
    ducks = [challenger_duck(challenger, "2026-11-21T12:00:00Z") for challenger in ROSTER]

    assert [d.growth.level for d in ducks] == sorted(d.growth.level for d in ducks)
    assert [c.difficulty for c in ROSTER] == sorted(c.difficulty for c in ROSTER)
    strongest = ducks[-1].mind()
    assert strongest.temperature_cp == 0  # always the engine's top move
    assert strongest.blunder_tolerance_cp == min(d.mind().blunder_tolerance_cp for d in ducks)
