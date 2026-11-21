"""The engine pool: exclusive leases under a process and memory budget (ADR-0007).

One lease is one process used by one caller, so two searches can never interfere.
The number of live processes and their total hash memory are capped.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from duckgambit.adapters.engines.catalog import EngineCatalog
from duckgambit.adapters.engines.uci import EngineLoop, UciEngine, default_deadline
from duckgambit.domain.engine_types import EngineIdentity
from duckgambit.services.ports import Engine, EngineError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Launch:
    command: list[str]
    cwd: Path
    identity: EngineIdentity


Locator = Callable[[str], Launch | None]


def catalog_locator(catalog: EngineCatalog) -> Locator:
    def locate(engine_id: str) -> Launch | None:
        entry = catalog.entry(engine_id)
        installed = catalog.installed(engine_id)
        if entry is None or installed is None:
            return None
        identity = EngineIdentity(
            entry.id, entry.name, installed.version, installed.binary_sha256[:16]
        )
        return Launch(installed.command, installed.binary.parent, identity)

    return locate


class ProcessEnginePool:
    def __init__(
        self,
        locate: Locator,
        max_engines: int,
        max_hash_mb_total: int,
        max_nodes: int,
        deadline: Any = default_deadline,
    ) -> None:
        self._locate = locate
        self._max_engines = max_engines
        self._hash_cap = max(1, max_hash_mb_total // max_engines)
        self._max_nodes = max_nodes
        self._deadline = deadline
        self._io = EngineLoop()
        self._slots = asyncio.Semaphore(max_engines)
        self._idle: dict[tuple[str, int], list[UciEngine]] = {}
        self._leased = 0
        self._closing = False

    @property
    def live_processes(self) -> int:
        return self._leased + sum(len(engines) for engines in self._idle.values())

    async def identity(self, engine_id: str) -> EngineIdentity | None:
        launch = self._locate(engine_id)
        return launch.identity if launch else None

    @asynccontextmanager
    async def lease(self, engine_id: str, hash_mb: int = 16) -> AsyncIterator[Engine]:
        launch = self._locate(engine_id)
        if launch is None:
            raise EngineError("engine.not_installed", "The engine is not installed")
        hash_mb = max(1, min(hash_mb, self._hash_cap))
        key = (engine_id, hash_mb)
        async with self._slots:
            engine = self._take_idle(key)
            if engine is None:
                while self.live_processes >= self._max_engines and await self._close_one_idle():
                    pass
                engine = UciEngine(
                    launch.command,
                    launch.cwd,
                    self._io,
                    {"Threads": 1, "Hash": hash_mb, "UCI_ShowWDL": True},
                    self._max_nodes,
                    self._deadline,
                )
                await engine.start()
            self._leased += 1
            try:
                yield engine
            finally:
                self._leased -= 1
                if engine.alive and not self._closing:
                    self._idle.setdefault(key, []).append(engine)
                else:
                    await engine.close()

    def _take_idle(self, key: tuple[str, int]) -> UciEngine | None:
        engines = self._idle.get(key, [])
        while engines:
            engine = engines.pop()
            if engine.alive:
                return engine
        return None

    async def _close_one_idle(self) -> bool:
        for engines in self._idle.values():
            if engines:
                await engines.pop().close()
                return True
        return False

    async def release_engine(self, engine_id: str) -> None:
        for key in [key for key in self._idle if key[0] == engine_id]:
            for engine in self._idle.pop(key):
                await engine.close()

    async def close(self) -> None:
        self._closing = True
        for engines in self._idle.values():
            for engine in engines:
                await engine.close()
        self._idle.clear()
        await asyncio.to_thread(self._io.stop)
