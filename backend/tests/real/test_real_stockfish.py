"""Checks against a real, installed Stockfish. Skipped when none is installed; never run in CI.

Run after installing the engine from the Engines page:
    uv run --project backend pytest backend/tests/real

The engine is looked up in DG_DATA_DIR, or in ./data at the repository root.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import chess
import pytest

from conftest import NOW, CountingIds, FixedClock
from duckgambit.adapters.engines.catalog import EngineCatalog
from duckgambit.adapters.engines.pool import ProcessEnginePool, catalog_locator
from duckgambit.adapters.sqlite.store import DEFAULT_PROFILE_ID, SqliteStore
from duckgambit.adapters.system import DataPaths
from duckgambit.domain.arena import Arena, EngineSettings, VirtualClockLimit
from duckgambit.domain.engine_types import SearchRequest
from duckgambit.services.ducks import DuckService
from duckgambit.services.events import EventLog
from duckgambit.services.jobs import JobRunner
from duckgambit.services.matches import MatchService

pytestmark = [pytest.mark.real_engine, pytest.mark.anyio]

REPO = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("DG_DATA_DIR", REPO / "data"))
CATALOG = EngineCatalog(DataPaths(DATA_DIR))
INSTALLED = CATALOG.installed("stockfish")

if INSTALLED is None:
    pytestmark.append(pytest.mark.skip(reason="Stockfish is not installed in the data directory"))

SICILIAN = ("e2e4", "c7c5", "g1f3", "d7d6")

# What Stockfish 19 returns for the Sicilian position above at 20,000 nodes, MultiPV 3,
# Hash 16, one thread. Search is deterministic for a given engine version, so any change
# here means the binary changed or the adapter picks lines differently: ratings measured
# before and after are then not comparable (ADR-0006). The same values are expected on
# every platform's official build; if a platform differs, record that as a finding.
EXPECTED_SICILIAN = [("d2d4", 23), ("b1c3", 23), ("f1c4", 19)]  # all from depth 9


def request(moves=SICILIAN, nodes=20_000, multipv=3) -> SearchRequest:
    return SearchRequest(chess.STARTING_FEN, tuple(moves), multipv=multipv, nodes=nodes)


@pytest.fixture
async def pool():
    engine_pool = ProcessEnginePool(
        catalog_locator(CATALOG), max_engines=2, max_hash_mb_total=64, max_nodes=5_000_000
    )
    yield engine_pool
    await engine_pool.close()


async def test_the_installed_engine_identifies_itself(pool):
    identity = await pool.identity("stockfish")

    async with pool.lease("stockfish") as engine:
        info = await engine.describe()

    assert info.name.startswith("Stockfish 19")
    assert identity.version == "19"
    assert len(identity.fingerprint) == 16
    options = {option.name: option for option in info.options}
    assert options["UCI_Elo"].min == 1320
    assert {"Debug Log File", "EvalFile", "SyzygyPath"} <= set(options)


async def test_a_known_search_matches_the_committed_expectation(pool):
    async with pool.lease("stockfish") as engine:
        result = await engine.search(request())

    assert [(c.move, c.cp) for c in result.candidates] == EXPECTED_SICILIAN
    assert len({c.depth for c in result.candidates}) == 1
    assert 20_000 <= result.nodes < 21_000
    assert all(c.wdl is not None and sum(c.wdl) == 1000 for c in result.candidates)


async def test_a_warm_engine_answers_exactly_like_a_fresh_one(pool):
    async with pool.lease("stockfish") as engine:
        fresh = await engine.search(request())
        await engine.search(request(moves=("d2d4", "g8f6"), nodes=50_000, multipv=5))
        warm = await engine.search(request())

    assert warm == fresh


async def test_a_real_bullet_game_replays_identically(pool, tmp_path):
    arena = Arena(
        EngineSettings("stockfish"),
        VirtualClockLimit(60_000, 0, 50_000),
        seed=42,
        max_plies=40,
    )

    async def play(name: str) -> tuple[str, list[int], list[list[str]]]:
        store = SqliteStore(tmp_path / f"{name}.db")
        store.migrate(NOW)
        store.profiles.ensure_default(NOW)
        clock, ids = FixedClock(), CountingIds()
        events = EventLog(store, clock)
        jobs = JobRunner(store, events, clock, ids)
        ducks = DuckService(store, events, clock, ids, DEFAULT_PROFILE_ID)
        matches = MatchService(store, events, jobs, pool, clock, ids, DEFAULT_PROFILE_ID)
        first = await ducks.hatch("Bold")
        second = await ducks.hatch("Calm")
        match = await matches.create((first.id, second.id), replace(arena))
        job = await jobs.wait(match.job_id)
        assert job.state == "succeeded", job
        game = (await matches.games(match.id))[0]
        nodes = [move.nodes for move in await matches.moves(game.id)]
        envelopes = await events.read([f"match:{match.id}"], 0, 500)
        considered = [
            [candidate["move"] for candidate in envelope.data["candidates"]]
            for envelope in envelopes
            if envelope.type == "MoveChosen"
        ]
        store.close()
        return game.pgn, nodes, considered

    first_pgn, first_nodes, considered = await play("first")
    second_pgn, second_nodes, _ = await play("second")

    assert first_pgn == second_pgn
    assert first_nodes == second_nodes
    assert len(first_nodes) == 40
    # Regression: a move must never appear on two lines of the same decision.
    assert all(len(moves) == len(set(moves)) for moves in considered)
