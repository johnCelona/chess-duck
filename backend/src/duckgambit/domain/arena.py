"""Arena settings: the conditions every duck in a match shares (spec 7.1)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from duckgambit.domain.errors import DomainError

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MAX_SEED = 2**53 - 1  # exact in JSON numbers


@dataclass(frozen=True)
class EngineSettings:
    id: str
    threads: int = 1
    hash_mb: int = 16


@dataclass(frozen=True)
class NodesLimit:
    nodes: int
    type: str = "nodes"


@dataclass(frozen=True)
class VirtualClockLimit:
    base_ms: int
    increment_ms: int
    virtual_nps: int
    type: str = "virtual-clock"


Limit = NodesLimit | VirtualClockLimit


@dataclass(frozen=True)
class Arena:
    engine: EngineSettings
    limit: Limit
    seed: int
    multipv: int = 5
    games: int = 1
    swap_colors: bool = True
    equal_engine: bool = False
    max_plies: int = 400
    initial_fen: str = STARTING_FEN


@dataclass(frozen=True)
class ArenaCaps:
    """Server-side limits (ADR-0011). Rated play is single-threaded by rule (ADR-0006)."""

    max_nodes: int = 5_000_000
    max_hash_mb: int = 256
    max_games: int = 100
    max_plies: int = 1000
    max_virtual_nps: int = 5_000_000
    max_base_ms: int = 3_600_000


BULLET = VirtualClockLimit(base_ms=60_000, increment_ms=0, virtual_nps=200_000)
CASUAL = NodesLimit(nodes=50_000)


def validate_arena(arena: Arena, caps: ArenaCaps = ArenaCaps()) -> None:
    if arena.engine.threads != 1:
        raise DomainError(
            "arena.threads",
            "Matches use one engine thread: multi-threaded search is not reproducible",
        )
    if not 1 <= arena.engine.hash_mb <= caps.max_hash_mb:
        raise DomainError("arena.hash", f"hashMb must be between 1 and {caps.max_hash_mb}")
    if not 1 <= arena.multipv <= 10:
        raise DomainError("arena.multipv", "multiPV must be between 1 and 10")
    if not 1 <= arena.games <= caps.max_games:
        raise DomainError("arena.games", f"games must be between 1 and {caps.max_games}")
    if not 2 <= arena.max_plies <= caps.max_plies:
        raise DomainError("arena.max_plies", f"maxPlies must be between 2 and {caps.max_plies}")
    if not 0 <= arena.seed <= MAX_SEED:
        raise DomainError("arena.seed", "seed must be between 0 and 2^53 - 1")
    limit = arena.limit
    if isinstance(limit, NodesLimit):
        if not 1 <= limit.nodes <= caps.max_nodes:
            raise DomainError("arena.limit", f"nodes must be between 1 and {caps.max_nodes}")
    else:
        if not 1_000 <= limit.base_ms <= caps.max_base_ms:
            raise DomainError("arena.limit", "base time must be between 1 second and 1 hour")
        if not 0 <= limit.increment_ms <= 60_000:
            raise DomainError("arena.limit", "increment must be between 0 and 60 seconds")
        if not 1_000 <= limit.virtual_nps <= caps.max_virtual_nps:
            raise DomainError(
                "arena.limit", f"virtualNps must be between 1000 and {caps.max_virtual_nps}"
            )


def time_control_tag(limit: Limit) -> str:
    """The PGN TimeControl header value."""
    if isinstance(limit, VirtualClockLimit):
        return f"{limit.base_ms // 1000}+{limit.increment_ms // 1000}"
    return "-"


@dataclass(frozen=True)
class RatingContext:
    """A rating only means something inside one context (spec 6.3)."""

    engine_id: str
    engine_version: str
    engine_fingerprint: str
    limit_type: str
    virtual_nps: int
    nodes: int
    hash_mb: int
    multipv: int
    equal_engine: bool
    decision_version: str
    balance_version: str

    @property
    def id(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "ctx_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def rating_context(
    arena: Arena,
    engine_version: str,
    engine_fingerprint: str,
    decision_version: str,
    balance_version: str,
) -> RatingContext:
    limit = arena.limit
    return RatingContext(
        engine_id=arena.engine.id,
        engine_version=engine_version,
        engine_fingerprint=engine_fingerprint,
        limit_type=limit.type,
        virtual_nps=limit.virtual_nps if isinstance(limit, VirtualClockLimit) else 0,
        nodes=limit.nodes if isinstance(limit, NodesLimit) else 0,
        hash_mb=arena.engine.hash_mb,
        multipv=arena.multipv,
        equal_engine=arena.equal_engine,
        decision_version=decision_version,
        balance_version=balance_version,
    )


def arena_from_doc(doc: dict[str, Any]) -> Arena:
    """Rebuild an Arena from `dataclasses.asdict(arena)` (the stored snapshot)."""
    limit_doc = dict(doc["limit"])
    limit: Limit
    if limit_doc.get("type") == "virtual-clock":
        limit = VirtualClockLimit(
            limit_doc["base_ms"], limit_doc["increment_ms"], limit_doc["virtual_nps"]
        )
    else:
        limit = NodesLimit(limit_doc["nodes"])
    return Arena(
        engine=EngineSettings(**doc["engine"]),
        limit=limit,
        seed=doc["seed"],
        multipv=doc["multipv"],
        games=doc["games"],
        swap_colors=doc["swap_colors"],
        equal_engine=doc["equal_engine"],
        max_plies=doc["max_plies"],
        initial_fen=doc["initial_fen"],
    )
