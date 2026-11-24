"""Runs of the minigame tests (ADR-0017). Kept in memory on purpose: nothing is stored
and no duck changes, so a test can be reshaped or thrown away without a migration."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from duckgambit.domain.minigames.base import Action, Info, Minigame, Snapshot
from duckgambit.domain.minigames.catalog import MINIGAMES, start
from duckgambit.domain.seeds import derive_seed
from duckgambit.services.errors import not_found
from duckgambit.services.ports import Clock, IdGenerator

MAX_RUNS = 50  # the oldest run is dropped beyond this


@dataclass
class Run:
    id: str
    game: Minigame
    last_ms: int


class MinigameService:
    def __init__(self, clock: Clock, ids: IdGenerator) -> None:
        self._clock = clock
        self._ids = ids
        self._runs: OrderedDict[str, Run] = OrderedDict()

    def all(self) -> list[Info]:
        return [game.info for game in MINIGAMES]

    def start(self, kind: str, seed: int | None, level: str = "") -> tuple[Run, Snapshot]:
        run_id = self._ids.new("mini")
        if seed is None:
            seed = derive_seed(0, run_id)
        run = Run(run_id, start(kind, seed, level), self._now_ms())
        self._runs[run_id] = run
        while len(self._runs) > MAX_RUNS:
            self._runs.popitem(last=False)
        return run, run.game.snapshot()

    def act(self, run_id: str, action: Action) -> tuple[Run, Snapshot]:
        run = self._runs.get(run_id)
        if run is None:
            raise not_found("minigame_run")
        # The player's time is measured here and handed to the domain as data (ADR-0015).
        now = self._now_ms()
        spent, run.last_ms = now - run.last_ms, now
        return run, run.game.act(action, spent)

    def _now_ms(self) -> int:
        return int(self._clock.now().timestamp() * 1000)
