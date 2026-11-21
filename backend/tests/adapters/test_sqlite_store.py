import sqlite3
from dataclasses import replace

import pytest

from conftest import NOW
from duckgambit.adapters.sqlite.database import Database, SchemaTooNewError, available_migrations
from duckgambit.adapters.sqlite.store import DEFAULT_PROFILE_ID, SqliteStore, upcast_duck_doc
from duckgambit.domain.arena import BULLET, Arena, EngineSettings, NodesLimit
from duckgambit.domain.duck import hatch
from duckgambit.domain.knowledge import Knowledge, PuzzleMemoryEntry, RepertoireEntry
from duckgambit.domain.rating import Rating
from duckgambit.services.records import (
    EngineProfile,
    GameRecord,
    JobRecord,
    MatchRecord,
    MoveRecord,
    RatingRecord,
)


def a_duck(duck_id="duck_1", name="Sir Quackalot"):
    duck, _ = hatch(duck_id=duck_id, profile_id=DEFAULT_PROFILE_ID, name=name, now=NOW)
    return duck


def a_match(arena=None) -> MatchRecord:
    return MatchRecord(
        id="mat_1",
        profile_id=DEFAULT_PROFILE_ID,
        duck_ids=("duck_1", "duck_2"),
        arena=arena or Arena(EngineSettings("stockfish"), BULLET, seed=7),
        mode="duck-vs-duck",
        rated=True,
        state="created",
        context_id="ctx_1",
        job_id="job_1",
        created_at=NOW,
    )


def test_a_fresh_database_is_migrated_to_the_latest_version(tmp_path):
    store = SqliteStore(tmp_path / "new.db")

    applied = store.migrate(NOW)

    latest = available_migrations()[-1][0]
    assert applied == list(range(1, latest + 1))
    assert store.database.schema_version() == latest
    assert store.migrate(NOW) == []


def test_a_database_from_a_newer_build_is_refused(tmp_path):
    path = tmp_path / "future.db"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 9999")
    connection.close()

    with pytest.raises(SchemaTooNewError):
        Database(path).migrate(NOW)


def test_duck_round_trips_with_its_knowledge(store):
    duck = a_duck()
    duck = duck.with_knowledge(
        Knowledge(
            repertoire=(RepertoireEntry("white", "key w KQkq -", "e2e4", 3, "lesson", "les_1"),),
            principles=("castle_early",),
            motifs={"fork": 60},
            puzzle_memory=(PuzzleMemoryEntry("other w - -", "g1f3", "les_2"),),
        )
    )

    store.ducks.add(duck)

    assert store.ducks.get("duck_1") == duck
    assert store.ducks.list_for(DEFAULT_PROFILE_ID) == [duck]
    assert store.ducks.get("duck_missing") is None


def test_a_duck_document_from_a_newer_build_is_refused():
    with pytest.raises(ValueError, match="newer"):
        upcast_duck_doc({}, version=99)


def test_events_get_a_sequence_per_stream_and_a_global_cursor(store):
    first = store.events.append("match:a", [("MatchStarted", {"match_id": "a"})], NOW)
    store.events.append("match:b", [("MatchStarted", {"match_id": "b"})], NOW)
    more = store.events.append("match:a", [("X", {}), ("Y", {})], NOW)

    assert [e.seq for e in first + more] == [1, 2, 3]
    assert more[-1].cursor == 4
    only_a = store.events.read(["match:a"], after=0, limit=10)
    assert [e.type for e in only_a] == ["MatchStarted", "X", "Y"]
    assert [e.type for e in store.events.read(["match:a", "match:b"], after=1, limit=2)] == [
        "MatchStarted",
        "X",
    ]
    assert only_a[0].data == {"match_id": "a"}


