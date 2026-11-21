"""Tournament scheduling (spec 7.2).

STUB FOR M3. The scheduler interface is settled; round robin is implemented because it
is the reference case for the interface. Swiss and knockout need standings as input and
are built in their session, as are tournament storage, events and the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from duckgambit.domain.errors import DomainError
from duckgambit.domain.seeds import draw_below, rng_for

FORMATS = ("round-robin", "swiss", "knockout")


@dataclass(frozen=True)
class Pairing:
    white: str
    black: str


@dataclass(frozen=True)
class Standing:
    participant: str
    points: float
    played: int


class Scheduler(Protocol):
    """Decides who plays whom. Pure and seeded, like everything that affects a result."""

    def total_rounds(self, participants: tuple[str, ...]) -> int: ...

    def pair_round(
        self,
        round_number: int,
        participants: tuple[str, ...],
        standings: tuple[Standing, ...],
        seed: int,
    ) -> tuple[Pairing, ...]:
        """Pairings for a round (numbered from 1). A participant left out has a bye."""
        ...


class RoundRobin:
    """Everyone meets everyone once per cycle; colours alternate between cycles."""

    def __init__(self, cycles: int = 1) -> None:
        if cycles < 1:
            raise DomainError("tournament.cycles", "A round robin needs at least one cycle")
        self._cycles = cycles

    def total_rounds(self, participants: tuple[str, ...]) -> int:
        slots = len(participants) + len(participants) % 2
        return (slots - 1) * self._cycles

    def pair_round(
        self,
        round_number: int,
        participants: tuple[str, ...],
        standings: tuple[Standing, ...],
        seed: int,
    ) -> tuple[Pairing, ...]:
        if len(set(participants)) != len(participants) or len(participants) < 2:
            raise DomainError("tournament.participants", "Need at least two different participants")
        if not 1 <= round_number <= self.total_rounds(participants):
            raise DomainError("tournament.round", "No such round")

        # A seeded shuffle fixes the starting order; then the circle method rotates it.
        order: list[str | None] = [*sorted(participants)]
        rng = rng_for(seed, "round-robin-order")
        for last in range(len(order) - 1, 0, -1):  # Fisher-Yates with our integer draw
            pick = draw_below(rng, last + 1)
            order[last], order[pick] = order[pick], order[last]
        if len(order) % 2:
            order.append(None)  # the bye
        per_cycle = len(order) - 1
        cycle, index = divmod(round_number - 1, per_cycle)
        fixed, rotating = order[0], order[1:]
        shift = index % per_cycle
        rotated = rotating[-shift:] + rotating[:-shift] if shift else rotating
        table = [fixed, *rotated]

        pairings = []
        half = len(table) // 2
        for board in range(half):
            first, second = table[board], table[-1 - board]
            if first is None or second is None:
                continue
            # Alternate colours by board and round, and flip everything on odd cycles.
            first_is_white = (board + index + cycle) % 2 == 0
            white, black = (first, second) if first_is_white else (second, first)
            pairings.append(Pairing(white, black))
        return tuple(pairings)


def scheduler_for(tournament_format: str, cycles: int = 1) -> Scheduler:
    if tournament_format == "round-robin":
        return RoundRobin(cycles)
    if tournament_format in FORMATS:
        raise DomainError(
            "tournament.not_built", f"{tournament_format} tournaments are not built yet (M3)"
        )
    raise DomainError("tournament.format", f"Unknown tournament format: {tournament_format!r}")
