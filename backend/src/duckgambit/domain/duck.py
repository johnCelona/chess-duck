"""The duck: identity, growth, stats, care and knowledge (spec section 4)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from duckgambit.domain.balance import DEFAULT_BALANCE, STAT_NAMES, Balance, MindParams, derive_mind
from duckgambit.domain.errors import DomainError
from duckgambit.domain.events import DuckHatched, Event
from duckgambit.domain.knowledge import Knowledge
from duckgambit.domain.seeds import draw_below, rng_for

# 2: ducks remember the egg seed they hatched from (design 03 §1).
DUCK_SCHEMA_VERSION = 2
EGG_SEED_MAX = 2**53 - 1  # exact in JSON and JavaScript numbers
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
    egg_seed: int | None = None  # None for ducks hatched without an egg (Lab, imports, v1)
    schema_version: int = DUCK_SCHEMA_VERSION

    def mind(self, balance: Balance = DEFAULT_BALANCE) -> MindParams:
        return derive_mind(self.stats, self.growth.level, balance)

    def with_knowledge(self, knowledge: Knowledge) -> Duck:
        return replace(self, knowledge=knowledge)


def default_stats(balance: Balance = DEFAULT_BALANCE) -> dict[str, int]:
    return dict.fromkeys(STAT_NAMES, balance.default_stat)


def stats_from_egg(egg_seed: int, balance: Balance = DEFAULT_BALANCE) -> dict[str, int]:
    """The starting spread an egg hatches into: the even spread, tilted by the seed.

    A few fixed-size transfers move points from one stat to another, so the total stays
    at the level-1 budget and every duck starts a little different. Same egg, same stats.
    A transfer that would leave the range 0..cap is skipped, so the result is always valid.
    """
    validate_egg_seed(egg_seed)
    stats = default_stats(balance)
    cap = balance.stage_for(1).stat_cap
    size = balance.egg_shift_size
    rng = rng_for(egg_seed, "egg-stats")
    for _ in range(balance.egg_stat_shifts):
        giver = STAT_NAMES[draw_below(rng, len(STAT_NAMES))]
        others = [name for name in STAT_NAMES if name != giver]
        taker = others[draw_below(rng, len(others))]
        if stats[giver] - size >= 0 and stats[taker] + size <= cap:
            stats[giver] -= size
            stats[taker] += size
    return stats


def validate_egg_seed(egg_seed: int) -> int:
    if (
        isinstance(egg_seed, bool)
        or not isinstance(egg_seed, int)
        or not 0 <= egg_seed <= EGG_SEED_MAX
    ):
        raise DomainError(
            "duck.invalid_egg_seed", f"An egg seed is a whole number from 0 to {EGG_SEED_MAX}"
        )
    return egg_seed


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
    egg_seed: int | None = None,
    balance: Balance = DEFAULT_BALANCE,
) -> tuple[Duck, list[Event]]:
    """Create a level-1 duck. Returns the duck and the events that describe what happened.

    Starting stats come from `stats` if given, else from the egg seed, else the even spread.
    """
    level = 1
    if stats is not None and egg_seed is not None:
        raise DomainError(
            "duck.egg_and_stats",
            "A duck's starting stats come from its egg or are chosen, not both",
        )
    if stats is not None:
        chosen_stats = dict(stats)
    elif egg_seed is not None:
        chosen_stats = stats_from_egg(egg_seed, balance)
    else:
        chosen_stats = default_stats(balance)
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
        egg_seed=egg_seed,
    )
    event = DuckHatched(
        duck_id=duck.id,
        name=duck.name,
        species=duck.avatar.species,
        stage=duck.growth.stage,
        level=duck.growth.level,
        stats=dict(duck.stats),
        egg_seed=duck.egg_seed,
    )
    return duck, [event]
