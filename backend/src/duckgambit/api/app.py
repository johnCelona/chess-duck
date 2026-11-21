import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, Any

import chess
from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware

from duckgambit.adapters.engines.uci import UciEngine
from duckgambit.adapters.engines.installer import (
    install_engine,
    installed_state,
    load_manifest,
    remove_engine,
)
from duckgambit.api.schemas import AnalyseRequest, SettingsPayload
from duckgambit.adapters.profile_files import list_profiles, save_profile
from duckgambit.services.engine_options import advertised_limit, validate_limit


ENGINE_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"


def known_engine_id(
    engine_id: Annotated[str, Path(pattern=ENGINE_ID_PATTERN)],
) -> str:
    """Only ids from the committed manifest may reach the filesystem."""
    if not any(item["id"] == engine_id for item in load_manifest()["engines"]):
        raise HTTPException(status_code=404, detail="Unknown engine")
    return engine_id


EngineId = Annotated[str, Depends(known_engine_id)]

engines: dict[str, UciEngine] = {}
engine_settings: dict[str, SettingsPayload] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await asyncio.gather(*(engine.stop() for engine in engines.values()))


app = FastAPI(title="Duck Gambit Engine API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/engines")
async def list_engines() -> list[dict[str, Any]]:
    result = []
    for engine in load_manifest()["engines"]:
        state = installed_state(engine["id"])
        result.append(
            {
                **engine,
                "status": "installed" if state else "not_installed",
                "installed": state,
            }
        )
    return result


@app.post("/api/engines/{engine_id}/install")
async def install(engine_id: EngineId) -> dict:
    try:
        return await install_engine(engine_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/engines/{engine_id}")
async def remove(engine_id: EngineId) -> dict:
    remove_engine(engine_id)
    engine = engines.pop(engine_id, None)
    if engine:
        await engine.stop()
    engine_settings.pop(engine_id, None)
    return {"status": "removed"}


def get_installed_engine(engine_id: EngineId) -> UciEngine:
    state = installed_state(engine_id)
    if not state:
        raise HTTPException(status_code=409, detail="Engine is not installed")
    engine = engines.get(engine_id)
    if engine is None:
        engine = UciEngine(state["binary"])
        engines[engine_id] = engine
    return engine


@app.get("/api/engines/{engine_id}/options")
async def engine_options(engine_id: EngineId) -> dict:
    engine = get_installed_engine(engine_id)
    try:
        return {"options": await engine.options()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Engine handshake failed: {exc}") from exc


@app.get("/api/engines/{engine_id}/settings")
async def get_settings(engine_id: EngineId) -> dict:
    settings = engine_settings.get(
        engine_id,
        SettingsPayload(limit={"type": "nodes", "value": 100_000}, multipv=3),
    )
    return settings.model_dump()


@app.put("/api/engines/{engine_id}/settings")
async def put_settings(engine_id: EngineId, payload: SettingsPayload) -> dict:
    engine = get_installed_engine(engine_id)
    advertised = await engine.options()
    validated: dict[str, object] = {}
    try:
        for name, value in payload.options.items():
            validated[name] = advertised_limit(name, value, advertised)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await engine.configure(validated)
    engine_settings[engine_id] = payload.model_copy(update={"options": validated})
    return engine_settings[engine_id].model_dump()


@app.post("/api/engines/{engine_id}/analyse")
async def analyse(engine_id: EngineId, payload: AnalyseRequest) -> dict:
    engine = get_installed_engine(engine_id)
    advertised = await engine.options()
    overrides: dict[str, object] = {}
    try:
        for name, value in payload.overrides.items():
            overrides[name] = advertised_limit(name, value, advertised)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        chess.Board(payload.fen)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {exc}") from exc

    try:
        limit = validate_limit(payload.limit.type, payload.limit.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if overrides:
        await engine.configure(overrides)
    candidates = await engine.analyse(payload.fen, limit, payload.multipv)
    return {"candidates": candidates}


@app.post("/api/engines/{engine_id}/test")
async def test_engine(engine_id: EngineId) -> dict:
    request = AnalyseRequest(
        fen=chess.STARTING_FEN,
        limit={"type": "nodes", "value": 100_000},
        multipv=3,
    )
    result = await analyse(engine_id, request)
    return {"status": "ok", **result}


@app.get("/api/engines/{engine_id}/profiles")
async def profiles(engine_id: EngineId) -> dict:
    return {"profiles": list_profiles(engine_id)}


@app.post("/api/engines/{engine_id}/profiles")
async def create_profile(engine_id: EngineId, payload: dict) -> dict:
    try:
        name = payload["name"]
        settings = SettingsPayload(**payload["settings"])
        return {"profile": save_profile(engine_id, name, settings.model_dump())}
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
