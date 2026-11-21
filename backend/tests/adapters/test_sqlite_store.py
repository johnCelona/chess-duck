import json
import sqlite3
from dataclasses import replace

import chess
import pytest

from conftest import NOW
from duckgambit.adapters.sqlite.data_steps import backfill_move_position_keys
from duckgambit.adapters.sqlite.database import Database, SchemaTooNewError, available_migrations
from duckgambit.adapters.sqlite.store import DEFAULT_PROFILE_ID, SqliteStore, upcast_duck_doc
from duckgambit.domain.arena import BULLET, Arena, EngineSettings, NodesLimit
from duckgambit.domain.chessutil import position_key
from duckgambit.domain.duck import hatch
from duckgambit.domain.knowledge import Knowledge, PuzzleMemoryEntry, RepertoireEntry
from duckgambit.domain.rating import Rating
from duckgambit.services.records import (
    EngineProfile,
    GameRecord,
    JobRecord,
    MatchRecord,
    MoveRecord,
    PositionMove,
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


def test_a_duck_keeps_the_egg_seed_it_hatched_from(store):
    duck, _ = hatch(
        duck_id="duck_1", profile_id=DEFAULT_PROFILE_ID, name="Eggbert", now=NOW, egg_seed=42
    )

    store.ducks.add(duck)

    assert store.ducks.get("duck_1") == duck
    assert store.ducks.get("duck_1").egg_seed == 42


def test_a_version_1_duck_document_reads_as_a_duck_without_an_egg(store):
    duck = a_duck()
    store.ducks.add(duck)
    with store.database.tx() as tx:
        doc = json.loads(tx.execute("SELECT doc FROM ducks WHERE id = 'duck_1'").fetchone()[0])
        del doc["egg_seed"]
        tx.execute(
            "UPDATE ducks SET doc = ?, doc_version = 1 WHERE id = 'duck_1'", (json.dumps(doc),)
        )

    loaded = store.ducks.get("duck_1")

    assert loaded == duck
    assert loaded.egg_seed is None


def test_the_active_duck_is_saved_on_the_profile(store):
    store.ducks.add(a_duck("duck_1"))
    store.ducks.add(a_duck("duck_2", "Bill"))
    assert store.profiles.active_duck(DEFAULT_PROFILE_ID) is None

    store.profiles.set_active_duck(DEFAULT_PROFILE_ID, "duck_2")

    assert store.profiles.active_duck(DEFAULT_PROFILE_ID) == "duck_2"
    assert store.profiles.name(DEFAULT_PROFILE_ID) == "Local player"


def test_a_version_2_database_upgrades_with_no_active_duck_and_keeps_its_ducks(tmp_path):
    path = tmp_path / "v2.db"
    assert Database(path).migrate(NOW, target=2) == [1, 2]
    old = SqliteStore(path)
    old.profiles.ensure_default(NOW)
    old.ducks.add(a_duck())
    old.close()

    store = SqliteStore(path)
    assert store.migrate(NOW) == [3]

    assert (tmp_path / "v2.db.bak-v2").exists()
    assert store.ducks.get("duck_1") == a_duck()
    assert store.profiles.active_duck(DEFAULT_PROFILE_ID) is None
    store.close()


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
        "game_1", 1, "white", "e2e4", "e4", "engine", 30, None, 1000, 8, 1500, 58_480, "fen", 4, "k"
    )

    store.matches.add_game(game)
    store.matches.add_move(move, 58_480, 60_000)
    store.matches.finish_game("game_1", "1-0", "checkmate", "1. e4 1-0", NOW)

    loaded = store.matches.get_game("game_1")
    assert (loaded.white_clock_ms, loaded.black_clock_ms) == (58_480, 60_000)
    assert (loaded.state, loaded.result, loaded.pgn) == ("finished", "1-0", "1. e4 1-0")
    assert store.matches.list_moves("game_1") == [move]
    assert store.matches.list_games("mat_1") == [loaded]


START = chess.STARTING_FEN
OPENING = ("e2e4", "e7e5", "g1f3", "b8c6")


def expected_keys(initial_fen, moves):
    board = chess.Board(initial_fen)
    keys = []
    for uci in moves:
        keys.append(position_key(board))
        board.push_uci(uci)
    return keys


