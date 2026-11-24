"""The challenger roster: house ducks your duck can call out in Super Bullet Arena.

Challengers are ordinary ducks. They follow the same stat budget, caps and decision layer
as every player's duck, so the strongest is strong only because of its stats and level:
level 50 (the narrowest blunder tolerance), maximum Calculation, and Creativity 0, which
means it always plays the engine's best move.

Names, blurbs and looks are placeholders for John (design 03 §7). Do not name a
challenger after a real person. Changing a challenger's stats changes how it plays;
bump ROSTER_VERSION so the change is visible in logs and reviews.
"""

from __future__ import annotations

from dataclasses import dataclass

from duckgambit.domain.balance import DEFAULT_BALANCE, Balance
from duckgambit.domain.duck import Avatar, Care, Duck, Growth, validate_avatar, validate_stats
from duckgambit.domain.knowledge import Knowledge

ROSTER_VERSION = 1
HOUSE_PROFILE_ID = "prof_house"


@dataclass(frozen=True)
class Challenger:
    duck_id: str
    name: str
    blurb: str
    difficulty: int  # 1 (easiest) upward, for ordering and display
    level: int
    skin: str
    stats: dict[str, int]


ROSTER: tuple[Challenger, ...] = (
    Challenger(
        duck_id="chal_puddle_rookie",
        name="Puddle Rookie",
        blurb="Just hatched. Hangs pieces, has fun doing it.",
        difficulty=1,
        level=1,
        skin="classic",
        stats={
            "calculation": 40,
            "memory": 40,
            "aggression": 40,
            "solidity": 40,
            "creativity": 40,
            "speed": 40,
        },
    ),
    Challenger(
        duck_id="chal_mallard_marauder",
        name="Mallard Marauder",
        blurb="Attacks first, asks questions never.",
        difficulty=2,
        level=10,
        skin="chalkboard",
        stats={
            "calculation": 50,
            "memory": 40,
            "aggression": 75,
            "solidity": 30,
            "creativity": 60,
            "speed": 39,
        },
    ),
    Challenger(
        duck_id="chal_the_wall",
        name="The Wall",
        blurb="Patient, solid, and very hard to break.",
        difficulty=3,
        level=25,
        skin="blueprint",
        stats={
            "calculation": 75,
            "memory": 60,
            "aggression": 30,
            "solidity": 90,
            "creativity": 20,
            "speed": 60,
        },
    ),
    Challenger(
        duck_id="chal_grandmallard",
        name="The Grandmallard",
        blurb="Plays the engine's best move, every move. Good luck.",
        difficulty=4,
        level=50,
        skin="terminal",
        stats={
            "calculation": 100,
            "memory": 100,
            "aggression": 100,
            "solidity": 100,
            "creativity": 0,
            "speed": 50,
        },
    ),
)


def challenger_duck(challenger: Challenger, now: str, balance: Balance = DEFAULT_BALANCE) -> Duck:
    """The challenger as a duck owned by the house profile. Validated like any duck."""
    validate_stats(challenger.stats, challenger.level, balance)
    return Duck(
        id=challenger.duck_id,
        profile_id=HOUSE_PROFILE_ID,
        name=challenger.name,
        avatar=validate_avatar(Avatar(skin=challenger.skin)),
        growth=Growth(
            stage=balance.stage_for(challenger.level).name,
            level=challenger.level,
            xp=balance.xp_needed(challenger.level),
        ),
        stats=dict(challenger.stats),
        care=Care(),
        knowledge=Knowledge(),
        created_at=now,
        origin="house",
    )


def challenger_for(duck_id: str) -> Challenger | None:
    return next((c for c in ROSTER if c.duck_id == duck_id), None)
