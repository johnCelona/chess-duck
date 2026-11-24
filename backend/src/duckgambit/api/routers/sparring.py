from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from duckgambit.api.deps import Services
from duckgambit.api.schemas.base import ID_PATTERN
from duckgambit.api.schemas.sparring import (
    SparringGameOut,
    SparringMoveIn,
    SparringSeriesOut,
    StartSeriesRequest,
    StartSparringRequest,
)

games = APIRouter(prefix="/sparring", tags=["sparring"])
series = APIRouter(prefix="/sparring-series", tags=["sparring"])

ResourceId = Annotated[str, Path(pattern=ID_PATTERN)]
Deps = Annotated[Services, Depends()]


@games.post("", status_code=201, operation_id="startSparring")
async def start_sparring(body: StartSparringRequest, services: Deps) -> SparringGameOut:
    """Play one of your ducks. Untimed unless you give a time control. Never rated."""
    control = body.time_control
    view = await services.sparring.start(
        body.duck_id,
        body.engine_id,
        body.human_color,
        control.base_seconds * 1000 if control else None,
        control.increment_seconds * 1000 if control else 0,
    )
    return SparringGameOut.of(view)


@games.get("", operation_id="listSparring")
async def list_sparring(
    services: Deps, limit: Annotated[int, Query(ge=1, le=50)] = 10
) -> list[SparringGameOut]:
    """Your recent games against your ducks, newest first (series games excluded)."""
    return [
        SparringGameOut.of(await services.sparring.get(game.id))
        for game in await services.sparring.recent(limit)
    ]


@games.get("/{game_id}", operation_id="getSparring")
async def get_sparring(game_id: ResourceId, services: Deps) -> SparringGameOut:
    return SparringGameOut.of(await services.sparring.get(game_id))


@games.post("/{game_id}/moves", operation_id="playSparringMove")
async def play_move(game_id: ResourceId, body: SparringMoveIn, services: Deps) -> SparringGameOut:
    """Your move. The duck's reply follows on the game's stream."""
    return SparringGameOut.of(await services.sparring.move(game_id, body.uci))


@games.put("/{game_id}/resignation", operation_id="resignSparring")
async def resign(game_id: ResourceId, services: Deps) -> SparringGameOut:
    return SparringGameOut.of(await services.sparring.resign(game_id))


@games.put("/{game_id}/timeout-claim", operation_id="claimSparringTimeout")
async def claim_timeout(game_id: ResourceId, services: Deps) -> SparringGameOut:
    """Your clock reached zero on screen: the server checks and ends the game."""
    return SparringGameOut.of(await services.sparring.claim_timeout(game_id))


@series.post("", status_code=201, operation_id="startSparringSeries")
async def start_series(body: StartSeriesRequest, services: Deps) -> SparringSeriesOut:
    """You against your duck: best of N, 30 seconds each. The first game starts now."""
    view = await services.sparring.start_series(body.duck_id, body.engine_id, body.best_of)
    return SparringSeriesOut.of(view)


@series.get("/{series_id}", operation_id="getSparringSeries")
async def get_series(series_id: ResourceId, services: Deps) -> SparringSeriesOut:
    return SparringSeriesOut.of(await services.sparring.get_series(series_id))


@series.post("/{series_id}/games", status_code=201, operation_id="nextSparringSeriesGame")
async def next_game(series_id: ResourceId, services: Deps) -> SparringSeriesOut:
    """Start the next game of the series (an Armageddon game if it is tied)."""
    return SparringSeriesOut.of(await services.sparring.next_series_game(series_id))