def test_atomic_block_commits_everything_or_nothing(store):
    with pytest.raises(RuntimeError), store.atomic():
        store.ducks.add(a_duck())
        store.events.append("duck:duck_1", [("DuckHatched", {})], NOW)
        raise RuntimeError("boom")

    assert store.ducks.get("duck_1") is None
    assert store.events.read(["duck:duck_1"], 0, 10) == []

    with store.atomic():
        store.ducks.add(a_duck())
        store.events.append("duck:duck_1", [("DuckHatched", {})], NOW)

    assert store.ducks.get("duck_1") is not None
    assert len(store.events.read(["duck:duck_1"], 0, 10)) == 1


@pytest.mark.parametrize(
    "arena",
    [
        Arena(EngineSettings("stockfish"), BULLET, seed=7),
        Arena(EngineSettings("stockfish", hash_mb=32), NodesLimit(50_000), seed=2**53 - 1, games=4),
    ],
)
def test_match_round_trips_with_its_arena_snapshot(store, arena):
    match = a_match(arena)

    store.matches.add_match(match)
    store.matches.set_match_state("mat_1", "finished", NOW, {"duck_1": 1.5, "duck_2": 0.5})

    loaded = store.matches.get_match("mat_1")
    assert loaded.arena == arena
    assert loaded == replace(
        match, state="finished", finished_at=NOW, scores={"duck_1": 1.5, "duck_2": 0.5}
    )
    assert store.matches.list_matches(DEFAULT_PROFILE_ID, 10) == [loaded]


def test_game_and_moves_round_trip_and_track_clocks(store):
    store.matches.add_match(a_match())
    game = GameRecord(
        "game_1", "mat_1", 0, "duck_1", "duck_2", 99, "startfen", "running", 60_000, 60_000, NOW
    )
    move = MoveRecord(
        "game_1", 1, "white", "e2e4", "e4", "engine", 30, None, 1000, 8, 1500, 58_480, "fen", 4
    )

    store.matches.add_game(game)
    store.matches.add_move(move, 58_480, 60_000)
    store.matches.finish_game("game_1", "1-0", "checkmate", "1. e4 1-0", NOW)

    loaded = store.matches.get_game("game_1")
    assert (loaded.white_clock_ms, loaded.black_clock_ms) == (58_480, 60_000)
    assert (loaded.state, loaded.result, loaded.pgn) == ("finished", "1-0", "1. e4 1-0")
    assert store.matches.list_moves("game_1") == [move]
    assert store.matches.list_games("mat_1") == [loaded]


def test_jobs_round_trip_and_unfinished_ones_are_listed(store):
    job = JobRecord("job_1", "match", "running", {"match_id": "mat_1"}, 1, 4, NOW, NOW)

    store.jobs.add(job)

    assert store.jobs.get("job_1") == job
    assert store.jobs.list_unfinished() == [job]
    store.jobs.save(replace(job, state="succeeded", done=4, finished_at=NOW))
    assert store.jobs.list_unfinished() == []
    assert store.jobs.get("job_1").finished


def test_ratings_are_kept_per_context_with_history(store):
    from duckgambit.domain.arena import rating_context

    store.ducks.add(a_duck())
    context = rating_context(a_match().arena, "19", "abc123", "decision-1", "balance-1")
    store.ratings.save_context(context, NOW)
    store.ratings.save_context(context, NOW)

    assert store.ratings.get("duck_1", context.id, "game") is None
    store.ratings.save(
        RatingRecord("duck_1", context.id, "game", Rating(1510.5, 300.0, 0.06, 1), NOW), "game_1"
    )
    store.ratings.save(
        RatingRecord("duck_1", context.id, "game", Rating(1522.0, 280.0, 0.06, 2), NOW), "game_2"
    )

    assert store.ratings.get("duck_1", context.id, "game") == Rating(1522.0, 280.0, 0.06, 2)
    assert len(store.ratings.list_for_duck("duck_1")) == 1


def test_engine_profiles_are_saved_by_name(store):
    store.engine_profiles.save(EngineProfile("stockfish", "Casual", 50_000, 3, 16), NOW)
    store.engine_profiles.save(EngineProfile("stockfish", "Casual", 60_000, 3, 16), NOW)

    assert store.engine_profiles.list_for("stockfish") == [
        EngineProfile("stockfish", "Casual", 60_000, 3, 16)
    ]
