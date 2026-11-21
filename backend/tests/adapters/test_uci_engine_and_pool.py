"""The real UCI adapter and pool, driven against a fake UCI process. No Stockfish needed."""

import asyncio
import sys
from pathlib import Path

import chess
import pytest

from duckgambit.adapters.engines.fake import FakeEngine
from duckgambit.adapters.engines.pool import Launch, ProcessEnginePool
from duckgambit.domain.engine_types import EngineIdentity, SearchRequest
from duckgambit.services.ports import EngineError

pytestmark = pytest.mark.anyio

FAKE_UCI = Path(__file__).resolve().parents[1] / "fakes" / "fake_uci.py"
START = chess.STARTING_FEN


def request(moves=(), nodes=1000, multipv=3) -> SearchRequest:
    return SearchRequest(START, tuple(moves), multipv=multipv, nodes=nodes)


@pytest.fixture
async def make_pool(monkeypatch, tmp_path):
    pools = []

    def factory(mode="normal", max_engines=2, deadline=lambda _request: 20.0, installed=True):
        monkeypatch.setenv("FAKE_UCI_MODE", mode)
        monkeypatch.setenv("FAKE_UCI_LOG", str(tmp_path / "uci.log"))
        launch = Launch(
            [sys.executable, str(FAKE_UCI)],
            FAKE_UCI.parent,
            EngineIdentity("fake-uci", "Fake UCI", "1", "0123456789abcdef"),
        )
        pool = ProcessEnginePool(
            lambda engine_id: launch if installed and engine_id == "fake-uci" else None,
            max_engines=max_engines,
            max_hash_mb_total=64,
            max_nodes=1_000_000,
            deadline=deadline,
        )
        pools.append(pool)
        return pool

    yield factory
    for pool in pools:
        await pool.close()


def commands(tmp_path) -> list[str]:
    return (tmp_path / "uci.log").read_text(encoding="utf-8").splitlines()


async def test_search_returns_candidates_best_first_with_scores_and_wdl(make_pool):
    pool = make_pool()

    async with pool.lease("fake-uci") as engine:
        result = await engine.search(request(moves=("e2e4",)))

    expected = await FakeEngine().search(request(moves=("e2e4",)))
    assert [c.move for c in result.candidates] == [c.move for c in expected.candidates]
    assert [c.cp for c in result.candidates] == [c.cp for c in expected.candidates]
    assert result.candidates[0].wdl == expected.candidates[0].wdl
    assert result.depth == 1
    assert result.nodes == 1017


async def test_every_search_resets_the_engine_first(make_pool, tmp_path):
    pool = make_pool()

    async with pool.lease("fake-uci") as engine:
        await engine.search(request())
        await engine.search(request(moves=("e2e4",)))

    sent = commands(tmp_path)
    assert sent.count("ucinewgame") == 2
    assert sent.index("ucinewgame") < next(i for i, c in enumerate(sent) if c.startswith("go"))
    assert "position startpos moves e2e4" in sent or any(
        c.startswith("position fen") and c.endswith("moves e2e4") for c in sent
    )


async def test_engine_is_configured_single_threaded_with_wdl(make_pool, tmp_path):
    pool = make_pool()

    async with pool.lease("fake-uci", hash_mb=32) as engine:
        await engine.search(request())

    sent = commands(tmp_path)
    # Threads is already 1 by default, so python-chess sends nothing for it.
    assert not any(c.startswith("setoption name Threads") and not c.endswith(" 1") for c in sent)
    assert "setoption name Hash value 32" in sent
    assert "setoption name UCI_ShowWDL value true" in sent
    assert not any("Debug Log File" in c or "SyzygyPath" in c for c in sent)


async def test_hash_is_capped_by_the_pool_budget(make_pool, tmp_path):
    pool = make_pool(max_engines=2)

    async with pool.lease("fake-uci", hash_mb=10_000) as engine:
        await engine.search(request())

    assert "setoption name Hash value 32" in commands(tmp_path)


