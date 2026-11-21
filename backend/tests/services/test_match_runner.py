"""The match runner end to end at the service level, on the in-process fake engine."""

from contextlib import asynccontextmanager
from dataclasses import replace

import pytest

from conftest import CountingIds, FixedClock
from duckgambit.adapters.engines.fake import FakeEngine, FakeEnginePool
from duckgambit.adapters.sqlite.store import DEFAULT_PROFILE_ID
from duckgambit.domain.arena import Arena, EngineSettings, NodesLimit, VirtualClockLimit
from duckgambit.domain.balance import DEFAULT_BALANCE, ClockPolicy
from duckgambit.domain.duck import default_stats
from duckgambit.domain.errors import DomainError
from duckgambit.services.ducks import DuckService, duck_stream
from duckgambit.services.errors import ServiceError
from duckgambit.services.events import EventLog
from duckgambit.services.jobs import JobRunner
from duckgambit.services.matches import MatchService, match_stream

pytestmark = pytest.mark.anyio

NODES = Arena(EngineSettings("fake"), NodesLimit(1_000), seed=11, games=2, max_plies=30)
BULLET = Arena(
    EngineSettings("fake"), VirtualClockLimit(60_000, 0, 200_000), seed=11, games=1, max_plies=30
)


class Harness:
    def __init__(self, store, pool=None, balance=DEFAULT_BALANCE):
        self.store = store
        self.clock = FixedClock()
        self.ids = CountingIds()
        self.events = EventLog(store, self.clock)
        self.jobs = JobRunner(store, self.events, self.clock, self.ids)
        self.pool = pool or FakeEnginePool()
        self.ducks = DuckService(store, self.events, self.clock, self.ids, DEFAULT_PROFILE_ID)
        self.matches = MatchService(
            store,
            self.events,
            self.jobs,
            self.pool,
            self.clock,
            self.ids,
            DEFAULT_PROFILE_ID,
            balance=balance,
        )

    async def two_ducks(self):
        bold = await self.ducks.hatch(
            "Bold", stats={**default_stats(), "aggression": 60, "solidity": 20}
        )
        calm = await self.ducks.hatch(
            "Calm", stats={**default_stats(), "creativity": 10, "speed": 60}
        )
        return bold, calm

    async def play(self, arena, rated=True):
        bold, calm = await self.two_ducks()
        match = await self.matches.create((bold.id, calm.id), arena, rated)
        job = await self.jobs.wait(match.job_id)
        return await self.matches.get(match.id), job

    async def pgns(self, match_id):
        return [game.pgn for game in await self.matches.games(match_id)]

    async def types(self, stream):
        return [e.type for e in await self.events.read([stream], 0, 500)]


@pytest.fixture
def harness(store):
    return Harness(store)


def fresh_harness(tmp_path, name, pool=None):
    from conftest import NOW
    from duckgambit.adapters.sqlite.store import SqliteStore

    other = SqliteStore(tmp_path / f"{name}.db")
    other.migrate(NOW)
    other.profiles.ensure_default(NOW)
    return Harness(other, pool)


async def test_a_match_plays_to_the_end_and_records_everything(harness):
    match, job = await harness.play(NODES)

    assert (match.state, job.state, job.done, job.total) == ("finished", "succeeded", 2, 2)
    games = await harness.matches.games(match.id)
    assert [g.state for g in games] == ["finished", "finished"]
    assert games[0].white_duck_id == games[1].black_duck_id  # colours swap
    assert sum(match.scores.values()) == 2.0
    moves = await harness.matches.moves(games[0].id)
    assert [m.ply for m in moves] == list(range(1, len(moves) + 1))
    assert games[0].pgn.count("[%eval") == len(moves)


