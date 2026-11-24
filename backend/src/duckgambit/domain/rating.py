"""Glicko-2 ratings (spec 4.4, ADR-0006).

Implemented from Glickman's description and checked against his worked example
(http://www.glicko.net/glicko/glicko2.pdf). Ratings are measured strength inside one
rating context; they are not levels and are never edited by hand.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

SCALE = 173.7178
DEFAULT_RATING = 1500.0
DEFAULT_DEVIATION = 350.0
DEFAULT_VOLATILITY = 0.06
DEFAULT_TAU = 0.5
PROVISIONAL_DEVIATION = 110.0
_CONVERGENCE = 1e-6


@dataclass(frozen=True)
class Rating:
    value: float = DEFAULT_RATING
    deviation: float = DEFAULT_DEVIATION
    volatility: float = DEFAULT_VOLATILITY
    games: int = 0

    @property
    def provisional(self) -> bool:
        """A rating is provisional until enough games have narrowed its deviation."""
        return self.deviation > PROVISIONAL_DEVIATION


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def expected_score(player: Rating, opponent: Rating) -> float:
    return _expected(
        (player.value - DEFAULT_RATING) / SCALE,
        (opponent.value - DEFAULT_RATING) / SCALE,
        opponent.deviation / SCALE,
    )


def update(
    player: Rating,
    results: Sequence[tuple[Rating, float]],
    tau: float = DEFAULT_TAU,
) -> Rating:
    """One rating period. `results` pairs each opponent with the player's score (1, 0.5, 0)."""
    mu = (player.value - DEFAULT_RATING) / SCALE
    phi = player.deviation / SCALE
    sigma = player.volatility

    if not results:
        phi_star = math.sqrt(phi * phi + sigma * sigma)
        return Rating(player.value, min(DEFAULT_DEVIATION, phi_star * SCALE), sigma, player.games)

    v_inverse = 0.0
    delta_sum = 0.0
    for opponent, score in results:
        mu_j = (opponent.value - DEFAULT_RATING) / SCALE
        phi_j = opponent.deviation / SCALE
        g_j = _g(phi_j)
        e_j = _expected(mu, mu_j, phi_j)
        v_inverse += g_j * g_j * e_j * (1.0 - e_j)
        delta_sum += g_j * (score - e_j)
    v = 1.0 / v_inverse
    delta = v * delta_sum

    # Volatility by the Illinois variant of regula falsi (step 5 of the paper).
    a = math.log(sigma * sigma)

    def f(x: float) -> float:
        ex = math.exp(x)
        top = ex * (delta * delta - phi * phi - v - ex)
        bottom = 2.0 * (phi * phi + v + ex) ** 2
        return top / bottom - (x - a) / (tau * tau)

    big_a = a
    if delta * delta > phi * phi + v:
        big_b = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        big_b = a - k * tau
    f_a, f_b = f(big_a), f(big_b)
    while abs(big_b - big_a) > _CONVERGENCE:
        big_c = big_a + (big_a - big_b) * f_a / (f_b - f_a)
        f_c = f(big_c)
        if f_c * f_b <= 0:
            big_a, f_a = big_b, f_b
        else:
            f_a /= 2.0
        big_b, f_b = big_c, f_c
    new_sigma = math.exp(big_a / 2.0)

    phi_star = math.sqrt(phi * phi + new_sigma * new_sigma)
    new_phi = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    new_mu = mu + new_phi * new_phi * delta_sum
    return Rating(
        value=SCALE * new_mu + DEFAULT_RATING,
        deviation=SCALE * new_phi,
        volatility=new_sigma,
        games=player.games + len(results),
    )
