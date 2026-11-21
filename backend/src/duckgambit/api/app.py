"""The FastAPI application: a thin layer over the services (ADR-0001, ADR-0002)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from duckgambit import __version__
from duckgambit.api.container import Container, build_container
from duckgambit.api.deps import Services
from duckgambit.api.errors import PROBLEM_RESPONSES, install_error_handlers
from duckgambit.api.routers import ducks, engines, events, matches
from duckgambit.api.schemas.matches import HealthOut
from duckgambit.api.security import LOOPBACK_HOSTS, BoundaryMiddleware
from duckgambit.logging_setup import configure_logging
from duckgambit.settings import Settings

API_PREFIX = "/api/v1"
log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or (container.settings if container else Settings())
    # The server may run in a child process (reload), so logging is set up here too.
    configure_logging(settings.log_level, settings.log_format)
    if settings.host not in LOOPBACK_HOSTS and settings.host != "::1" and not settings.api_token:
        raise RuntimeError(
            "Refusing to listen on a non-loopback address without DG_API_TOKEN (ADR-0011)"
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        built = container or build_container(settings)
        app.state.container = built
        await built.startup()
        log.info("Duck Gambit %s ready; data in %s", __version__, built.paths.root)
        try:
            yield
        finally:
            await built.shutdown()
            log.info("Duck Gambit stopped")

    app = FastAPI(
        title="Duck Gambit API",
        version=__version__,
        description=(
            "Versioned API for every Duck Gambit client. Clients render events and call this "
            "API; they contain no chess rules, scoring or rating logic."
        ),
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    install_error_handlers(app)

    v1 = APIRouter(prefix=API_PREFIX, responses=PROBLEM_RESPONSES)

    @v1.get("/health", tags=["system"], operation_id="getHealth")
    async def health(services: Annotated[Services, Depends()]) -> HealthOut:
        """Liveness and version check. A launcher waits for this before showing the game."""
        built = services.container
        return HealthOut(
            status="ok",
            version=__version__,
            api_version="v1",
            schema_version=built.store.database.schema_version(),
            engine_budget=built.settings.engine_budget,
            fake_engine=built.settings.fake_engine,
            lichess_enabled=built.settings.lichess_enabled,
        )

    v1.include_router(engines.router)
    v1.include_router(ducks.router)
    v1.include_router(ducks.profile)
    v1.include_router(ducks.challengers)
    v1.include_router(matches.matches)
    v1.include_router(matches.games)
    v1.include_router(matches.jobs)
    v1.include_router(events.router)
    app.include_router(v1)

    if settings.origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.origins),
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["content-type", "authorization", "last-event-id"],
        )
    app.add_middleware(BoundaryMiddleware, settings=settings)
    return app
