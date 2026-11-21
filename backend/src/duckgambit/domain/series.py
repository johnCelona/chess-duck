"""Best-of series and their Armageddon tie-break (Super Bullet Arena, design 03).

A series is a match that stops as soon as one side cannot be caught. Draws count half a
point. If the points are level after every game, one Armageddon game decides it: a draw
in that game counts as a series win for Black. Its colours come from the match seed, so
a replay of the series plays the same Armageddon (rule 6).

Pure functions over game results; the match runner asks `series_status` after each game.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from duckgambit.domain.errors import DomainError
from duckgambit.domain.seeds import draw_below, rng_for

BEST_OF_CHOICES = (3, 5, 7, 15)


@dataclass(frozen=True)
class SeriesFormat:
    best_of: int
    type: str = "best-of"


def validate_format(series: SeriesFormat) -> SeriesFormat:
    if series.type != "best-of" or series.best_of not in BEST_OF_CHOICES:
        choices = ", ".join(str(n) for n in BEST_OF_CHOICES)
        raise DomainError("series.best_of", f"A series is best of {choices}")
    return series


@dataclass(frozen=True)
class SeriesGame:
    """One finished game, seen from the first duck of the match."""

    first_points: Fraction  # 1, 1/2 or 0
    armageddon: bool = False
    first_is_black: bool = False


@dataclass(frozen=True)
class SeriesStatus:
    state: str  # "playing" | "armageddon" | "decided"
    first_points: Fraction
    second_points: Fraction
    games_played: int
    winner: int | None = None  # 0 for the first duck, 1 for the second
    decided_by: str | None = None  # "games" | "armageddon"


def series_status(best_of: int, games: list[SeriesGame]) -> SeriesStatus:
    regular = [game for game in games if not game.armageddon]
    first = sum((game.first_points for game in regular), Fraction(0))
    second = len(regular) - first
    remaining = best_of - len(regular)
    played = len(games)

    if first > second + remaining:
        return SeriesStatus("decided", first, second, played, 0, "games")
    if second > first + remaining:
        return SeriesStatus("decided", first, second, played, 1, "games")
    if remaining > 0:
        return SeriesStatus("playing", first, second, played)

    deciders = [game for game in games if game.armageddon]
    if not deciders:
        return SeriesStatus("armageddon", first, second, played)
    decider = deciders[0]
    if decider.first_points == Fraction(1, 2):
        first_wins = decider.first_is_black  # a draw is a win for Black
    else:
        first_wins = decider.first_points == 1
    return SeriesStatus("decided", first, second, played, 0 if first_wins else 1, "armageddon")


def armageddon_first_is_white(seed: int) -> bool:
    """Which side the first duck takes in the Armageddon game: a coin toss from the seed."""
    return draw_below(rng_for(seed, "armageddon"), 2) == 0
