"""How routers reach the services. Routers stay thin: parse, call a service, shape the reply."""

from __future__ import annotations

from fastapi import Request

from duckgambit.api.container import Container
from duckgambit.services.ducks import DuckService
from duckgambit.services.engines import EngineService
from duckgambit.services.events import EventLog
from duckgambit.services.jobs import JobRunner
from duckgambit.services.matches import MatchService
from duckgambit.services.sparring import SparringService


class Services:
    """Request-scoped view of the container, injected with `Depends()`."""

    def __init__(self, request: Request) -> None:
        self.container: Container = request.app.state.container

    @property
    def ducks(self) -> DuckService:
        return self.container.ducks

    @property
    def matches(self) -> MatchService:
        return self.container.matches

    @property
    def sparring(self) -> SparringService:
        return self.container.sparring

    @property
    def engines(self) -> EngineService:
        return self.container.engines

    @property
    def jobs(self) -> JobRunner:
        return self.container.jobs

    @property
    def events(self) -> EventLog:
        return self.container.events
