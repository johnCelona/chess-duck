from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from duckgambit.api.schemas.base import Id, Wire, WireIn
from duckgambit.domain.arena import (
    STARTING_FEN,
    Arena,
    EngineSettings,
    NodesLimit,
    VirtualClockLimit,
)
from duckgambit.services.records import GameRecord, JobRecord, MatchRecord, MoveRecord


class ArenaEngine(WireIn):
    id: Id
    threads: Literal[1] = Field(
        default=1, description="Always 1: multi-threaded search is not reproducible"
    )
    hash_mb: int = Field(default=16, ge=1, le=256)


class NodesLimitModel(WireIn):
    type: Literal["nodes"]
    value: int = Field(
        ge=1, le=5_000_000, description="Nodes per move before the duck's multiplier"
    )


class TimeControl(WireIn):
    base_seconds: int = Field(ge=1, le=3600)
    increment_seconds: int = Field(default=0, ge=0, le=60)


class VirtualClockLimitModel(WireIn):
    """A simulated clock: think time converts to nodes, so results do not depend on the machine."""

    type: Literal["virtual-clock"]
    time_control: TimeControl
    virtual_nps: int = Field(default=200_000, ge=1_000, le=5_000_000)


LimitModel = Annotated[NodesLimitModel | VirtualClockLimitModel, Field(discriminator="type")]


class ArenaModel(WireIn):
    """Match conditions shared by every duck (spec 7.1)."""

    engine: ArenaEngine
    limit: LimitModel
    seed: int = Field(ge=0, le=2**53 - 1, description="Same seed, same ducks, same games")
    multi_pv: int = Field(default=5, ge=1, le=10, alias="multiPV")
    games: int = Field(default=1, ge=1, le=100)
    swap_colors: bool = True
    equal_engine: bool = Field(
        default=False, description="Ignore the calculation stat: every duck gets the same nodes"
    )
    max_plies: int = Field(default=400, ge=2, le=1000)
    initial_fen: str = Field(default=STARTING_FEN, max_length=100)

    def to_domain(self) -> Arena:
        limit: NodesLimit | VirtualClockLimit
        if isinstance(self.limit, NodesLimitModel):
            limit = NodesLimit(self.limit.value)
        else:
            limit = VirtualClockLimit(
                self.limit.time_control.base_seconds * 1000,
                self.limit.time_control.increment_seconds * 1000,
                self.limit.virtual_nps,
            )
        return Arena(
            engine=EngineSettings(self.engine.id, self.engine.threads, self.engine.hash_mb),
            limit=limit,
            seed=self.seed,
            multipv=self.multi_pv,
            games=self.games,
            swap_colors=self.swap_colors,
            equal_engine=self.equal_engine,
            max_plies=self.max_plies,
            initial_fen=self.initial_fen,
        )

    @classmethod
    def of(cls, arena: Arena) -> ArenaModel:
        limit: NodesLimitModel | VirtualClockLimitModel
        if isinstance(arena.limit, NodesLimit):
            limit = NodesLimitModel(type="nodes", value=arena.limit.nodes)
        else:
            limit = VirtualClockLimitModel(
                type="virtual-clock",
                time_control=TimeControl(
                    base_seconds=arena.limit.base_ms // 1000,
                    increment_seconds=arena.limit.increment_ms // 1000,
                ),
                virtual_nps=arena.limit.virtual_nps,
            )
        return cls(
            engine=ArenaEngine(id=arena.engine.id, threads=1, hash_mb=arena.engine.hash_mb),
            limit=limit,
            seed=arena.seed,
            multi_pv=arena.multipv,
            games=arena.games,
            swap_colors=arena.swap_colors,
            equal_engine=arena.equal_engine,
            max_plies=arena.max_plies,
            initial_fen=arena.initial_fen,
        )


class CreateMatchRequest(WireIn):
    duck_ids: list[Id] = Field(
        min_length=2, max_length=2, description="First duck has White in the first game"
    )
    arena: ArenaModel
    rated: bool = True


class DuckScoreOut(Wire):
    duck_id: str
    points: float


MatchState = Literal["created", "running", "finished", "cancelled", "failed"]


class MatchOut(Wire):
    id: str
    duck_ids: list[str]
    arena: ArenaModel
    mode: str
    rated: bool
    state: MatchState
    context_id: str
    job_id: str
    scores: list[DuckScoreOut]
    created_at: str
    finished_at: str | None
    stream: str = Field(description="Event stream to follow this match live or replay it")

    @classmethod
    def of(cls, match: MatchRecord) -> MatchOut:
        return cls(
            id=match.id,
            duck_ids=list(match.duck_ids),
            arena=ArenaModel.of(match.arena),
            mode=match.mode,
            rated=match.rated,
            state=match.state,
            context_id=match.context_id,
            job_id=match.job_id,
            scores=[
                DuckScoreOut(duck_id=duck_id, points=match.scores.get(duck_id, 0.0))
                for duck_id in match.duck_ids
            ],
            created_at=match.created_at,
            finished_at=match.finished_at,
            stream=f"match:{match.id}",
        )


class GameOut(Wire):
    id: str
    match_id: str
    index: int
    white_duck_id: str
    black_duck_id: str
    seed: int
    initial_fen: str
    state: Literal["running", "finished"]
    result: str | None
    termination: str | None
    white_clock_ms: int | None
    black_clock_ms: int | None
    started_at: str
    finished_at: str | None

    @classmethod
    def of(cls, game: GameRecord) -> GameOut:
        return cls.model_validate(game)


class MoveOut(Wire):
    ply: int
    color: Literal["white", "black"]
    uci: str
    san: str
    source: str
    cp: int | None
    mate: int | None
    nodes: int
    depth: int
    think_ms: int
    clock_ms: int | None
    fen_after: str

    @classmethod
    def of(cls, move: MoveRecord) -> MoveOut:
        return cls.model_validate(move)


JobState = Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]


class JobOut(Wire):
    id: str
    kind: str
    state: JobState
    done: int
    total: int
    error_code: str | None
    error_detail: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    stream: str

    @classmethod
    def of(cls, job: JobRecord) -> JobOut:
        return cls(
            id=job.id,
            kind=job.kind,
            state=job.state,
            done=job.done,
            total=job.total,
            error_code=job.error_code,
            error_detail=job.error_detail,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            stream=f"job:{job.id}",
        )


class HealthOut(Wire):
    status: Literal["ok"]
    version: str
    api_version: Literal["v1"]
    schema_version: int
    engine_budget: int
    fake_engine: bool
    lichess_enabled: bool