async def test_the_event_stream_tells_the_whole_story_in_order(harness):
    match, _ = await harness.play(replace(NODES, games=1))

    types = await harness.types(match_stream(match.id))

    assert types[:3] == ["MatchCreated", "MatchStarted", "GameStarted"]
    assert types[-2:] == ["GameFinished", "MatchFinished"]
    body = types[3:-2]
    assert body[0::2] == ["MoveChosen"] * (len(body) // 2)
    assert body[1::2] == ["MoveMade"] * (len(body) // 2)
    envelopes = await harness.events.read([match_stream(match.id)], 0, 500)
    assert [e.seq for e in envelopes] == list(range(1, len(envelopes) + 1))
    chosen = envelopes[3].data
    assert chosen["candidates"] and chosen["reasons"]
    assert {"move", "san", "rank", "final_score", "probability_ppm"} <= set(chosen["candidates"][0])
    made = envelopes[4].data
    assert made["fen_after"] and made["by"] == "duck"


async def test_the_same_seed_replays_the_same_games_and_another_seed_does_not(harness, tmp_path):
    match, _ = await harness.play(NODES)
    again = fresh_harness(tmp_path, "again")
    same, _ = await again.play(NODES)
    other = fresh_harness(tmp_path, "other")
    different, _ = await other.play(replace(NODES, seed=12))

    assert await again.pgns(same.id) == await harness.pgns(match.id)
    assert await other.pgns(different.id) != await harness.pgns(match.id)


class CancellingPool(FakeEnginePool):
    """Requests a cancel from inside the Nth search, the way a user would mid-game."""

    def __init__(self, after):
        super().__init__()
        self.after = after
        self.count = 0
        self.cancel = None

    @asynccontextmanager
    async def lease(self, engine_id, hash_mb=16):
        pool = self

        class Engine(FakeEngine):
            async def search(self, request):
                pool.count += 1
                if pool.count == pool.after and pool.cancel is not None:
                    await pool.cancel()
                return await super().search(request)

        yield Engine()


async def test_a_cancelled_match_resumes_and_ends_identically_to_an_uninterrupted_one(
    harness, tmp_path
):
    straight, _ = await harness.play(NODES)

    pool = CancellingPool(after=7)
    interrupted = fresh_harness(tmp_path, "interrupted", pool)
    bold, calm = await interrupted.two_ducks()
    match = await interrupted.matches.create((bold.id, calm.id), NODES)
    pool.cancel = lambda: interrupted.jobs.cancel(match.job_id)
    job = await interrupted.jobs.wait(match.job_id)

    assert job.state == "cancelled"
    assert (await interrupted.matches.get(match.id)).state == "cancelled"
    partial = await interrupted.matches.games(match.id)
    assert partial[0].state == "running"
    assert 0 < len(await interrupted.matches.moves(partial[0].id)) < 30

    pool.cancel = None
    await interrupted.matches.resume(match.id)
    job = await interrupted.jobs.wait(match.job_id)

    assert job.state == "succeeded"
    assert await interrupted.pgns(match.id) == await harness.pgns(straight.id)
    seqs = [e.seq for e in await interrupted.events.read([match_stream(match.id)], 0, 500)]
    assert seqs == list(range(1, len(seqs) + 1))
    assert (await interrupted.types(match_stream(match.id))).count("MatchStarted") == 1


async def test_a_job_interrupted_by_shutdown_is_marked_and_can_be_resumed(harness, tmp_path):
    straight, _ = await harness.play(NODES)

    pool = CancellingPool(after=5)
    stopped = fresh_harness(tmp_path, "stopped", pool)
    bold, calm = await stopped.two_ducks()
    match = await stopped.matches.create((bold.id, calm.id), NODES)

    async def crash():
        raise_in = stopped.jobs._tasks[match.job_id]
        raise_in.cancel()

    pool.cancel = crash
    job = await stopped.jobs.wait(match.job_id)
    assert job.state == "interrupted"

    # A new process: recover() would mark stale jobs; here the state is already settled.
    pool.cancel = None
    await stopped.matches.resume(match.id)
    assert (await stopped.jobs.wait(match.job_id)).state == "succeeded"
    assert await stopped.pgns(match.id) == await harness.pgns(straight.id)


async def test_recover_marks_jobs_left_running_by_a_dead_process(harness):
    await harness.jobs.create("job_stale", "match", {}, 1)
    stale = await harness.jobs.get("job_stale")
    harness.store.jobs.save(replace(stale, state="running"))

    assert await harness.jobs.recover() == ["job_stale"]
    assert (await harness.jobs.get("job_stale")).state == "interrupted"


async def test_bullet_games_run_on_a_virtual_clock(harness):
    match, _ = await harness.play(BULLET)

    game = (await harness.matches.games(match.id))[0]
    moves = await harness.matches.moves(game.id)
    white_clocks = [m.clock_ms for m in moves if m.color == "white"]
    assert white_clocks == sorted(white_clocks, reverse=True)
    assert white_clocks[0] < 60_000
    assert all(m.think_ms > 0 for m in moves)
    assert '[TimeControl "60+0"]' in game.pgn
    assert "[%clk 0:00:5" in game.pgn


async def test_a_duck_that_runs_out_of_virtual_time_loses_on_time(store):
    # A policy that insists on 400 ms per move burns a one-second clock in three moves.
    harness = Harness(store, balance=replace(DEFAULT_BALANCE, clock=ClockPolicy(min_think_ms=400)))
    blitz = replace(BULLET, limit=VirtualClockLimit(1_000, 0, 200_000))

    match, job = await harness.play(blitz)

    game = (await harness.matches.games(match.id))[0]
    assert job.state == "succeeded"
    assert game.termination == "time_forfeit"
    assert game.result in {"1-0", "0-1"}
    assert '[Termination "Time forfeit"]' in game.pgn


async def test_calculation_changes_the_node_budget_unless_the_engine_is_equal(harness):
    strong = await harness.ducks.hatch(
        "Strong", stats={**default_stats(), "calculation": 60, "memory": 20}
    )
    weak = await harness.ducks.hatch("Weak", stats={**default_stats(), "calculation": 20})
    arena = replace(NODES, games=1)

    async def budgets(match_arena):
        match = await harness.matches.create((strong.id, weak.id), match_arena)
        await harness.jobs.wait(match.job_id)
        envelopes = await harness.events.read([match_stream(match.id)], 0, 500)
        chosen = [
            e.data for e in envelopes if e.type == "MoveChosen" and e.data["source"] == "engine"
        ]
        return {c["duck_id"]: c["nodes_budget"] for c in chosen}

    scaled = await budgets(arena)
    equal = await budgets(replace(arena, equal_engine=True))

    assert scaled[strong.id] > 1_000 > scaled[weak.id]
    assert equal[strong.id] == equal[weak.id] == 1_000


async def test_rated_games_update_both_ducks_ratings(harness):
    match, _ = await harness.play(NODES)

    for duck_id in match.duck_ids:
        records = await harness.ducks.ratings(duck_id)
        assert [(r.context_id, r.kind, r.rating.games) for r in records] == [
            (match.context_id, "game", 2)
        ]
        headline = await harness.ducks.headline(duck_id)
        assert headline.provisional
        assert headline.games == 2
        assert "RatingUpdated" in await harness.types(duck_stream(duck_id))


async def test_unrated_games_leave_ratings_alone_and_new_ducks_show_the_stub(harness):
    match, _ = await harness.play(NODES, rated=False)

    headline = await harness.ducks.headline(match.duck_ids[0])
    assert (headline.value, headline.games, headline.provisional, headline.context_id) == (
        1500.0,
        0,
        True,
        None,
    )


async def test_a_taught_opening_move_is_played_from_the_book(harness):
    import chess

    from duckgambit.domain.chessutil import position_key
    from duckgambit.domain.knowledge import Knowledge, RepertoireEntry

    bold, calm = await harness.two_ducks()
    taught = replace(
        bold.with_knowledge(
            Knowledge(repertoire=(RepertoireEntry("white", position_key(chess.Board()), "g1f3"),))
        ),
        id="duck_book",
        stats={**default_stats(), "memory": 60, "solidity": 20, "aggression": 20},
    )
    # memory 60 gives 80% recall; seed 11 game 0 recalls (checked by the assertion below)
    harness.store.ducks.add(taught)

    match = await harness.matches.create((taught.id, calm.id), replace(NODES, games=1, seed=3))
    await harness.jobs.wait(match.job_id)

    game = (await harness.matches.games(match.id))[0]
    first = (await harness.matches.moves(game.id))[0]
    assert (first.uci, first.source, first.nodes) == ("g1f3", "book", 0)
    assert "1. Nf3 { book }" in game.pgn


async def test_a_match_needs_two_different_existing_ducks_and_an_installed_engine(harness):
    bold, calm = await harness.two_ducks()

    with pytest.raises(ServiceError) as error:
        await harness.matches.create((bold.id, bold.id), NODES)
    assert error.value.code == "match.same_duck"

    with pytest.raises(ServiceError) as error:
        await harness.matches.create((bold.id, "duck_missing"), NODES)
    assert error.value.status == 404

    class NoEngine(FakeEnginePool):
        async def identity(self, engine_id):
            return None

    bare = Harness(harness.store, NoEngine())
    with pytest.raises(ServiceError) as error:
        await bare.matches.create((bold.id, calm.id), NODES)
    assert (error.value.code, error.value.status) == ("engine.not_installed", 409)


async def test_arena_settings_are_validated_before_anything_starts(harness):
    bold, calm = await harness.two_ducks()

    for bad in (
        replace(NODES, engine=EngineSettings("fake", threads=4)),
        replace(NODES, limit=NodesLimit(10**9)),
        replace(NODES, games=0),
        replace(NODES, seed=-1),
    ):
        with pytest.raises(DomainError):
            await harness.matches.create((bold.id, calm.id), bad)
    assert await harness.matches.recent() == []


async def test_a_finished_match_cannot_be_resumed(harness):
    match, _ = await harness.play(replace(NODES, games=1))

    with pytest.raises(ServiceError) as error:
        await harness.matches.resume(match.id)

    assert error.value.status == 409
