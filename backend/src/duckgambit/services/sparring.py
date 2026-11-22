"""Games between the player and one of their ducks (Practice Pond, "You play"; ADR-0015).

Not a background job: the game waits for the human. The human's move arrives as a UCI
string; this service measures how long they took with the clock port and passes it to
the domain as data. The duck's reply is computed in a task and published on the game's
stream. The duck's moves depend only on the move history, the seed and its mind, so a
stored game replays exactly. These games are never rated; the duck earns XP for each.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, replace
from fractions import Fraction

import chess

from duckgambit.domain.arena import STARTING_FEN, Limit, NodesLimit, VirtualClockLimit
from duckgambit.domain.balance import DEFAULT_BALANCE, Balance
from duckgambit.domain.challengers import HOUSE_PROFILE_ID
from duckgambit.domain.chessutil import board_from, move_flags, parse_move
from duckgambit.domain.clock import charge, charge_human
from duckgambit.domain.duck import grant_xp
from duckgambit.domain.errors import DomainError
from duckgambit.domain.events import (
    Event,
    MoveChosen,
    MoveMade,
    SparringGameFinished,
    SparringGameStarted,
    SparringSeriesUpdated,
)
from duckgambit.domain.game import Outcome, outcome_of, points, resignation, timeout
from duckgambit.domain.seeds import derive_seed, draw_below, rng_for
from duckgambit.domain.series import (
    SeriesFormat,
    SeriesGame,
    SeriesStatus,
    armageddon_first_is_white,
    series_status,
    validate_format,
)
from duckgambit.services.duck_turn import decide_duck_move
from duckgambit.services.ducks import duck_stream
from duckgambit.services.errors import ServiceError, not_found
from duckgambit.services.events import EventLog, iso
from duckgambit.services.ports import Clock, EnginePool, IdGenerator, Store
from duckgambit.services.records import SparringGame, SparringMove, SparringSeries

log = logging.getLogger(__name__)

UNTIMED_NODES = 200_000  # [PH] the duck's base search per move in an untimed game
VIRTUAL_NPS = 200_000  # as the Arena presets
MAX_PLIES = 400
MULTIPV = 5
SUPER_BULLET_MS = 30_000  # "You play" series: 30 seconds each (John, 2026-11-21)


def sparring_stream(game_id: str) -> str:
    return f"sparring:{game_id}"


def series_stream(series_id: str) -> str:
    return f"sparring-series:{series_id}"


@dataclass(frozen=True)
class SparringView:
    """A game as the player sees it right now."""

    game: SparringGame
    moves: list[SparringMove]
    board: chess.Board
    now_ms: int

    @property
    def turn(self) -> str:
        return "white" if self.board.turn else "black"

    @property
    def human_to_move(self) -> bool:
        return self.game.state == "running" and self.turn == self.game.human_color

    def clock_ms(self, color: str) -> int | None:
        """Time left; the human's clock runs while it is their turn. The duck's clock is
        virtual and only changes when it moves."""
        game = self.game
        stored = game.white_clock_ms if color == "white" else game.black_clock_ms
        if stored is None or game.state != "running" or color != self.turn:
            return stored
        if color != game.human_color or game.turn_started_ms is None:
            return stored
        return max(0, stored - (self.now_ms - game.turn_started_ms))

    @property
    def winner(self) -> str | None:
        if self.game.result is None or self.game.result == "1/2-1/2":
            return None
        white_won = self.game.result == "1-0"
        return "human" if white_won == (self.game.human_color == "white") else "duck"


@dataclass(frozen=True)
class SeriesView:
    series: SparringSeries
    games: list[SparringGame]
    status: SeriesStatus
    armageddon_human_color: str | None

    @property
    def winner(self) -> str | None:
        if self.status.winner is None:
            return None
        return "human" if self.status.winner == 0 else "duck"


class SparringService:
    def __init__(
        self,
        store: Store,
        events: EventLog,
        pool: EnginePool,
        clock: Clock,
        ids: IdGenerator,
        profile_id: str,
        balance: Balance = DEFAULT_BALANCE,
        max_nodes: int = 5_000_000,
    ) -> None:
        self._store = store
        self._events = events
        self._pool = pool
        self._clock = clock
        self._ids = ids
        self._profile_id = profile_id
        self._balance = balance
        self._max_nodes = max_nodes
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    # ----- games -------------------------------------------------------------------

    async def start(
        self,
        duck_id: str,
        engine_id: str,
        human_color: str = "random",
        base_ms: int | None = None,
        increment_ms: int = 0,
        *,
        series: SparringSeries | None = None,
        series_index: int | None = None,
    ) -> SparringView:
        duck = await asyncio.to_thread(self._store.ducks.get, duck_id)
        if duck is None or duck.profile_id != self._profile_id:
            raise not_found("duck")
        if await self._pool.identity(engine_id) is None:
            raise ServiceError("engine.not_installed", "Install the engine before playing", 409)
        if human_color not in ("white", "black", "random"):
            raise ServiceError("sparring.color", "Choose white, black or random", 422)
        if base_ms is not None and not 1_000 <= base_ms <= 3_600_000:
            raise ServiceError("sparring.time", "Base time must be 1 second to 1 hour", 422)
        if not 0 <= increment_ms <= 60_000:
            raise ServiceError("sparring.time", "Increment must be 0 to 60 seconds", 422)

        game_id = self._ids.new("spar")
        if series is not None and series_index is not None:
            seed = derive_seed(series.seed, "game", series_index)
        else:
            seed = derive_seed(0, "sparring", game_id)
        if human_color == "random":
            human_color = "white" if draw_below(rng_for(seed, "color"), 2) == 0 else "black"

        game = SparringGame(
            id=game_id,
            profile_id=self._profile_id,
            duck_id=duck_id,
            engine_id=engine_id,
            human_color=human_color,
            base_ms=base_ms,
            increment_ms=increment_ms if base_ms is not None else 0,
            seed=seed,
            initial_fen=STARTING_FEN,
            state="running",
            white_clock_ms=base_ms,
            black_clock_ms=base_ms,
            turn_started_ms=self._now_ms(),
            created_at=iso(self._clock),
            series_id=series.id if series else None,
            series_index=series_index,
        )
        started = SparringGameStarted(
            game_id, duck_id, human_color, STARTING_FEN, base_ms, base_ms, game.series_id
        )

        def write() -> None:
            with self._store.atomic():
                self._store.sparring.add_game(game)
                self._events.append(sparring_stream(game_id), [started])

        await asyncio.to_thread(write)
        self._events.notify()
        view = await self._view(game_id)
        self._ensure_duck_turn(view)
        return view

    async def get(self, game_id: str) -> SparringView:
        """The game now. A human who ran out of time loses here, and a duck whose reply
        was interrupted (a restart) starts thinking again."""
        view = await self._view(game_id)
        if view.human_to_move and self._out_of_time(view):
            async with self._lock(game_id):
                view = await self._view(game_id)
                if view.human_to_move and self._out_of_time(view):
                    await self._finish(view, timeout(view.board, view.turn == "white"))
                    view = await self._view(game_id)
        self._ensure_duck_turn(view)
        return view

    async def recent(self, limit: int = 10) -> list[SparringGame]:
        return await asyncio.to_thread(self._store.sparring.recent_games, self._profile_id, limit)

    async def move(self, game_id: str, uci: str) -> SparringView:
        async with self._lock(game_id):
            view = await self._view(game_id)
            if view.game.state != "running":
                raise ServiceError("sparring.finished", "The game is over", 409)
            if not view.human_to_move:
                raise ServiceError("sparring.not_your_turn", "Wait for your duck's move", 409)
            try:
                move = parse_move(view.board, uci)
            except DomainError as error:
                raise ServiceError(
                    "sparring.illegal_move", "That move is not legal here", 422
                ) from error

            game = view.game
            elapsed = view.now_ms - (game.turn_started_ms or view.now_ms)
            color = view.turn
            clocks = {"white": game.white_clock_ms, "black": game.black_clock_ms}
            remaining = clocks[color]
            if game.base_ms is not None and remaining is not None:
                charged = charge_human(remaining, elapsed, game.increment_ms)
                if charged.flagged:
                    await self._finish(view, timeout(view.board, color == "white"))
                    return await self._view(game_id)
                clocks[color] = charged.remaining_ms
            await self._record(view, move, "human", elapsed, clocks, None)
            view = await self._view(game_id)
            outcome = outcome_of(view.board, MAX_PLIES)
            if outcome is not None:
                await self._finish(view, outcome)
                return await self._view(game_id)
        self._ensure_duck_turn(view)
        return view

    async def resign(self, game_id: str) -> SparringView:
        async with self._lock(game_id):
            view = await self._view(game_id)
            if view.game.state != "running":
                raise ServiceError("sparring.finished", "The game is over", 409)
            await self._finish(view, resignation(view.game.human_color == "white"))
            return await self._view(game_id)

    async def claim_timeout(self, game_id: str) -> SparringView:
        """The client says the human's clock reached zero; the server checks and ends it."""
        view = await self.get(game_id)
        if view.game.state == "running":
            raise ServiceError("sparring.time_left", "There is still time on the clock", 409)
        return view

    async def wait_idle(self, game_id: str) -> None:
        """Wait for the duck's reply in progress, if any (tests and shutdown)."""
        task = self._tasks.get(game_id)
        if task is not None:
            await task

    async def close(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        for task in list(self._tasks.values()):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    # ----- "You play" series -----------------------------------------------------

    async def start_series(self, duck_id: str, engine_id: str, best_of: int) -> SeriesView:
        validate_format(SeriesFormat(best_of))
        series = SparringSeries(
            id=self._ids.new("sser"),
            profile_id=self._profile_id,
            duck_id=duck_id,
            engine_id=engine_id,
            best_of=best_of,
            seed=0,
            state="playing",
            created_at=iso(self._clock),
        )
        series = replace(series, seed=derive_seed(0, "sparring-series", series.id))
        duck = await asyncio.to_thread(self._store.ducks.get, duck_id)
        if duck is None or duck.profile_id != self._profile_id:
            raise not_found("duck")
        await asyncio.to_thread(self._store.sparring.add_series, series)
        await self._events.publish(
            series_stream(series.id), [self._series_event(self._series_view(series, []))]
        )
        await self._next_series_game(series, [])
        return await self.get_series(series.id)

    async def get_series(self, series_id: str) -> SeriesView:
        series = await asyncio.to_thread(self._store.sparring.get_series, series_id)
        if series is None or series.profile_id != self._profile_id:
            raise not_found("series")
        games = await asyncio.to_thread(self._store.sparring.series_games, series_id)
        return self._series_view(series, games)

    async def next_series_game(self, series_id: str) -> SeriesView:
        view = await self.get_series(series_id)
        if view.status.state == "decided":
            raise ServiceError("series.decided", "The series is over", 409)
        if any(game.state == "running" for game in view.games):
            raise ServiceError("series.game_running", "Finish the current game first", 409)
        await self._next_series_game(view.series, view.games)
        return await self.get_series(series_id)

    async def _next_series_game(self, series: SparringSeries, games: list[SparringGame]) -> None:
        index = len(games)
        if index >= series.best_of:  # the Armageddon game
            human_white = armageddon_first_is_white(series.seed)
        else:
            human_white = index % 2 == 0
        await self.start(
            series.duck_id,
            series.engine_id,
            "white" if human_white else "black",
            SUPER_BULLET_MS,
            0,
            series=series,
            series_index=index,
        )

    def _series_view(self, series: SparringSeries, games: list[SparringGame]) -> SeriesView:
        played = [
            SeriesGame(
                first_points=Fraction(points(game.result, game.human_color)),
                armageddon=(game.series_index or 0) >= series.best_of,
                first_is_black=game.human_color == "black",
            )
            for game in games
            if game.result is not None
        ]
        status = series_status(series.best_of, played)
        armageddon_color = None
        if status.state == "armageddon" or status.decided_by == "armageddon":
            armageddon_color = "white" if armageddon_first_is_white(series.seed) else "black"
        return SeriesView(series, games, status, armageddon_color)

    def _series_event(self, view: SeriesView) -> SparringSeriesUpdated:
        return SparringSeriesUpdated(
            series_id=view.series.id,
            best_of=view.series.best_of,
            human_points=float(view.status.first_points),
            duck_points=float(view.status.second_points),
            games_played=view.status.games_played,
            state=view.status.state,
            winner=view.winner,
            decided_by=view.status.decided_by,
            armageddon_human_color=view.armageddon_human_color,
        )

    # ----- internals ---------------------------------------------------------------

    def _now_ms(self) -> int:
        return int(self._clock.now().timestamp() * 1000)

    def _lock(self, game_id: str) -> asyncio.Lock:
        return self._locks.setdefault(game_id, asyncio.Lock())

    @staticmethod
    def _out_of_time(view: SparringView) -> bool:
        left = view.clock_ms(view.turn)
        return view.game.base_ms is not None and left is not None and left <= 0

    async def _view(self, game_id: str) -> SparringView:
        game = await asyncio.to_thread(self._store.sparring.get_game, game_id)
        if game is None or game.profile_id != self._profile_id:
            raise not_found("game")
        moves = await asyncio.to_thread(self._store.sparring.list_moves, game_id)
        board = board_from(game.initial_fen, tuple(move.uci for move in moves))
        return SparringView(game, moves, board, self._now_ms())

    def _ensure_duck_turn(self, view: SparringView) -> None:
        if view.game.state != "running" or view.human_to_move:
            return
        running = self._tasks.get(view.game.id)
        if running is not None and not running.done():
            return
        task = asyncio.create_task(self._duck_reply(view.game.id))
        self._tasks[view.game.id] = task
        task.add_done_callback(self._reply_done)

    @staticmethod
    def _reply_done(task: asyncio.Task[None]) -> None:
        if not task.cancelled() and task.exception() is not None:
            log.error("A duck's reply failed", exc_info=task.exception())

    async def _duck_reply(self, game_id: str) -> None:
        async with self._lock(game_id):
            view = await self._view(game_id)
            if view.game.state != "running" or view.human_to_move:
                return
            game = view.game
            duck = await asyncio.to_thread(self._store.ducks.get, game.duck_id)
            if duck is None:
                return
            limit: Limit = (
                VirtualClockLimit(game.base_ms, game.increment_ms, VIRTUAL_NPS)
                if game.base_ms is not None
                else NodesLimit(UNTIMED_NODES)
            )
            color = view.turn
            clocks = {"white": game.white_clock_ms, "black": game.black_clock_ms}
            async with self._pool.lease(game.engine_id) as engine:
                turn = await decide_duck_move(
                    engine,
                    view.board,
                    duck,
                    color=color,
                    limit=limit,
                    remaining_ms=clocks[color],
                    multipv=MULTIPV,
                    equal_engine=False,
                    seed=game.seed,
                    balance=self._balance,
                    max_nodes=self._max_nodes,
                )
            remaining = clocks[color]
            if game.base_ms is not None and remaining is not None:
                charged = charge(remaining, turn.think_ms, game.increment_ms, self._balance.clock)
                if charged.flagged:
                    await self._finish(view, timeout(view.board, color == "white"))
                    return
                clocks[color] = charged.remaining_ms
            move = parse_move(view.board, turn.decision.move)
            ply = len(view.board.move_stack) + 1
            chosen = MoveChosen(
                game_id=game.id,
                ply=ply,
                duck_id=duck.id,
                color=color,
                fen_before=view.board.fen(),
                move=turn.decision.move,
                san=turn.decision.san,
                source=turn.decision.source,
                candidates=turn.decision.candidates,
                reasons=turn.decision.reasons,
                think_ms=turn.think_ms,
                nodes_budget=turn.nodes_budget,
                nodes=turn.decision.nodes,
                depth=turn.decision.depth,
            )
            await self._record(view, move, "duck", turn.think_ms, clocks, chosen)
            view = await self._view(game_id)
            outcome = outcome_of(view.board, MAX_PLIES)
            if outcome is not None:
                await self._finish(view, outcome)

    async def _record(
        self,
        view: SparringView,
        move: chess.Move,
        by: str,
        elapsed_ms: int,
        clocks: dict[str, int | None],
        chosen: MoveChosen | None,
    ) -> None:
        game = view.game
        board = view.board.copy()
        color = "white" if board.turn else "black"
        flags = move_flags(board, move)
        san = board.san(move)
        board.push(move)
        ply = len(board.move_stack)
        made = MoveMade(
            game_id=game.id,
            ply=ply,
            color=color,
            by=by,
            duck_id=game.duck_id if by == "duck" else None,
            uci=move.uci(),
            san=san,
            fen_after=board.fen(),
            capture=flags.capture,
            en_passant=flags.en_passant,
            check=flags.check,
            checkmate=flags.checkmate,
            castle=flags.castle,
            promotion=flags.promotion,
            think_ms=elapsed_ms,
            white_clock_ms=clocks["white"],
            black_clock_ms=clocks["black"],
        )
        record = SparringMove(
            game.id,
            ply,
            color,
            by,
            move.uci(),
            san,
            chosen.source if chosen else None,
            elapsed_ms,
            board.fen(),
        )
        updated = replace(
            game,
            white_clock_ms=clocks["white"],
            black_clock_ms=clocks["black"],
            turn_started_ms=self._now_ms(),
        )
        events: list[Event] = [chosen, made] if chosen else [made]

        def write() -> None:
            with self._store.atomic():
                self._store.sparring.add_move(record)
                self._store.sparring.save_game(updated)
                self._events.append(sparring_stream(game.id), events)

        await asyncio.to_thread(write)
        self._events.notify()

    async def _finish(self, view: SparringView, outcome: Outcome) -> None:
        game = replace(
            view.game,
            state="finished",
            result=outcome.result,
            termination=outcome.termination,
            finished_at=iso(self._clock),
        )
        done = SparringView(game, view.moves, view.board, view.now_ms)
        finished = SparringGameFinished(
            game.id, outcome.result, outcome.termination, done.winner, len(view.board.move_stack)
        )
        series = (
            await asyncio.to_thread(self._store.sparring.get_series, game.series_id)
            if game.series_id
            else None
        )

        def write() -> None:
            with self._store.atomic():
                self._store.sparring.save_game(game)
                self._events.append(sparring_stream(game.id), [finished])
                duck = self._store.ducks.get(game.duck_id)
                if duck is not None and duck.profile_id != HOUSE_PROFILE_ID:
                    amount = self._balance.xp_rewards["game_played"]
                    grown, events = grant_xp(duck, amount, "sparring", self._balance)
                    self._store.ducks.update(grown)
                    self._events.append(duck_stream(duck.id), events)
                if series is not None:
                    games = self._store.sparring.series_games(series.id)
                    status = self._series_view(series, games)
                    if status.status.state == "decided":
                        self._store.sparring.set_series_state(
                            series.id, "decided", game.finished_at
                        )
                    self._events.append(series_stream(series.id), [self._series_event(status)])

        await asyncio.to_thread(write)
        self._events.notify()
