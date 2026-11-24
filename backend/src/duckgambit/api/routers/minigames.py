from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from duckgambit.api.deps import Services
from duckgambit.api.schemas.base import ID_PATTERN
from duckgambit.api.schemas.minigames import (
    MinigameActionIn,
    MinigameInfoOut,
    MinigameRunOut,
    StartMinigameRequest,
)
from duckgambit.domain.minigames.base import Action

minigames = APIRouter(prefix="/minigames", tags=["minigames (experimental)"])
runs = APIRouter(prefix="/minigame-runs", tags=["minigames (experimental)"])

RunId = Annotated[str, Path(pattern=ID_PATTERN)]
Deps = Annotated[Services, Depends()]


@minigames.get("", operation_id="listMinigames")
async def list_minigames(services: Deps) -> list[MinigameInfoOut]:
    """Every minigame test. Nothing in here changes a duck."""
    return [MinigameInfoOut.model_validate(info) for info in services.minigames.all()]


@runs.post("", status_code=201, operation_id="startMinigame")
async def start_minigame(body: StartMinigameRequest, services: Deps) -> MinigameRunOut:
    """Start a run. The same seed deals the same run."""
    return MinigameRunOut.of(*services.minigames.start(body.kind, body.seed))


@runs.post("/{run_id}/actions", operation_id="playMinigame")
async def play_minigame(run_id: RunId, body: MinigameActionIn, services: Deps) -> MinigameRunOut:
    """One thing the player did: a move, a choice, a hint, or going on to the next round."""
    return MinigameRunOut.of(*services.minigames.act(run_id, Action(body.type, body.value)))
