"""The composition root: builds adapters and services from settings (ADR-0001)."""

from __future__ import annotations

from dataclasses import dataclass

from duckgambit.adapters.engines.admin import CatalogEngineAdmin
from duckgambit.adapters.engines.catalog import EngineCatalog
from duckgambit.adapters.engines.fake import FakeEngineAdmin, FakeEnginePool
from duckgambit.adapters.engines.installer import EngineInstaller
from duckgambit.adapters.engines.pool import ProcessEnginePool, catalog_locator
from duckgambit.adapters.sqlite.store import SqliteStore
from duckgambit.adapters.system import DataPaths, SystemClock, UuidIds
from duckgambit.domain.arena import ArenaCaps
from duckgambit.services.ducks import DuckService, ensure_challengers
from duckgambit.services.engines import EngineAdmin, EngineService
from duckgambit.services.events import EventLog, iso
from duckgambit.services.jobs import JobRunner
from duckgambit.services.matches import MatchService
from duckgambit.services.ports import Clock, EnginePool, IdGenerator
from duckgambit.settings import Settings


@dataclass
class Container:
    settings: Settings
    paths: DataPaths
    store: SqliteStore
    clock: Clock
    events: EventLog
    jobs: JobRunner
    pool: EnginePool
    ducks: DuckService
    matches: MatchService
    engines: EngineService

    async def startup(self) -> None:
        await self.jobs.recover()

    async def shutdown(self) -> None:
        self.events.close()
        await self.jobs.shutdown()
        await self.pool.close()
        self.store.close()


def build_container(
    settings: Settings,
    *,
    pool: EnginePool | None = None,
    admin: EngineAdmin | None = None,
    clock: Clock | None = None,
    ids: IdGenerator | None = None,
) -> Container:
    clock = clock or SystemClock()
    ids = ids or UuidIds()
    paths = DataPaths(settings.resolved_data_dir)
    paths.prepare()

    store = SqliteStore(paths.database)
    now = iso(clock)
    store.migrate(now)
    profile_id = store.profiles.ensure_default(now)
    ensure_challengers(store, now)

    caps = ArenaCaps()
    if settings.fake_engine:
        pool = pool or FakeEnginePool()
        admin = admin or FakeEngineAdmin()
    if pool is None or admin is None:
        catalog = EngineCatalog(paths)
        pool = pool or ProcessEnginePool(
            catalog_locator(catalog),
            max_engines=settings.engine_budget,
            max_hash_mb_total=settings.max_hash_mb_total,
            max_nodes=caps.max_nodes,
        )
        admin = admin or CatalogEngineAdmin(catalog, EngineInstaller(catalog, paths))

    events = EventLog(store, clock)
    jobs = JobRunner(store, events, clock, ids)
    return Container(
        settings=settings,
        paths=paths,
        store=store,
        clock=clock,
        events=events,
        jobs=jobs,
        pool=pool,
        ducks=DuckService(store, events, clock, ids, profile_id),
        matches=MatchService(store, events, jobs, pool, clock, ids, profile_id, caps=caps),
        engines=EngineService(admin, pool, store, clock),
    )
