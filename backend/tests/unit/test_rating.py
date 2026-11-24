import pytest

from duckgambit.domain.rating import Rating, expected_score, update


def test_matches_glickmans_worked_example():
    """Section "Example calculation" of http://www.glicko.net/glicko/glicko2.pdf."""
    player = Rating(1500, 200, 0.06)
    results = [
        (Rating(1400, 30, 0.06), 1.0),
        (Rating(1550, 100, 0.06), 0.0),
        (Rating(1700, 300, 0.06), 0.0),
    ]

    updated = update(player, results, tau=0.5)

    assert updated.value == pytest.approx(1464.06, abs=0.01)
    assert updated.deviation == pytest.approx(151.52, abs=0.01)
    assert updated.volatility == pytest.approx(0.05999, abs=0.00001)
    assert updated.games == 3


def test_a_period_without_games_only_widens_the_deviation():
    player = Rating(1600, 80, 0.06, games=10)

    updated = update(player, [])

    assert updated.value == 1600
    assert updated.deviation > 80
    assert updated.games == 10


def test_winning_raises_and_losing_lowers():
    player, opponent = Rating(), Rating()

    assert update(player, [(opponent, 1.0)]).value > 1500
    assert update(player, [(opponent, 0.0)]).value < 1500
    assert update(player, [(opponent, 0.5)]).value == pytest.approx(1500)


def test_new_ducks_are_provisional_until_games_narrow_the_deviation():
    player = Rating()
    assert player.provisional

    for _ in range(30):
        player = update(player, [(Rating(1500, 50, 0.06), 0.5)])

    assert not player.provisional


def test_expected_score_favours_the_higher_rating():
    assert expected_score(Rating(1700, 50), Rating(1500, 50)) > 0.7
    assert expected_score(Rating(1500, 50), Rating(1500, 50)) == pytest.approx(0.5)
