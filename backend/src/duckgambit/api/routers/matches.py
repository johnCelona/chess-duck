from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import PlainTextResponse

from duckgambit.api.deps import Services
from duckgambit.api.schemas.base import ID_PATTERN
from duckgambit.api.schemas.matches import CreateMatchRequest, GameOut, JobOut, MatchOut, MoveOut
from duckgambit.services.errors import ServiceError

matches = APIRouter(prefix="/matches", tags=["matches"])
games = APIRouter(prefix="/games", tags=["matches"])
jobs = APIRouter(prefix="/jobs", tags=["jobs"])

ResourceId = Annotated[str, Path(pattern=ID_PATTERN)]
Deps = Annotated[Services, Depends()]


@matches.post("", status_code=201, operation_id="createMatch")
async def create_match(body: CreateMatchRequest, services: Deps) -> MatchOut:
    """Start a duck-vs-duck match as a background job. Follow `stream` to watch it."""
    first, second = body.duck_ids
    series = body.series.to_domain() if body.series else None
    match = await services.matches.create(
        (first, second), body.arena.to_domain(), body.rated, series
    )
    return MatchOut.of(match)


@matches.get("", operation_id="listMatches")
async def list_matches(
    services: Deps, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[MatchOut]:
    return [MatchOut.of(match) for match in await services.matches.recent(limit)]


@matches.get("/{match_id}", operation_id="getMatch")
async def get_match(match_id: ResourceId, services: Deps) -> MatchOut:
    return MatchOut.of(await services.matches.get(match_id))


@matches.get("/{match_id}/games", operation_id="listMatchGames")
async def list_games(match_id: ResourceId, services: Deps) -> list[GameOut]:
    return [GameOut.of(game) for game in await services.matches.games(match_id)]


@matches.put("/{match_id}/resumption", operation_id="resumeMatch")
async def resume_match(match_id: ResourceId, services: Deps) -> MatchOut:
    """Continue a cancelled, failed or interrupted match from its last recorded move."""
    await services.matches.resume(match_id)
    return MatchOut.of(await services.matches.get(match_id))


@games.get("/{game_id}", operation_id="getGame")
async def get_game(game_id: ResourceId, services: Deps) -> GameOut:
    return GameOut.of(await services.matches.game(game_id))


@games.get("/{game_id}/moves", operation_id="listGameMoves")
async def list_moves(game_id: ResourceId, services: Deps) -> list[MoveOut]:
    return [MoveOut.of(move) for move in await services.matches.moves(game_id)]


@games.get(
    "/{game_id}/pgn",
    operation_id="getGamePgn",
    response_class=PlainTextResponse,
    responses={200: {"content": {"application/x-chess-pgn": {"schema": {"type": "string"}}}}},
)
async def get_pgn(game_id: ResourceId, services: Deps) -> PlainTextResponse:
    """The finished game as PGN with evals, clocks and move sources in comments."""
    game = await services.matches.game(game_id)
    if game.pgn is None:
        raise ServiceError("game.not_finished", "The PGN is ready when the game finishes", 409)
    return PlainTextResponse(
        game.pgn,
        media_type="application/x-chess-pgn",
        headers={"Content-Disposition": f'attachment; filename="{game.id}.pgn"'},
    )


@jobs.get("/{job_id}", operation_id="getJob")
async def get_job(job_id: ResourceId, services: Deps) -> JobOut:
    return JobOut.of(await services.jobs.get(job_id))


@jobs.put("/{job_id}/cancellation", operation_id="cancelJob")
async def cancel_job(job_id: ResourceId, services: Deps) -> JobOut:
    """Ask a running job to stop. It stops at the next move boundary and can be resumed."""
    return JobOut.of(await services.jobs.cancel(job_id))
