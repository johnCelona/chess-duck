"""The duck file: a portable, versioned JSON export friends can share (ADR-0004).

Importing never trusts the file. The stat budget is re-checked against the level,
the duck gets a new local id, care is reset, and ratings are kept only as a claim.
"""

from __future__ import annotations

from typing import Any

from duckgambit.domain.balance import DEFAULT_BALANCE, Balance
from duckgambit.domain.brand import APP_NAME
from duckgambit.domain.chessutil import UCI_MOVE
from duckgambit.domain.duck import (
    EGG_SEED_MAX,
    Avatar,
    Care,
    Duck,
    Growth,
    validate_avatar,
    validate_name,
    validate_stats,
)
from duckgambit.domain.errors import DomainError
from duckgambit.domain.knowledge import Knowledge, PuzzleMemoryEntry, RepertoireEntry

FORMAT = "duck-gambit.duck"
DUCK_FILE_VERSION = 1
MAX_REPERTOIRE_ENTRIES = 50_000
MAX_LIST_ENTRIES = 5_000


def export_duck(
    duck: Duck,
    ratings: list[dict[str, Any]],
    exported_at: str,
    app_version: str,
) -> dict[str, Any]:
    def side(color: str) -> list[dict[str, Any]]:
        return [
            {"fen": e.position_key, "move": e.move, "weight": e.weight, "source": e.source}
            for e in duck.knowledge.repertoire
            if e.color == color
        ]

    return {
        "format": FORMAT,
        "schemaVersion": DUCK_FILE_VERSION,
        "exportedAt": exported_at,
        "exportedBy": {"app": "duck-gambit", "version": app_version},
        "duck": {
            "id": duck.id,
            "name": duck.name,
            "avatar": {
                "species": duck.avatar.species,
                "skin": duck.avatar.skin,
                "accessories": list(duck.avatar.accessories),
            },
            "growth": {
                "stage": duck.growth.stage,
                "level": duck.growth.level,
                "xp": duck.growth.xp,
            },
            "stats": dict(duck.stats),
            "eggSeed": duck.egg_seed,
            "knowledge": {
                "repertoire": {"white": side("white"), "black": side("black")},
                "principles": list(duck.knowledge.principles),
                "motifs": dict(duck.knowledge.motifs),
                "puzzleMemory": [
                    {"fen": e.position_key, "move": e.move} for e in duck.knowledge.puzzle_memory
                ],
            },
            "ratings": ratings,
        },
    }