def write_v1_game(connection, game_id, moves, initial_fen=START, idx=0):
    """Insert a game and its moves the way a version-1 build did: no position keys."""
    connection.execute(
        "INSERT INTO games (id, match_id, idx, white_duck_id, black_duck_id, seed, initial_fen,"
        " state, started_at) VALUES (?, 'mat_1', ?, 'duck_1', 'duck_2', 1, ?, 'finished', ?)",
        (game_id, idx, initial_fen, NOW),
    )
    for ply, uci in enumerate(moves, start=1):
        connection.execute(
            "INSERT INTO moves (game_id, ply, color, uci, san, source, nodes, depth, think_ms,"
            " fen_after, event_seq) VALUES (?, ?, ?, ?, ?, 'engine', 0, 0, 0, 'fen', ?)",
            (game_id, ply, "white" if ply % 2 else "black", uci, uci, ply),
        )


def test_a_version_1_database_upgrades_keeps_its_data_and_backfills_position_keys(tmp_path):
    path = tmp_path / "old.db"
    assert Database(path).migrate(NOW, target=1) == [1]
    old = SqliteStore(path)
    old.profiles.ensure_default(NOW)
    old.matches.add_match(a_match())
    with old.database.tx() as tx:
        write_v1_game(tx, "game_1", OPENING)
        # A corrupt game: ply 3 is illegal, so plies 1 and 2 get keys and 3 on stays NULL.
        write_v1_game(tx, "game_bad", ("d2d4", "d7d5", "e1e8", "g8f6"), idx=1)
    old.close()

    store = SqliteStore(path)
    assert store.migrate(NOW)[0] == 2  # later migrations follow in the same run

    assert (tmp_path / "old.db.bak-v1").exists()
    moves = store.matches.list_moves("game_1")
    assert [m.uci for m in moves] == list(OPENING)
    assert [m.position_key for m in moves] == expected_keys(START, OPENING)
    assert moves[0].position_key == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
    bad = store.matches.list_moves("game_bad")
    assert [m.position_key is not None for m in bad] == [True, True, False, False]
    assert store.matches.get_match("mat_1") is not None
    store.close()


def test_the_position_key_backfill_is_idempotent_and_follows_the_initial_fen(tmp_path):
    from_fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    store = SqliteStore(tmp_path / "steps.db")
    store.migrate(NOW)
    store.profiles.ensure_default(NOW)
    store.matches.add_match(a_match())
    with store.database.tx() as tx:
        write_v1_game(tx, "game_1", ("f1b5", "a7a6", "b5a4"), initial_fen=from_fen)

        assert backfill_move_position_keys(tx) == 3
        assert backfill_move_position_keys(tx) == 0

    keys = [m.position_key for m in store.matches.list_moves("game_1")]
    assert keys == expected_keys(from_fen, ("f1b5", "a7a6", "b5a4"))
    store.close()


def test_moves_at_position_finds_what_each_duck_played_there(store):
    store.matches.add_match(a_match())
    with store.database.tx() as tx:
        write_v1_game(tx, "game_1", ("e2e4", "e7e5"))
        write_v1_game(tx, "game_2", ("d2d4", "d7d5"), idx=1)
        # Colours swap: duck_2 has white here and opens 1. e4, reaching the same key.
        write_v1_game(tx, "game_3", ("e2e4", "c7c5"), idx=2)
        tx.execute(
            "UPDATE games SET white_duck_id = 'duck_2', black_duck_id = 'duck_1',"
            " started_at = '2026-11-22T00:00:00Z' WHERE id = 'game_3'"
        )
        tx.execute("UPDATE games SET result = '1-0' WHERE id = 'game_1'")
        backfill_move_position_keys(tx)

    start = position_key(chess.Board())
    after_e4 = expected_keys(START, ("e2e4", "e7e5"))[1]

    at_start = store.matches.moves_at_position(start)
    assert [(p.game_id, p.duck_id, p.uci) for p in at_start] == [
        ("game_3", "duck_2", "e2e4"),  # newest game first
        ("game_2", "duck_1", "d2d4"),
        ("game_1", "duck_1", "e2e4"),
    ]
    assert at_start[-1] == PositionMove(
        "game_1", "mat_1", 1, "white", "duck_1", "e2e4", "e2e4", "engine", None, None, "1-0"
    )
    replies = store.matches.moves_at_position(after_e4, duck_id="duck_1")
    assert [(p.game_id, p.uci, p.color) for p in replies] == [("game_3", "c7c5", "black")]
    by_duck_2 = store.matches.moves_at_position(after_e4, duck_id="duck_2")
    assert [(p.game_id, p.uci) for p in by_duck_2] == [("game_1", "e7e5")]
    assert len(store.matches.moves_at_position(start, limit=1)) == 1
    assert store.matches.moves_at_position("no such position w - -") == []


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
