"""The match runner (ADR-0007).

It loops plan → search → choose and records what happened. It makes no chess judgment
of its own: the domain decides moves, clocks and outcomes; the engine pool searches.

Every ply is committed atomically (move row, clocks, events), and every search is
stateless, so a cancelled or interrupted match continues from its last ply and ends
with exactly the same games as an uninterrupted one. The server never sleeps: clients
pace playback from the virtual think time carried in each event.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from fractions import Fraction
from functools import partial

from duckgambit.domain.arena import (
    Arena,
    ArenaCaps,
    VirtualClockLimit,
    rating_context,
    time_control_tag,
    validate_arena,
)
from duckgambit.domain.balance import DEFAULT_BALANCE, Balance
from duckgambit.domain.challengers import HOUSE_PROFILE_ID
from duckgambit.domain.chessutil import board_from, move_flags, parse_move, position_key
from duckgambit.domain.clock import charge, nodes_for, scale_nodes, think_budget_ms
from duckgambit.domain.decision import DECISION_LAYER_VERSION, SearchBudget, choose, plan
from duckgambit.domain.duck import Duck, grant_xp
from duckgambit.domain.engine_types import EngineIdentity
from duckgambit.domain.events import (
    DuckScore,
    Event,
    GameFinished,
    GameStarted,
    MatchCreated,
    MatchFinished,
    MatchStarted,
    MoveChosen,
    MoveMade,
    RatingUpdated,
    SeriesUpdated,
)
from duckgambit.domain.game import Outcome, outcome_of, points, time_forfeit
from duckgambit.domain.pgn import PgnGame, PgnMove, export_pgn
from duckgambit.domain.rating import Rating, update
from duckgambit.domain.seeds import derive_seed
from duckgambit.domain.series import (
    SeriesFormat,
    SeriesGame,
    SeriesStatus,
    armageddon_first_is_white,
    series_status,
    validate_format,
)
from duckgambit.services.ducks import duck_stream
from duckgambit.services.errors import ServiceError, not_found
from duckgambit.services.events import EventLog, iso
from duckgambit.services.jobs import JobCancelled, JobHandle, JobRunner
from duckgambit.services.ports import Clock, EnginePool, IdGenerator, Store
from duckgambit.services.records import GameRecord, MatchRecord, MoveRecord, RatingRecord

MODE_DUCK_VS_DUCK = "duck-vs-duck"


def match_stream(match_id: str) -> str:
    return f"match:{match_id}"


class MatchService:
    def __init__(
        self,
        store: Store,
        events: EventLog,
        jobs: JobRunner,
        pool: EnginePool,
        clock: Clock,
        ids: IdGenerator,
        profile_id: str,
        balance: Balance = DEFAULT_BALANCE,
        caps: ArenaCaps | None = None,
    ) -> None:
        self._store = store
        self._events = events
        self._jobs = jobs
        self._pool = pool
        self._clock = clock
        self._ids = ids
        self._profile_id = profile_id
        self._balance = balance
        self._caps = caps or ArenaCaps()
        self._policy = balance.clock

    # ----- queries -----------------------------------------------------------------

    async def get(self, match_id: str) -> MatchRecord:
        match = await asyncio.to_thread(self._store.matches.get_match, match_id)
        if match is None:
            raise not_found("match")
        return match

    async def recent(self, limit: int = 50) -> list[MatchRecord]:
        return await asyncio.to_thread(self._store.matches.list_matches, self._profile_id, limit)

    async def games(self, match_id: str) -> list[GameRecord]:
        await self.get(match_id)
        return await asyncio.to_thread(self._store.matches.list_games, match_id)

    async def game(self, game_id: str) -> GameRecord:
        game = await asyncio.to_thread(self._store.matches.get_game, game_id)
        if game is None:
            raise not_found("game")
        return game

    async def moves(self, game_id: str) -> list[MoveRecord]:
        await self.game(game_id)
        return await asyncio.to_thread(self._store.matches.list_moves, game_id)

    # ----- commands ----------------------------------------------------------------

    async def create(
        self,
        duck_ids: tuple[str, str],
        arena: Arena,
        rated: bool = True,
        series: SeriesFormat | None = None,
    ) -> MatchRecord:
        """Start a match. With `series`, it is a best-of series that stops once decided
        (and plays an Armageddon game if tied); `arena.games` is then the series length."""
        if series is not None:
            arena = replace(arena, games=validate_format(series).best_of)
        validate_arena(arena, self._caps)
        if len(set(duck_ids)) != 2:
            raise ServiceError("match.same_duck", "A match needs two different ducks")
        for duck_id in duck_ids:
            if await asyncio.to_thread(self._store.ducks.get, duck_id) is None:
                raise not_found("duck")
        identity = await self._pool.identity(arena.engine.id)
        if identity is None:
            raise ServiceError("engine.not_installed", "Install the engine before playing", 409)
        context = rating_context(
            arena,
            identity.version,
            identity.fingerprint,
            DECISION_LAYER_VERSION,
            self._balance.version,
        )
        match = MatchRecord(
            id=self._ids.new("mat"),
            profile_id=self._profile_id,
            duck_ids=duck_ids,
            arena=arena,
            mode=MODE_DUCK_VS_DUCK,
            rated=rated,
            state="created",
            context_id=context.id,
            job_id=self._jobs.new_id(),
            created_at=iso(self._clock),
            series=series,
        )
        await self._jobs.create(match.job_id, "match", {"match_id": match.id}, arena.games)
        created = MatchCreated(match.id, duck_ids, arena.games, match.mode, rated)

        def write() -> None:
            with self._store.atomic():
                self._store.ratings.save_context(context, match.created_at)
                self._store.matches.add_match(match)
                self._events.append(match_stream(match.id), [created])

        await asyncio.to_thread(write)
        self._events.notify()
        await self._jobs.start(match.job_id, partial(self._run, match.id))
        return match

    async def resume(self, match_id: str) -> MatchRecord:
        """Continue a cancelled, failed or interrupted match from its last recorded ply."""
        match = await self.get(match_id)
        if match.state == "finished":
            raise ServiceError("match.finished", "The match has already finished", 409)
        await self._jobs.start(match.job_id, partial(self._run, match.id))
        return match

    # ----- the runner --------------------------------------------------------------

    async def _run(self, match_id: str, handle: JobHandle) -> None:
        match = await self.get(match_id)
        try:
            await self._play_match(match, handle)
        except JobCancelled:
            await asyncio.to_thread(self._store.matches.set_match_state, match_id, "cancelled")
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.to_thread(self._store.matches.set_match_state, match_id, "failed")
            raise

    async def _play_match(self, match: MatchRecord, handle: JobHandle) -> None:
        ducks = {}
        for duck_id in match.duck_ids:
            duck = await asyncio.to_thread(self._store.ducks.get, duck_id)
            if duck is None:
                raise not_found("duck")
            ducks[duck_id] = duck
        identity = await self._pool.identity(match.arena.engine.id)
        if identity is None:
            raise ServiceError("engine.not_installed", "The engine is no longer installed", 409)

        first_run = match.state == "created"
        await asyncio.to_thread(self._store.matches.set_match_state, match.id, "running")
        if first_run:
            opening: list[Event] = [MatchStarted(match.id)]
            if match.series is not None:
                opening.append(self._series_event(match, series_status(match.series.best_of, [])))
            await self._events.publish(match_stream(match.id), opening)

        if match.series is not None:
            await self._play_series(match, match.series, ducks, identity, handle)
            await self._finish_match(match)
            return

        total = match.arena.games
        existing = {game.index: game for game in await self.games(match.id)}
        for index in range(total):
            handle.check()
            game = existing.get(index) or await self._start_game(match, index)
            if game.state != "finished":
                await self._play_game(match, game, ducks, identity, handle)
            await handle.progress(index + 1, total)
        await self._finish_match(match)

    async def _play_series(
        self,
        match: MatchRecord,
        series: SeriesFormat,
        ducks: dict[str, Duck],
        identity: EngineIdentity,
        handle: JobHandle,
    ) -> None:
        """Play games until the series is decided. Game `best_of` (0-based) is Armageddon."""
        index = 0
        while True:
            handle.check()
            games = await asyncio.to_thread(self._store.matches.list_games, match.id)
            status = series_status(series.best_of, self._series_games(match, games))
            if status.state == "decided":
                return
            existing = {game.index: game for game in games}
            game = existing.get(index) or await self._start_game(match, index)
            if game.state != "finished":
                await self._play_game(match, game, ducks, identity, handle)
            index += 1
            total = series.best_of + (1 if index > series.best_of else 0)
            await handle.progress(index, total)

    def _series_games(self, match: MatchRecord, games: list[GameRecord]) -> list[SeriesGame]:
        assert match.series is not None
        first = match.duck_ids[0]
        return [
            SeriesGame(
                first_points=Fraction(
                    points(game.result, "white" if game.white_duck_id == first else "black")
                ),
                armageddon=game.index >= match.series.best_of,
                first_is_black=game.black_duck_id == first,
            )
            for game in sorted(games, key=lambda game: game.index)
            if game.result is not None
        ]

    def _series_event(self, match: MatchRecord, status: SeriesStatus) -> SeriesUpdated:
        assert match.series is not None
        first, second = match.duck_ids
        armageddon_white = None
        if status.state == "armageddon" or status.decided_by == "armageddon":
            armageddon_white = first if armageddon_first_is_white(match.arena.seed) else second
        return SeriesUpdated(
            match_id=match.id,
            best_of=match.series.best_of,
            scores=(
                DuckScore(first, float(status.first_points)),
                DuckScore(second, float(status.second_points)),
            ),
            games_played=status.games_played,
            state=status.state,
            winner_duck_id=None if status.winner is None else match.duck_ids[status.winner],
            decided_by=status.decided_by,
            armageddon_white_duck_id=armageddon_white,
        )

    async def _start_game(self, match: MatchRecord, index: int) -> GameRecord:
        arena = match.arena
        first, second = match.duck_ids
        if match.series is not None and index >= match.series.best_of:
            swapped = not armageddon_first_is_white(arena.seed)  # the Armageddon game
        else:
            swapped = arena.swap_colors and index % 2 == 1
        base = arena.limit.base_ms if isinstance(arena.limit, VirtualClockLimit) else None
        game = GameRecord(
            id=self._ids.new("game"),
            match_id=match.id,
            index=index,
            white_duck_id=second if swapped else first,
            black_duck_id=first if swapped else second,
            seed=derive_seed(arena.seed, "game", index),
            initial_fen=arena.initial_fen,
            state="running",
            white_clock_ms=base,
            black_clock_ms=base,
            started_at=iso(self._clock),
        )
        started = GameStarted(
            match.id,
            game.id,
            index,
            game.white_duck_id,
            game.black_duck_id,
            game.initial_fen,
            base,
            base,
        )

        def write() -> None:
            with self._store.atomic():
                self._store.matches.add_game(game)
                self._events.append(match_stream(match.id), [started])

        await asyncio.to_thread(write)
        self._events.notify()
        return game

    async def _play_game(
        self,
        match: MatchRecord,
        game: GameRecord,
        ducks: dict[str, Duck],
        identity: EngineIdentity,
        handle: JobHandle,
    ) -> None:
        arena = match.arena
        limit = arena.limit
        recorded = await asyncio.to_thread(self._store.matches.list_moves, game.id)
        board = board_from(game.initial_fen, tuple(move.uci for move in recorded))
        clocks: dict[str, int | None] = {
            "white": game.white_clock_ms,
            "black": game.black_clock_ms,
        }
        outcome: Outcome | None = None

        async with self._pool.lease(arena.engine.id, arena.engine.hash_mb) as engine:
            while True:
                outcome = outcome_of(board, arena.max_plies)
                if outcome is not None:
                    break
                handle.check()

                color = "white" if board.turn else "black"
                duck = ducks[game.white_duck_id if color == "white" else game.black_duck_id]
                mind = duck.mind(self._balance)
                multiplier = 1000 if arena.equal_engine else mind.node_multiplier_milli
                remaining = clocks[color]
                if isinstance(limit, VirtualClockLimit) and remaining is not None:
                    think_ms = think_budget_ms(
                        remaining, limit.increment_ms, board.fullmove_number, mind, self._policy
                    )
                    nodes = nodes_for(
                        think_ms, limit.virtual_nps, multiplier, self._caps.max_nodes, self._policy
                    )
                else:
                    think_ms = 0
                    nodes = scale_nodes(
                        getattr(limit, "nodes", 0), multiplier, self._caps.max_nodes, self._policy
                    )

                key = position_key(board)
                planned = plan(
                    board,
                    mind,
                    duck.knowledge.book_moves(color, key),
                    SearchBudget(nodes, arena.multipv),
                    game.seed,
                    duck.knowledge.taught_move(key),
                )
                if planned.decision is not None:
                    decision = planned.decision
                    nodes = 0
                    if isinstance(limit, VirtualClockLimit):
                        think_ms = self._policy.instant_move_ms
                else:
                    assert planned.request is not None
                    result = await engine.search(planned.request)
                    decision = choose(board, mind, result, game.seed, planned.notes)

                if isinstance(limit, VirtualClockLimit) and remaining is not None:
                    charged = charge(remaining, think_ms, limit.increment_ms, self._policy)
                    clocks[color] = charged.remaining_ms
                    if charged.flagged:
                        outcome = time_forfeit(loser_is_white=color == "white")
                        break

                ply = len(board.move_stack) + 1
                fen_before = board.fen()
                move = parse_move(board, decision.move)
                flags = move_flags(board, move)
                board.push(move)
                played = next((c for c in decision.candidates if c.move == decision.move), None)
                chosen = MoveChosen(
                    game_id=game.id,
                    ply=ply,
                    duck_id=duck.id,
                    color=color,
                    fen_before=fen_before,
                    move=decision.move,
                    san=decision.san,
                    source=decision.source,
                    candidates=decision.candidates,
                    reasons=decision.reasons,
                    think_ms=think_ms,
                    nodes_budget=nodes,
                    nodes=decision.nodes,
                    depth=decision.depth,
                )
                made = MoveMade(
                    game_id=game.id,
                    ply=ply,
                    color=color,
                    by="duck",
                    duck_id=duck.id,
                    uci=decision.move,
                    san=decision.san,
                    fen_after=board.fen(),
                    capture=flags.capture,
                    en_passant=flags.en_passant,
                    check=flags.check,
                    checkmate=flags.checkmate,
                    castle=flags.castle,
                    promotion=flags.promotion,
                    think_ms=think_ms,
                    white_clock_ms=clocks["white"],
                    black_clock_ms=clocks["black"],
                )
                record = MoveRecord(
                    game_id=game.id,
                    ply=ply,
                    color=color,
                    uci=decision.move,
                    san=decision.san,
                    source=decision.source,
                    cp=played.cp if played else None,
                    mate=played.mate if played else None,
                    nodes=decision.nodes,
                    depth=decision.depth,
                    think_ms=think_ms,
                    clock_ms=clocks[color],
                    fen_after=board.fen(),
                    event_seq=0,
                    position_key=key,  # computed above, before the move was pushed
                )
                await self._record_ply(match.id, record, [chosen, made], clocks)

        await self._finish_game(match, game, ducks, identity, outcome, len(board.move_stack))

    async def _record_ply(
        self,
        match_id: str,
        move: MoveRecord,
        events: list[Event],
        clocks: dict[str, int | None],
    ) -> None:
        def write() -> None:
            with self._store.atomic():
                envelopes = self._events.append(match_stream(match_id), events)
                self._store.matches.add_move(
                    replace(move, event_seq=envelopes[0].seq), clocks["white"], clocks["black"]
                )

        await asyncio.to_thread(write)
        self._events.notify()

    async def _finish_game(
        self,
        match: MatchRecord,
        game: GameRecord,
        ducks: dict[str, Duck],
        identity: EngineIdentity,
        outcome: Outcome,
        plies: int,
    ) -> None:
        white, black = ducks[game.white_duck_id], ducks[game.black_duck_id]
        moves = await asyncio.to_thread(self._store.matches.list_moves, game.id)
        pgn = export_pgn(
            PgnGame(
                event="Duck Gambit match",
                site="Duck Gambit",
                date=game.started_at[:10].replace("-", "."),
                round=str(game.index + 1),
                white=white.name,
                black=black.name,
                result=outcome.result,
                termination=outcome.termination,
                time_control=time_control_tag(match.arena.limit),
                initial_fen=game.initial_fen,
                seed=game.seed,
                rating_context=match.context_id,
                engine=f"{identity.name} {identity.version}",
                moves=tuple(PgnMove(m.uci, m.source, m.cp, m.mate, m.clock_ms) for m in moves),
            )
        )
        winner = {"white": white.id, "black": black.id}.get(outcome.winner or "")
        finished = GameFinished(
            match.id, game.id, outcome.result, outcome.termination, winner, plies
        )
        now = iso(self._clock)
        after: list[Event] = []
        if match.series is not None:
            games = await asyncio.to_thread(self._store.matches.list_games, match.id)
            done = [replace(g, result=outcome.result) if g.id == game.id else g for g in games]
            status = series_status(match.series.best_of, self._series_games(match, done))
            after.append(self._series_event(match, status))

        def write() -> list[tuple[str, RatingUpdated]]:
            rating_events: list[tuple[str, RatingUpdated]] = []
            with self._store.atomic():
                self._store.matches.finish_game(
                    game.id, outcome.result, outcome.termination, pgn, now
                )
                self._events.append(match_stream(match.id), [finished, *after])
                if match.rated:
                    rating_events = self._rate(match.context_id, game, outcome.result, now)
                    for stream, event in rating_events:
                        self._events.append(stream, [event])
            return rating_events

        await asyncio.to_thread(write)
        self._events.notify()

    def _rate(
        self, context_id: str, game: GameRecord, result: str, now: str
    ) -> list[tuple[str, RatingUpdated]]:
        """Glicko-2 update for both ducks from this one game, inside the caller's transaction."""
        ratings = self._store.ratings
        initial = Rating(value=float(self._balance.provisional_rating))
        before = {
            duck_id: ratings.get(duck_id, context_id, "game") or initial
            for duck_id in (game.white_duck_id, game.black_duck_id)
        }
        events = []
        for duck_id, color, opponent in (
            (game.white_duck_id, "white", game.black_duck_id),
            (game.black_duck_id, "black", game.white_duck_id),
        ):
            after = update(before[duck_id], [(before[opponent], points(result, color))])
            ratings.save(RatingRecord(duck_id, context_id, "game", after, now), game.id)
            events.append(
                (
                    duck_stream(duck_id),
                    RatingUpdated(
                        duck_id=duck_id,
                        context_id=context_id,
                        kind="game",
                        before=round(before[duck_id].value, 1),
                        after=round(after.value, 1),
                        deviation=round(after.deviation, 1),
                        games=after.games,
                        provisional=after.provisional,
                    ),
                )
            )
        return events

    async def _finish_match(self, match: MatchRecord) -> None:
        games = await asyncio.to_thread(self._store.matches.list_games, match.id)
        scores = dict.fromkeys(match.duck_ids, 0.0)
        for game in games:
            if game.result is None:
                continue
            scores[game.white_duck_id] += points(game.result, "white")
            scores[game.black_duck_id] += points(game.result, "black")
        first, second = match.duck_ids
        winner = None
        if match.series is not None:
            status = series_status(match.series.best_of, self._series_games(match, games))
            winner = None if status.winner is None else match.duck_ids[status.winner]
        elif scores[first] != scores[second]:
            winner = first if scores[first] > scores[second] else second
        finished = MatchFinished(
            match.id,
            tuple(DuckScore(duck_id, scores[duck_id]) for duck_id in match.duck_ids),
            winner,
        )
        now = iso(self._clock)
        rewards = self._balance.xp_rewards

        def write() -> None:
            with self._store.atomic():
                self._store.matches.set_match_state(match.id, "finished", now, scores)
                self._events.append(match_stream(match.id), [finished])
                # XP only now, at the end: every game of the match (and any resume) was
                # played at the level the duck had when the match started.
                for duck_id in match.duck_ids:
                    duck = self._store.ducks.get(duck_id)
                    if duck is None or duck.profile_id == HOUSE_PROFILE_ID:
                        continue  # challengers do not grow
                    played = [
                        g
                        for g in games
                        if g.result is not None and duck_id in (g.white_duck_id, g.black_duck_id)
                    ]
                    wins = sum(
                        1
                        for g in played
                        if points(
                            g.result or "", "white" if g.white_duck_id == duck_id else "black"
                        )
                        == 1
                    )
                    amount = len(played) * rewards["game_played"] + wins * rewards["game_won"]
                    grown, events = grant_xp(duck, amount, "match", self._balance)
                    self._store.ducks.update(grown)
                    self._events.append(duck_stream(duck_id), events)

        await asyncio.to_thread(write)
        self._events.notify()