def upcast(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade an older duck file to the current version. One step per version."""
    version = data.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise DomainError("duckfile.invalid", "Missing or invalid schemaVersion")
    if version > DUCK_FILE_VERSION:
        raise DomainError(
            "duckfile.too_new",
            f"This duck file is version {version}; this build reads up to {DUCK_FILE_VERSION}",
        )
    # version 1 is current; future steps go here: `if version < 2: data = _v1_to_v2(data)`
    return data


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DomainError("duckfile.invalid", message)


def _entries(raw: Any, what: str, limit: int) -> list[dict[str, Any]]:
    _require(isinstance(raw, list) and len(raw) <= limit, f"{what} must be a list of entries")
    for entry in raw:
        _require(isinstance(entry, dict), f"{what} entries must be objects")
        _require(
            isinstance(entry.get("fen"), str) and 0 < len(entry["fen"]) <= 100,
            f"{what} entry has no position",
        )
        _require(
            isinstance(entry.get("move"), str) and bool(UCI_MOVE.match(entry["move"])),
            f"{what} entry has an invalid move",
        )
    return list(raw)


def import_duck(
    data: Any,
    *,
    duck_id: str,
    profile_id: str,
    now: str,
    balance: Balance = DEFAULT_BALANCE,
) -> Duck:
    """Validate a duck file and build a local duck from it."""
    _require(isinstance(data, dict) and data.get("format") == FORMAT, f"Not a {APP_NAME} duck file")
    data = upcast(data)
    body = data.get("duck")
    _require(isinstance(body, dict), "The file has no duck")

    growth_raw = body.get("growth")
    _require(isinstance(growth_raw, dict), "The duck has no growth data")
    xp = growth_raw.get("xp")
    _require(
        isinstance(xp, int) and not isinstance(xp, bool) and 0 <= xp <= 10**9, "Invalid xp value"
    )
    # Level and stage are derived from XP, never read from the file.
    level = balance.level_for_xp(xp)

    stats = body.get("stats")
    _require(isinstance(stats, dict), "The duck has no stats")
    validate_stats(stats, level, balance)

    avatar_raw = body.get("avatar") if isinstance(body.get("avatar"), dict) else {}
    accessories = avatar_raw.get("accessories", [])
    _require(
        isinstance(accessories, list) and all(isinstance(a, str) for a in accessories),
        "Invalid accessories",
    )
    avatar = validate_avatar(
        Avatar(
            str(avatar_raw.get("species", "mallard")),
            str(avatar_raw.get("skin", "default")),
            tuple(accessories),
        )
    )

    knowledge_raw = body.get("knowledge") if isinstance(body.get("knowledge"), dict) else {}
    repertoire_raw = knowledge_raw.get("repertoire", {})
    _require(isinstance(repertoire_raw, dict), "Invalid repertoire")
    repertoire: list[RepertoireEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for color in ("white", "black"):
        for entry in _entries(repertoire_raw.get(color, []), "Repertoire", MAX_REPERTOIRE_ENTRIES):
            weight = entry.get("weight", 1)
            _require(
                isinstance(weight, int) and not isinstance(weight, bool) and 1 <= weight <= 1000,
                "Repertoire weight must be between 1 and 1000",
            )
            key = (color, entry["fen"], entry["move"])
            if key not in seen:
                seen.add(key)
                repertoire.append(
                    RepertoireEntry(color, entry["fen"], entry["move"], weight, "import")
                )

    memory: dict[str, PuzzleMemoryEntry] = {}
    for entry in _entries(knowledge_raw.get("puzzleMemory", []), "Puzzle memory", MAX_LIST_ENTRIES):
        memory[entry["fen"]] = PuzzleMemoryEntry(entry["fen"], entry["move"])

    principles = knowledge_raw.get("principles", [])
    _require(
        isinstance(principles, list)
        and len(principles) <= 100
        and all(isinstance(p, str) and len(p) <= 64 for p in principles),
        "Invalid principles",
    )
    motifs = knowledge_raw.get("motifs", {})
    _require(
        isinstance(motifs, dict)
        and len(motifs) <= 100
        and all(
            isinstance(k, str)
            and len(k) <= 64
            and isinstance(v, int)
            and not isinstance(v, bool)
            and 0 <= v <= 100
            for k, v in motifs.items()
        ),
        "Invalid motifs",
    )

    # Optional and additive (files written before it simply lack it). It is provenance only:
    # the stats above are validated on their own and are not re-derived from the seed.
    egg_seed = body.get("eggSeed")
    if egg_seed is not None:
        _require(
            isinstance(egg_seed, int)
            and not isinstance(egg_seed, bool)
            and 0 <= egg_seed <= EGG_SEED_MAX,
            "Invalid egg seed",
        )

    name = body.get("name")
    _require(isinstance(name, str), "The duck has no name")
    origin = body.get("id")
    return Duck(
        id=duck_id,
        profile_id=profile_id,
        name=validate_name(name),
        avatar=avatar,
        growth=Growth(stage=balance.stage_for(level).name, level=level, xp=xp),
        stats=dict(stats),
        care=Care(),
        knowledge=Knowledge(
            repertoire=tuple(repertoire),
            principles=tuple(principles),
            motifs=dict(motifs),
            puzzle_memory=tuple(memory.values()),
        ),
        created_at=now,
        origin=origin if isinstance(origin, str) and len(origin) <= 64 else None,
        egg_seed=egg_seed,
    )
