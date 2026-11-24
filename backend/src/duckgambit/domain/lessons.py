"""Lessons: the one door through which a duck's knowledge changes (spec 5, ADR-0008).

STUB FOR M2/M5. The shape is settled and tested; no service or API calls it yet.
Every lesson ends as an update to Knowledge, never to the engine. Each knowledge row
records the lesson that produced it, so the game can always answer "why does my duck
play this?" and a lesson can be undone later.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from duckgambit.domain.balance import DEFAULT_BALANCE, Balance
from duckgambit.domain.chessutil import UCI_MOVE
from duckgambit.domain.duck import Duck, Growth
from duckgambit.domain.errors import DomainError
from duckgambit.domain.events import DuckLeveledUp, Event, KnowledgeAdded, LessonCompleted
from duckgambit.domain.knowledge import PuzzleMemoryEntry, RepertoireEntry

LESSON_KINDS = ("opening", "fix")  # principles and motif drills arrive in M2 and M4


@dataclass(frozen=True)
class TaughtMove:
    position_key: str
    move: str
    color: str = "white"  # used by opening lessons: the side the duck plays
    weight: int = 1


@dataclass(frozen=True)
class Lesson:
    id: str
    kind: str
    moves: tuple[TaughtMove, ...]
    xp: int | None = None  # None: use the balance table's reward for this kind


def apply_lesson(
    duck: Duck, lesson: Lesson, balance: Balance = DEFAULT_BALANCE
) -> tuple[Duck, list[Event]]:
    """Return the duck after the lesson and the events that describe what changed."""
    if lesson.kind not in LESSON_KINDS:
        raise DomainError("lesson.unknown_kind", f"Unknown lesson kind: {lesson.kind!r}")
    if not lesson.moves:
        raise DomainError("lesson.empty", "A lesson must teach at least one move")
    for taught in lesson.moves:
        if not UCI_MOVE.match(taught.move) or taught.color not in ("white", "black"):
            raise DomainError("lesson.invalid_move", f"Not a teachable move: {taught.move!r}")

    knowledge = duck.knowledge
    added = 0
    if lesson.kind == "opening":
        known = {(e.color, e.position_key, e.move) for e in knowledge.repertoire}
        new_entries = []
        for taught in lesson.moves:
            key = (taught.color, taught.position_key, taught.move)
            if key not in known:
                known.add(key)
                new_entries.append(
                    RepertoireEntry(
                        taught.color,
                        taught.position_key,
                        taught.move,
                        taught.weight,
                        "lesson",
                        lesson.id,
                    )
                )
        added = len(new_entries)
        knowledge = replace(knowledge, repertoire=(*knowledge.repertoire, *new_entries))
    else:  # "fix": the latest fix for a position replaces the earlier one
        replaced = {taught.position_key for taught in lesson.moves}
        kept = tuple(e for e in knowledge.puzzle_memory if e.position_key not in replaced)
        new_memory = tuple(
            PuzzleMemoryEntry(taught.position_key, taught.move, lesson.id)
            for taught in lesson.moves
        )
        added = len(new_memory)
        knowledge = replace(knowledge, puzzle_memory=(*kept, *new_memory))

    reward = lesson.xp if lesson.xp is not None else balance.xp_rewards["lesson_completed"]
    xp = duck.growth.xp + max(0, reward)
    level = balance.level_for_xp(xp)
    growth = Growth(stage=balance.stage_for(level).name, level=level, xp=xp)
    updated = replace(duck, knowledge=knowledge, growth=growth)

    events: list[Event] = [LessonCompleted(duck.id, lesson.id, lesson.kind, max(0, reward))]
    if added:
        target = "repertoire" if lesson.kind == "opening" else "puzzle_memory"
        events.append(KnowledgeAdded(duck.id, lesson.id, target, added))
    if level > duck.growth.level:
        events.append(
            DuckLeveledUp(
                duck_id=duck.id,
                level=level,
                stage=growth.stage,
                stat_budget=balance.stat_budget(level),
                stage_advanced=growth.stage != duck.growth.stage,
            )
        )
    return updated, events
