from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from duckgambit.api.deps import Services
from duckgambit.api.schemas.base import ID_PATTERN
from duckgambit.api.schemas.ducks import (
    ActiveDuckIn,
    DuckFile,
    DuckOut,
    HatchRequest,
    ProfileOut,
)
from duckgambit.domain.duck import Duck

router = APIRouter(prefix="/ducks", tags=["ducks"])
profile = APIRouter(prefix="/profile", tags=["profile"])

DuckId = Annotated[str, Path(pattern=ID_PATTERN)]
Deps = Annotated[Services, Depends()]


async def _out(services: Services, duck: Duck) -> DuckOut:
    return DuckOut.of(duck, await services.ducks.headline(duck.id), services.ducks.balance)


@router.post("", status_code=201, operation_id="hatchDuck")
async def hatch_duck(body: HatchRequest, services: Deps) -> DuckOut:
    """Hatch a level-1 duck. Emits DuckHatched on the duck's stream.

    With `eggSeed`, the starting stats are derived from the egg. Hatching never replaces a duck.
    """
    duck = await services.ducks.hatch(
        body.name,
        body.avatar.to_domain() if body.avatar else None,
        body.stats.model_dump() if body.stats else None,
        body.egg_seed,
    )
    return await _out(services, duck)


@router.get("", operation_id="listDucks")
async def list_ducks(services: Deps) -> list[DuckOut]:
    return [await _out(services, duck) for duck in await services.ducks.all()]


@router.get("/{duck_id}", operation_id="getDuck")
async def get_duck(duck_id: DuckId, services: Deps) -> DuckOut:
    return await _out(services, await services.ducks.get(duck_id))


@router.get("/{duck_id}/export", operation_id="exportDuck", response_model=DuckFile)
async def export_duck(duck_id: DuckId, services: Deps) -> JSONResponse:
    """The duck as a portable, versioned duck file."""
    data = await services.ducks.export(duck_id)
    filename = f"{duck_id}.duck.json"
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@profile.get("", operation_id="getProfile")
async def get_profile(services: Deps) -> ProfileOut:
    """The local player and the duck the hub shows."""
    return ProfileOut.of(await services.ducks.profile())


@profile.put("/active-duck", operation_id="setActiveDuck")
async def set_active_duck(body: ActiveDuckIn, services: Deps) -> ProfileOut:
    """Choose the duck the hub shows. Saved, so it survives a restart and is shared by clients."""
    return ProfileOut.of(await services.ducks.set_active(body.duck_id))


@router.post("/imports", status_code=201, operation_id="importDuck")
async def import_duck(body: DuckFile, services: Deps) -> DuckOut:
    """Add a duck from a duck file. The file is validated; stats must fit the level's budget."""
    duck = await services.ducks.import_file(body.model_dump(by_alias=True))
    return await _out(services, duck)
