"""Duck use cases: hatch, list, export, import, and the profile's active duck."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from duckgambit import __version__
from duckgambit.domain.balance import DEFAULT_BALANCE, Balance
from duckgambit.domain.challengers import (
    HOUSE_PROFILE_ID,
    ROSTER,
    Challenger,
    challenger_duck,
    challenger_for,
)
from duckgambit.domain.duck import Avatar, Duck, hatch
from duckgambit.domain.duckfile import export_duck, import_duck
from duckgambit.domain.events import DuckHatched
from duckgambit.domain.rating import DEFAULT_DEVIATION, Rating
from duckgambit.services.errors import not_found
from duckgambit.services.events import EventLog, iso
from duckgambit.services.ports import Clock, IdGenerator, Store
from duckgambit.services.records import RatingRecord


def duck_stream(duck_id: str) -> str:
    return f"duck:{duck_id}"


def ensure_challengers(store: Store, now: str, balance: Balance = DEFAULT_BALANCE) -> None:
    """Create the house ducks, or bring them in line with the roster. Runs at startup.

    Only the roster's own fields are rewritten; a challenger's ratings and games stay.
    """
    store.profiles.ensure(HOUSE_PROFILE_ID, "The house", now)
    for challenger in ROSTER:
        stored = store.ducks.get(challenger.duck_id)
        wanted = challenger_duck(challenger, stored.created_at if stored else now, balance)
        if stored is None:
            store.ducks.add(wanted)
        elif stored != wanted:
            store.ducks.update(wanted)


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    active_duck_id: str | None


@dataclass(frozen=True)
class HeadlineRating:
    """The one rating shown next to a duck. `context_id` is None for the calibration stub."""

    value: float
    deviation: float
    games: int
    provisional: bool
    context_id: str | None


def headline_rating(records: list[RatingRecord], balance: Balance) -> HeadlineRating:
    """Most recently updated game rating, or a provisional placeholder.

    CALIBRATION STUB (ADR-0006): until the harness exists (M3) a duck that has not played
    starts from one fixed number for every duck. It is always flagged provisional.
    """
    games = [record for record in records if record.kind == "game"]
    if not games:
        return HeadlineRating(float(balance.provisional_rating), DEFAULT_DEVIATION, 0, True, None)
    latest = max(games, key=lambda record: record.updated_at)
    rating: Rating = latest.rating
    return HeadlineRating(
        rating.value, rating.deviation, rating.games, rating.provisional, latest.context_id
    )


class DuckService:
    def __init__(
        self,
        store: Store,
        events: EventLog,
        clock: Clock,
        ids: IdGenerator,
        profile_id: str,
        balance: Balance = DEFAULT_BALANCE,
    ) -> None:
        self._store = store
        self._events = events
        self._clock = clock
        self._ids = ids
        self._profile_id = profile_id
        self.balance = balance

    async def hatch(
        self,
        name: str,
        avatar: Avatar | None = None,
        stats: dict[str, int] | None = None,
        egg_seed: int | None = None,
    ) -> Duck:
        duck, events = hatch(
            duck_id=self._ids.new("duck"),
            profile_id=self._profile_id,
            name=name,
            now=iso(self._clock),
            avatar=avatar,
            stats=stats,
            egg_seed=egg_seed,
            balance=self.balance,
        )

        def write() -> None:
            with self._store.atomic():
                self._store.ducks.add(duck)
                self._events.append(duck_stream(duck.id), events)

        await asyncio.to_thread(write)
        self._events.notify()
        return duck

    async def profile(self) -> Profile:
        """The local player, with the duck the hub should show.

        Falls back to the oldest duck when none was chosen yet (or the choice is gone),
        and to None when there are no ducks.
        """

        def read() -> Profile:
            active = self._store.profiles.active_duck(self._profile_id)
            if active is None:
                ducks = self._store.ducks.list_for(self._profile_id)
                active = ducks[0].id if ducks else None
            name = self._store.profiles.name(self._profile_id) or ""
            return Profile(self._profile_id, name, active)

        return await asyncio.to_thread(read)

    async def set_active(self, duck_id: str) -> Profile:
        duck = await self.get(duck_id)
        if duck.profile_id != self._profile_id:
            raise not_found("duck")
        await asyncio.to_thread(self._store.profiles.set_active_duck, self._profile_id, duck_id)
        return await self.profile()

    async def challengers(self) -> list[tuple[Challenger, Duck]]:
        """The house ducks to challenge, easiest first."""
        ducks = await asyncio.to_thread(self._store.ducks.list_for, HOUSE_PROFILE_ID)
        found = [(challenger_for(duck.id), duck) for duck in ducks]
        paired = [(challenger, duck) for challenger, duck in found if challenger is not None]
        return sorted(paired, key=lambda pair: pair[0].difficulty)

    async def all(self) -> list[Duck]:
        return await asyncio.to_thread(self._store.ducks.list_for, self._profile_id)

    async def get(self, duck_id: str) -> Duck:
        duck = await asyncio.to_thread(self._store.ducks.get, duck_id)
        if duck is None:
            raise not_found("duck")
        return duck

    async def ratings(self, duck_id: str) -> list[RatingRecord]:
        return await asyncio.to_thread(self._store.ratings.list_for_duck, duck_id)

    async def headline(self, duck_id: str) -> HeadlineRating:
        return headline_rating(await self.ratings(duck_id), self.balance)

    async def export(self, duck_id: str) -> dict[str, Any]:
        duck = await self.get(duck_id)
        ratings = [
            {
                "contextId": record.context_id,
                "kind": record.kind,
                "value": round(record.rating.value, 1),
                "deviation": round(record.rating.deviation, 1),
                "games": record.rating.games,
            }
            for record in await self.ratings(duck_id)
        ]
        return export_duck(duck, ratings, iso(self._clock), __version__)

    async def import_file(self, data: Any) -> Duck:
        """Add a duck from a duck file. Ratings in the file are a claim and are not stored:
        a rating only means something in the local rating context (ADR-0004)."""
        duck = import_duck(
            data,
            duck_id=self._ids.new("duck"),
            profile_id=self._profile_id,
            now=iso(self._clock),
            balance=self.balance,
        )
        hatched = DuckHatched(
            duck_id=duck.id,
            name=duck.name,
            species=duck.avatar.species,
            stage=duck.growth.stage,
            level=duck.growth.level,
            stats=dict(duck.stats),
            egg_seed=duck.egg_seed,
        )

        def write() -> None:
            with self._store.atomic():
                self._store.ducks.add(duck)
                self._events.append(duck_stream(duck.id), [hatched])

        await asyncio.to_thread(write)
        self._events.notify()
        return duck
