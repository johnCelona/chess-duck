"""The duck: identity, growth, stats, care and knowledge (spec section 4)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from duckgambit.domain.balance import DEFAULT_BALANCE, STAT_NAMES, Balance, MindParams, derive_mind
from duckgambit.domain.errors import DomainError
from duckgambit.domain.events import DuckHatched, Event
from duckgambit.domain.knowledge import Knowledge

DUCK_SCHEMA_VERSION = 1
NAME_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]{1,40}$")
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


@dataclass(frozen=True)
class Avatar:
    species: str = "mallard"
    skin: str = "default"
    accessories: tuple[str, ...] = ()


@dataclass(frozen=True)
class Growth:
    stage: str
    level: int
    xp: int


@dataclass(frozen=True)
class Care:
    """Care limits how much a duck can train. It never removes knowledge (spec 4.3)."""

    hunger: float = 0.0
    energy: float = 1.0
    mood: float = 1.0
    last_fed_at: str | None = None


@dataclass(frozen=True)
class Duck:
    id: str
    profile_id: str
    name: str
    avatar: Avatar
    growth: Growth
    stats: dict[str, int]
    care: Care
    knowledge: Knowledge
    created_at: str
    origin: str | None = None
    schema_version: int = DUCK_SCHEMA_VERSION

    def mind(self, balance: Balance = DEFAULT_BALANCE) -> MindParams:
        return derive_mind(self.stats, self.growth.level, balance)

    def with_knowledge(self, knowledge: Knowledge) -> Duck:
        return replace(self, knowledge=knowledge)


def default_stats(balance: Balance = DEFAULT_BALANCE) -> dict[str, int]:
    return dict.fromkeys(STAT_NAMES, balance.default_stat)


def validate_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not NAME_PATTERN.match(cleaned):
        raise DomainError("duck.invalid_name", "A duck needs a name of 1 to 40 characters")
    return cleaned


def validate_avatar(avatar: Avatar) -> Avatar:
    for value in (avatar.species, avatar.skin, *avatar.accessories):
        if not SLUG_PATTERN.match(value):
            raise DomainError("duck.invalid_avatar", f"Not a valid asset id: {value!r}")
    if len(avatar.accessories) > 8:
        raise DomainError("duck.invalid_avatar", "Too many accessories")
    return avatar


def validate_stats(stats: dict[str, int], level: int, balance: Balance = DEFAULT_BALANCE) -> None:
    """Stats are a budget that grows with level; nobody can max everything (spec 4.2)."""
    if set(stats) != set(STAT_NAMES):
        raise DomainError("duck.invalid_stats", f"Stats must be exactly: {', '.join(STAT_NAMES)}")
    cap = balance.stage_for(level).stat_cap
    for name in STAT_NAMES:
        value = stats[name]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= cap:
            raise DomainError(
                "duck.stat_out_of_range", f"{name} must be a whole number from 0 to {cap}"
            )
    budget = balance.stat_budget(level)
    if sum(stats.values()) > budget:
        raise DomainError(
            "duck.stat_budget_exceeded",
            f"Stats add up to {sum(stats.values())}, over the budget of {budget} at level {level}",
        )


def hatch(
    *,
    duck_id: str,
    profile_id: str,
    name: str,
    now: str,
    avatar: Avatar | None = None,
    stats: dict[str, int] | None = None,
    balance: Balance = DEFAULT_BALANCE,
) -> tuple[Duck, list[Event]]:
    """Create a level-1 duck. Returns the duck and the events that describe what happened."""
    level = 1
    chosen_stats = dict(stats) if stats is not None else default_stats(balance)
    validate_stats(chosen_stats, level, balance)
    duck = Duck(
        id=duck_id,
        profile_id=profile_id,
        name=validate_name(name),
        avatar=validate_avatar(avatar or Avatar()),
        growth=Growth(stage=balance.stage_for(level).name, level=level, xp=0),
        stats=chosen_stats,
        care=Care(),
        knowledge=Knowledge(),
        created_at=now,
    )
    event = DuckHatched(
        duck_id=duck.id,
        name=duck.name,
        species=duck.avatar.species,
        stage=duck.growth.stage,
        level=duck.growth.level,
        stats=dict(duck.stats),
    )
    return duck, [event]
