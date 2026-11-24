"""Games against the player (ADR-0015) on the fake engine, with a clock the test drives."""

from datetime import UTC, datetime, timedelta

import chess
import pytest

from conftest import NOW, CountingIds
from duckgambit.adapters.engines.fake import FakeEnginePool
from duckgambit.adapters.sqlite.store import DEFAULT_PROFILE_ID, SqliteStore
from duckgambit.domain.balance import DEFAULT_BALANCE
from duckgambit.domain.clock import HUMAN_MOVE_FLOOR_MS, charge_human
from duckgambit.domain.game import timeout
from duckgambit.services.ducks import DuckService, duck_stream
from duckgambit.services.errors import ServiceError
from duckgambit.services.events import EventLog
from duckgambit.services.sparring import SparringService, series_stream, sparring_stream

pytestmark = pytest.mark.anyio


class ManualClock:
    """Stands still until the test moves it: elapsed time is exactly what a test says."""

    def __init__(self) -> None:
        self.moment = datetime(2026, 11, 21, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.moment

    def advance(self, ms: int) -> None:
        self.moment += timedelta(milliseconds=ms)


class Table:
    def __init__(self, store):
        self.store = store
        self.clock = ManualClock()
        ids = CountingIds()
        self.events = EventLog(store, self.clock)
        self.ducks = DuckService(store, self.events, self.clock, ids, DEFAULT_PROFILE_ID)
        self.play = SparringService(
            store, self.events, FakeEnginePool(), self.clock, ids, DEFAULT_PROFILE_ID
        )

    async def start(self, color="white", base_ms=None, increment_ms=0):
        duck = await self.ducks.hatch("Sparky")
        view = await self.play.start(duck.id, "fake", color, base_ms, increment_ms)
        await self.play.wait_idle(view.game.id)
        return duck, await self.play.get(view.game.id)

    async def types(self, stream):
        return [e.type for e in await self.events.read([stream], 0, 500)]


@pytest.fixture
def table(store):
    return Table(store)


def fresh_table(tmp_path, name):
    other = SqliteStore(tmp_path / f"{name}.db")
    other.migrate(NOW)
    other.profiles.ensure_default(NOW)
    return Table(other)


def first_legal(view):
    return sorted(move.uci() for move in view.board.legal_moves)[0]


async def play_out(table, game_id, moves=6):
    """The human plays the first legal move (alphabetically) each turn; the duck replies."""
    view = await table.play.get(game_id)
    for _ in range(moves):
        if view.game.state != "running":
            break
        view = await table.play.move(game_id, first_legal(view))
        await table.play.wait_idle(game_id)
        view = await table.play.get(game_id)
    return view


# ----- domain rules used here -----------------------------------------------------------


def test_a_human_is_charged_what_they_took_with_a_small_floor_and_can_flag():
    assert charge_human(60_000, 2_500, 1_000).remaining_ms == 58_500
    assert charge_human(60_000, 0, 0).remaining_ms == 60_000 - HUMAN_MOVE_FLOOR_MS
    assert charge_human(1_000, 1_000, 0).flagged


def test_running_out_of_time_is_a_draw_when_the_opponent_cannot_mate():
    bare_king = chess.Board("8/8/8/4k3/8/8/8/4K2R b - - 0 1")
    assert timeout(bare_king, loser_is_white=False).result == "1-0"
    assert timeout(bare_king, loser_is_white=True).termination == "timeout_vs_insufficient_material"


# ----- untimed games ----------------------------------------------------------------------


async def test_you_move_and_your_duck_replies_on_the_games_stream(table):
    _, view = await table.start("white")
    assert view.human_to_move and view.game.base_ms is None
    assert view.board.move_stack == []

    view = await table.play.move(view.game.id, "e2e4")
    assert not view.human_to_move  # the duck is thinking
    await table.play.wait_idle(view.game.id)
    view = await table.play.get(view.game.id)

    assert [m.by for m in view.moves] == ["human", "duck"]
    assert view.human_to_move
    types = await table.types(sparring_stream(view.game.id))
    assert types == ["SparringGameStarted", "MoveMade", "MoveChosen", "MoveMade"]


async def test_when_you_take_black_your_duck_moves_first(table):
    _, view = await table.start("black")

    assert [m.by for m in view.moves] == ["duck"]
    assert view.human_to_move


async def test_illegal_or_out_of_turn_moves_are_refused(table):
    _, view = await table.start("white")

    with pytest.raises(ServiceError) as error:
        await table.play.move(view.game.id, "e2e5")
    assert error.value.code == "sparring.illegal_move"

    await table.play.resign(view.game.id)
    with pytest.raises(ServiceError) as error:
        await table.play.move(view.game.id, "e2e4")
    assert error.value.code == "sparring.finished"


async def test_a_stored_game_replays_with_the_same_duck_moves(table, tmp_path):
    _, first = await table.start("white")
    first = await play_out(table, first.game.id)

    again = fresh_table(tmp_path, "again")
    _, second = await again.start("white")
    second = await play_out(again, second.game.id)

    assert [m.uci for m in second.moves] == [m.uci for m in first.moves]
    assert len(first.moves) >= 10


async def test_resigning_ends_the_game_and_the_duck_still_earns_xp(table):
    duck, view = await table.start("white")

    view = await table.play.resign(view.game.id)

    assert (view.game.result, view.game.termination, view.winner) == ("0-1", "resignation", "duck")
    grown = await table.ducks.get(duck.id)
    assert grown.growth.xp == DEFAULT_BALANCE.xp_rewards["game_played"]
    assert "XpGained" in await table.types(duck_stream(duck.id))


# ----- timed games -----------------------------------------------------------------------


async def test_your_clock_runs_on_your_turn_and_is_charged_when_you_move(table):
    _, view = await table.start("white", base_ms=60_000, increment_ms=1_000)

    table.clock.advance(2_500)
    assert (await table.play.get(view.game.id)).clock_ms("white") == 57_500
    view = await table.play.move(view.game.id, "e2e4")

    assert view.game.white_clock_ms == 58_500  # 60s - 2.5s + 1s increment
    await table.play.wait_idle(view.game.id)
    view = await table.play.get(view.game.id)
    assert view.game.black_clock_ms is not None and view.game.black_clock_ms < 60_000


async def test_running_out_of_time_loses_without_making_a_move(table):
    _, view = await table.start("white", base_ms=30_000)

    table.clock.advance(31_000)
    view = await table.play.claim_timeout(view.game.id)

    assert (view.game.result, view.game.termination, view.winner) == (
        "0-1",
        "time_forfeit",
        "duck",
    )


async def test_a_timeout_claim_with_time_left_is_refused(table):
    _, view = await table.start("white", base_ms=30_000)

    with pytest.raises(ServiceError) as error:
        await table.play.claim_timeout(view.game.id)
    assert error.value.code == "sparring.time_left"


# ----- "You play" series -----------------------------------------------------------------


async def test_a_you_play_series_alternates_colours_and_ends_when_decided(table):
    duck = await table.ducks.hatch("Rival")
    series = await table.play.start_series(duck.id, "fake", 3)
    first = await table.play.get(series.games[0].id)
    assert (first.game.base_ms, first.game.human_color) == (30_000, "white")

    with pytest.raises(ServiceError) as error:
        await table.play.next_series_game(series.series.id)
    assert error.value.code == "series.game_running"

    await table.play.resign(first.game.id)
    series = await table.play.next_series_game(series.series.id)
    second = await table.play.get(series.games[1].id)
    await table.play.wait_idle(second.game.id)
    assert second.game.human_color == "black"
    await table.play.resign(second.game.id)

    series = await table.play.get_series(series.series.id)
    assert (series.status.state, series.winner) == ("decided", "duck")
    with pytest.raises(ServiceError) as error:
        await table.play.next_series_game(series.series.id)
    assert error.value.code == "series.decided"
    types = await table.types(series_stream(series.series.id))
    assert types == ["SparringSeriesUpdated"] * 3