async def test_only_lines_from_the_last_complete_depth_are_used(make_pool):
    pool = make_pool(mode="partial-depth")

    async with pool.lease("fake-uci") as engine:
        result = await engine.search(request())

    expected = await FakeEngine().search(request())
    assert result.depth == 1
    assert [c.move for c in result.candidates] == [c.move for c in expected.candidates]


async def test_a_hung_engine_is_killed_and_reported(make_pool):
    pool = make_pool(mode="hang", deadline=lambda _request: 0.5)

    async with pool.lease("fake-uci") as engine:
        with pytest.raises(EngineError) as error:
            await engine.search(request())
        assert not engine.alive

    assert error.value.code == "engine.timeout"
    assert pool.live_processes == 0


async def test_a_crashed_engine_is_reported_and_replaced_on_the_next_lease(make_pool, monkeypatch):
    pool = make_pool(mode="crash")

    async with pool.lease("fake-uci") as engine:
        with pytest.raises(EngineError) as error:
            await engine.search(request())
    assert error.value.code == "engine.failed"

    monkeypatch.setenv("FAKE_UCI_MODE", "normal")
    async with pool.lease("fake-uci") as engine:
        assert (await engine.search(request())).candidates


async def test_cancelling_a_search_kills_the_engine(make_pool):
    pool = make_pool(mode="hang")

    async with pool.lease("fake-uci") as engine:
        task = asyncio.ensure_future(engine.search(request()))
        await asyncio.sleep(0.3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not engine.alive


async def test_an_engine_that_never_answers_uci_fails_to_start(make_pool, monkeypatch):
    import duckgambit.adapters.engines.uci as uci

    monkeypatch.setattr(uci, "START_TIMEOUT_S", 0.5)
    pool = make_pool(mode="no-handshake")

    with pytest.raises(EngineError) as error:
        async with pool.lease("fake-uci"):
            pass

    assert error.value.code == "engine.start_failed"


async def test_malformed_requests_never_reach_the_engine(make_pool, tmp_path):
    pool = make_pool()

    async with pool.lease("fake-uci") as engine:
        for bad in (
            request(nodes=0),
            request(nodes=10**9),
            request(multipv=99),
            request(moves=("e2e4; quit",)),
            request(moves=("e2e5",)),
        ):
            with pytest.raises(EngineError):
                await engine.search(bad)
        assert engine.alive

    assert not any(c.startswith("go") for c in commands(tmp_path))


async def test_leases_are_exclusive_and_bounded_by_the_budget(make_pool):
    pool = make_pool(max_engines=1)
    order = []

    async def use(name):
        async with pool.lease("fake-uci") as engine:
            order.append(f"{name} in")
            assert pool.live_processes == 1
            await engine.search(request())
            await asyncio.sleep(0.05)
            order.append(f"{name} out")

    await asyncio.gather(use("a"), use("b"))

    assert order in (["a in", "a out", "b in", "b out"], ["b in", "b out", "a in", "a out"])


async def test_idle_processes_are_reused_and_released_on_request(make_pool, tmp_path):
    pool = make_pool()

    async with pool.lease("fake-uci") as first:
        await first.search(request())
    async with pool.lease("fake-uci") as second:
        await second.search(request())

    assert second is first
    assert commands(tmp_path).count("uci") == 1
    await pool.release_engine("fake-uci")
    assert pool.live_processes == 0


async def test_leasing_an_engine_that_is_not_installed_is_an_error(make_pool):
    pool = make_pool(installed=False)

    with pytest.raises(EngineError) as error:
        async with pool.lease("fake-uci"):
            pass

    assert error.value.code == "engine.not_installed"
    assert await pool.identity("fake-uci") is None


async def test_describe_reports_advertised_options(make_pool):
    pool = make_pool()

    async with pool.lease("fake-uci") as engine:
        info = await engine.describe()

    assert info.name == "Fake UCI 1"
    assert {"Threads", "Hash", "Debug Log File"} <= {option.name for option in info.options}
