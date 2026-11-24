from __future__ import annotations

from typing import Literal

from pydantic import Field

from duckgambit.api.schemas.base import Id, Wire, WireIn
from duckgambit.api.schemas.matches import TimeControl
from duckgambit.domain.chessutil import UCI_MOVE
from duckgambit.services.sparring import SeriesView, SparringView, series_stream, sparring_stream

Color = Literal["white", "black"]


class StartSparringRequest(WireIn):
    duck_id: Id
    engine_id: Id
    human_color: Literal["white", "black", "random"] = "random"
    time_control: TimeControl | None = Field(
        default=None, description="Your clock and the duck's; null (the default) is untimed"
    )


class SparringMoveIn(WireIn):
    uci: str = Field(pattern=UCI_MOVE.pattern, description="Your move, e.g. e2e4 or e7e8q")


class SparringMoveOut(Wire):
    ply: int
    color: Color
    by: Literal["human", "duck"]
    uci: str
    san: str
    fen_after: str


class SparringGameOut(Wire):
    """A game against your duck. Never rated."""

    id: str
    duck_id: str
    engine_id: str
    human_color: Color
    time_control: TimeControl | None
    state: Literal["running", "finished"]
    result: Literal["1-0", "0-1", "1/2-1/2"] | None
    termination: str | None
    winner: Literal["human", "duck"] | None
    initial_fen: str
    fen: str
    turn: Color
    check: bool
    moves: list[SparringMoveOut]
    legal_moves: list[str] = Field(
        description="Your legal moves in UCI when it is your turn; empty otherwise"
    )
    duck_thinking: bool
    white_clock_ms: int | None = Field(description="Time left now; null when untimed")
    black_clock_ms: int | None
    series_id: str | None
    series_index: int | None
    created_at: str
    stream: str

    @classmethod
    def of(cls, view: SparringView) -> SparringGameOut:
        game = view.game
        control = (
            TimeControl(
                base_seconds=game.base_ms // 1000, increment_seconds=game.increment_ms // 1000
            )
            if game.base_ms is not None
            else None
        )
        legal = sorted(move.uci() for move in view.board.legal_moves) if view.human_to_move else []
        return cls(
            id=game.id,
            duck_id=game.duck_id,
            engine_id=game.engine_id,
            human_color=game.human_color,
            time_control=control,
            state=game.state,
            result=game.result,
            termination=game.termination,
            winner=view.winner,
            initial_fen=game.initial_fen,
            fen=view.board.fen(),
            turn=view.turn,
            check=view.board.is_check(),
            moves=[
                SparringMoveOut(
                    ply=m.ply,
                    color=m.color,
                    by=m.by,
                    uci=m.uci,
                    san=m.san,
                    fen_after=m.fen_after,
                )
                for m in view.moves
            ],
            legal_moves=legal,
            duck_thinking=game.state == "running" and not view.human_to_move,
            white_clock_ms=view.clock_ms("white"),
            black_clock_ms=view.clock_ms("black"),
            series_id=game.series_id,
            series_index=game.series_index,
            created_at=game.created_at,
            stream=sparring_stream(game.id),
        )


class StartSeriesRequest(WireIn):
    duck_id: Id
    engine_id: Id
    best_of: int = Field(description="3, 5, 7 or 15")


class SparringSeriesOut(Wire):
    """A "You play" Super Bullet series: 30 seconds each, Armageddon if tied."""

    id: str
    duck_id: str
    best_of: int
    state: Literal["playing", "armageddon", "decided"]
    human_points: float
    duck_points: float
    winner: Literal["human", "duck"] | None
    decided_by: Literal["games", "armageddon"] | None
    armageddon_human_color: Color | None
    game_ids: list[str]
    current_game_id: str | None = Field(description="The latest game, running or finished")
    stream: str

    @classmethod
    def of(cls, view: SeriesView) -> SparringSeriesOut:
        status = view.status
        return cls(
            id=view.series.id,
            duck_id=view.series.duck_id,
            best_of=view.series.best_of,
            state=status.state,
            human_points=float(status.first_points),
            duck_points=float(status.second_points),
            winner=view.winner,
            decided_by=status.decided_by,
            armageddon_human_color=view.armageddon_human_color,
            game_ids=[game.id for game in view.games],
            current_game_id=view.games[-1].id if view.games else None,
            stream=series_stream(view.series.id),
        )
