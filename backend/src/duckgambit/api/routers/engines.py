from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from duckgambit.api.deps import Services
from duckgambit.api.schemas.base import ID_PATTERN
from duckgambit.api.schemas.engines import (
    AnalysisOut,
    AnalysisRequest,
    EngineOptionOut,
    EngineOut,
    EngineProfileBody,
    EngineProfileOut,
)

router = APIRouter(prefix="/engines", tags=["engines"])

EngineId = Annotated[str, Path(pattern=ID_PATTERN, description="An engine id from the manifest")]
Deps = Annotated[Services, Depends()]


@router.get("", operation_id="listEngines")
async def list_engines(services: Deps) -> list[EngineOut]:
    return [EngineOut.of(listing) for listing in services.engines.all()]


@router.put("/{engine_id}/installation", operation_id="installEngine")
async def install_engine(engine_id: EngineId, services: Deps) -> EngineOut:
    """Download the engine from the pinned manifest, verify it, smoke-test it, install it."""
    return EngineOut.of(await services.engines.install(engine_id))


@router.delete("/{engine_id}/installation", operation_id="removeEngine")
async def remove_engine(engine_id: EngineId, services: Deps) -> EngineOut:
    return EngineOut.of(await services.engines.remove(engine_id))


@router.get("/{engine_id}/options", operation_id="listEngineOptions")
async def engine_options(engine_id: EngineId, services: Deps) -> list[EngineOptionOut]:
    """What the engine advertises. Only options marked userSettable can be changed."""
    return [EngineOptionOut.of(option) for option in await services.engines.options(engine_id)]


@router.post("/{engine_id}/analyses", operation_id="analysePosition")
async def analyse(engine_id: EngineId, body: AnalysisRequest, services: Deps) -> AnalysisOut:
    """A diagnostic search ("Test engine"). Not used for anything that affects a result."""
    analysis = await services.engines.analyse(
        engine_id, body.fen, body.nodes, body.multi_pv, body.hash_mb
    )
    return AnalysisOut.of(analysis)


@router.get("/{engine_id}/profiles", operation_id="listEngineProfiles")
async def list_profiles(engine_id: EngineId, services: Deps) -> list[EngineProfileOut]:
    return [EngineProfileOut.of(p) for p in await services.engines.profiles(engine_id)]


@router.put("/{engine_id}/profiles", operation_id="saveEngineProfile")
async def save_profile(
    engine_id: EngineId, body: EngineProfileBody, services: Deps
) -> EngineProfileOut:
    """Create or replace the profile with this name."""
    return EngineProfileOut.of(await services.engines.save_profile(body.to_record(engine_id)))
