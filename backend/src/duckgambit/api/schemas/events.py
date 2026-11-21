"""Wire schemas for the event stream (ADR-0002).

One envelope class per event type, discriminated by `type`, so generated clients get a
tagged union: checking `event.type` narrows `event.data`. These mirror the dataclasses
in `domain/events.py`; a test keeps the two in step.

Clients must ignore event types and fields they do not know.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from duckgambit.api.schemas.base import WdlField, Wire
from duckgambit.services.records import Envelope


class DuckHatchedData(Wire):
    duck_id: str
    name: str
    species: str
    stage: str
    level: int
    stats: dict[str, int]


class MatchCreatedData(Wire):
    match_id: str
    duck_ids: list[str]
    games: int
    mode: str
    rated: bool


class MatchStartedData(Wire):
    match_id: str


class GameStartedData(Wire):
    match_id: str
    game_id: str
    index: int
    white_duck_id: str
    black_duck_id: str
    initial_fen: str
    white_clock_ms: int | None
    black_clock_ms: int | None


class AdjustmentModel(Wire):
    rule_id: str
    kind: Literal["aggression", "solidity", "principle", "motif"]
    delta_cp: int
    label: str


class CandidateModel(Wire):
    move: str
    san: str
    rank: int = Field(description="The engine's own order; 1 is its favourite")
    cp: int | None = Field(description="Centipawns from the mover's side; null when it is a mate")
    mate: int | None
    wdl: WdlField
    base_score: int
    adjustments: list[AdjustmentModel]
    final_score: int
    filtered: bool = Field(description="Ruled out by the duck's blunder tolerance")
    probability_ppm: int = Field(description="Chance this move was played, parts per million")
    pv: list[str]


class ReasonModel(Wire):
    code: str = Field(description="Stable identifier; render your own copy from it if you like")
    text: str = Field(description="Default English sentence")
    params: dict[str, str | int]


class MoveChosenData(Wire):
    game_id: str
    ply: int
    duck_id: str
    color: Literal["white", "black"]
    fen_before: str
    move: str
    san: str
    source: Literal["memory", "book", "forced", "engine"]
    candidates: list[CandidateModel]
    reasons: list[ReasonModel]
    think_ms: int = Field(description="Virtual think time; pace playback with this")
    nodes_budget: int
    nodes: int
    depth: int


class MoveMadeData(Wire):
    game_id: str
    ply: int
    color: Literal["white", "black"]
    by: Literal["duck", "human"]
    duck_id: str | None
    uci: str
    san: str
    fen_after: str
    capture: bool
    en_passant: bool
    check: bool
    checkmate: bool
    castle: Literal["kingside", "queenside"] | None
    promotion: Literal["q", "r", "b", "n"] | None
    think_ms: int
    white_clock_ms: int | None
    black_clock_ms: int | None


class GameFinishedData(Wire):
    match_id: str
    game_id: str
    result: Literal["1-0", "0-1", "1/2-1/2"]
    termination: str
    winner_duck_id: str | None
    plies: int


class DuckScoreData(Wire):
    duck_id: str
    points: float


class MatchFinishedData(Wire):
    match_id: str
    scores: list[DuckScoreData]
    winner_duck_id: str | None


class RatingUpdatedData(Wire):
    duck_id: str
    context_id: str
    kind: Literal["game", "puzzle"]
    before: float
    after: float
    deviation: float
    games: int
    provisional: bool


class JobProgressedData(Wire):
    job_id: str
    state: str
    done: int
    total: int


class JobFinishedData(Wire):
    job_id: str
    state: str
    error_code: str | None


class _Envelope(Wire):
    cursor: int = Field(description="Global position; pass as `after` (or Last-Event-ID) to resume")
    stream: str
    seq: int = Field(description="Position within the stream, starting at 1")
    recorded_at: str


class DuckHatchedEvent(_Envelope):
    type: Literal["DuckHatched"]
    data: DuckHatchedData


class MatchCreatedEvent(_Envelope):
    type: Literal["MatchCreated"]
    data: MatchCreatedData


class MatchStartedEvent(_Envelope):
    type: Literal["MatchStarted"]
    data: MatchStartedData


class GameStartedEvent(_Envelope):
    type: Literal["GameStarted"]
    data: GameStartedData


class MoveChosenEvent(_Envelope):
    type: Literal["MoveChosen"]
    data: MoveChosenData


class MoveMadeEvent(_Envelope):
    type: Literal["MoveMade"]
    data: MoveMadeData


class GameFinishedEvent(_Envelope):
    type: Literal["GameFinished"]
    data: GameFinishedData


class MatchFinishedEvent(_Envelope):
    type: Literal["MatchFinished"]
    data: MatchFinishedData


class RatingUpdatedEvent(_Envelope):
    type: Literal["RatingUpdated"]
    data: RatingUpdatedData


class JobProgressedEvent(_Envelope):
    type: Literal["JobProgressed"]
    data: JobProgressedData


class JobFinishedEvent(_Envelope):
    type: Literal["JobFinished"]
    data: JobFinishedData


EventEnvelope = Annotated[
    DuckHatchedEvent
    | MatchCreatedEvent
    | MatchStartedEvent
    | GameStartedEvent
    | MoveChosenEvent
    | MoveMadeEvent
    | GameFinishedEvent
    | MatchFinishedEvent
    | RatingUpdatedEvent
    | JobProgressedEvent
    | JobFinishedEvent,
    Field(discriminator="type"),
]

EVENT_ADAPTER: TypeAdapter[EventEnvelope] = TypeAdapter(EventEnvelope)


class EventPage(Wire):
    events: list[EventEnvelope]
    next_cursor: int = Field(description="Pass as `after` to continue")


def to_wire(envelope: Envelope) -> EventEnvelope:
    return EVENT_ADAPTER.validate_python(
        {
            "cursor": envelope.cursor,
            "stream": envelope.stream,
            "seq": envelope.seq,
            "recorded_at": envelope.recorded_at,
            "type": envelope.type,
            "data": envelope.data,
        }
    )


def wire_event_types() -> set[str]:
    schema = EVENT_ADAPTER.json_schema()
    return set(schema["discriminator"]["mapping"])
