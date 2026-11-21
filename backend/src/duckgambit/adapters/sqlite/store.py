"""SQLite implementations of the repository ports (ADR-0004).

Columns hold identity and anything queried; JSON documents hold nested values that are
read whole. Every document carries a schema version and is upgraded on read.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from duckgambit.adapters.sqlite.database import Database
from duckgambit.domain.arena import RatingContext, arena_from_doc
from duckgambit.domain.duck import DUCK_SCHEMA_VERSION, Avatar, Care, Duck, Growth
from duckgambit.domain.knowledge import Knowledge, PuzzleMemoryEntry, RepertoireEntry
from duckgambit.domain.rating import Rating
from duckgambit.services.records import (
    EngineProfile,
    Envelope,
    GameRecord,
    JobRecord,
    MatchRecord,
    MoveRecord,
    RatingRecord,
)

DEFAULT_PROFILE_ID = "prof_local"


def _dump(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def upcast_duck_doc(doc: dict[str, Any], version: int) -> dict[str, Any]:
    """Bring a stored duck document up to the current shape. Add a step per new version."""
    if version > DUCK_SCHEMA_VERSION:
        raise ValueError(f"Duck document version {version} is newer than this build supports")
    # version 1 is current; future steps go here: `if version < 2: doc = _v1_to_v2(doc)`
    return doc


class _Repository:
    def __init__(self, database: Database) -> None:
        self._db = database


class SqliteProfiles(_Repository):
    def ensure_default(self, now: str) -> str:
        with self._db.tx() as tx:
            tx.execute(
                "INSERT OR IGNORE INTO profiles (id, name, created_at) VALUES (?, ?, ?)",
                (DEFAULT_PROFILE_ID, "Local player", now),
            )
        return DEFAULT_PROFILE_ID


class SqliteDucks(_Repository):
    def add(self, duck: Duck) -> None:
        doc = {
            "avatar": asdict(duck.avatar),
            "growth": asdict(duck.growth),
            "stats": duck.stats,
            "care": asdict(duck.care),
            "principles": list(duck.knowledge.principles),
            "motifs": duck.knowledge.motifs,
        }
        with self._db.tx() as tx:
            tx.execute(
                "INSERT INTO ducks (id, profile_id, name, created_at, origin, doc_version, doc)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    duck.id,
                    duck.profile_id,
                    duck.name,
                    duck.created_at,
                    duck.origin,
                    duck.schema_version,
                    _dump(doc),
                ),
            )
            tx.executemany(
                "INSERT INTO repertoire_entries"
                " (duck_id, color, position_key, move_uci, weight, source, lesson_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (duck.id, e.color, e.position_key, e.move, e.weight, e.source, e.lesson_id)
                    for e in duck.knowledge.repertoire
                ],
            )
            tx.executemany(
                "INSERT INTO puzzle_memory (duck_id, position_key, move_uci, lesson_id)"
                " VALUES (?, ?, ?, ?)",
                [
                    (duck.id, e.position_key, e.move, e.lesson_id)
                    for e in duck.knowledge.puzzle_memory
                ],
            )

    def get(self, duck_id: str) -> Duck | None:
        with self._db.tx() as tx:
            row = tx.execute("SELECT * FROM ducks WHERE id = ?", (duck_id,)).fetchone()
            return self._load(tx, row) if row else None

    def list_for(self, profile_id: str) -> list[Duck]:
        with self._db.tx() as tx:
            rows = tx.execute(
                "SELECT * FROM ducks WHERE profile_id = ? ORDER BY created_at, id", (profile_id,)
            ).fetchall()
            return [self._load(tx, row) for row in rows]

    def _load(self, tx: sqlite3.Connection, row: sqlite3.Row) -> Duck:
        doc = upcast_duck_doc(json.loads(row["doc"]), row["doc_version"])
        repertoire = tuple(
            RepertoireEntry(
                r["color"],
                r["position_key"],
                r["move_uci"],
                r["weight"],
                r["source"],
                r["lesson_id"],
            )
            for r in tx.execute(
                "SELECT * FROM repertoire_entries WHERE duck_id = ? ORDER BY id", (row["id"],)
            )
        )
        memory = tuple(
            PuzzleMemoryEntry(r["position_key"], r["move_uci"], r["lesson_id"])
            for r in tx.execute(
                "SELECT * FROM puzzle_memory WHERE duck_id = ? ORDER BY id", (row["id"],)
            )
        )
        avatar = doc["avatar"]
        return Duck(
            id=row["id"],
            profile_id=row["profile_id"],
            name=row["name"],
            avatar=Avatar(avatar["species"], avatar["skin"], tuple(avatar["accessories"])),
            growth=Growth(**doc["growth"]),
            stats=dict(doc["stats"]),
            care=Care(**doc["care"]),
            knowledge=Knowledge(
                repertoire=repertoire,
                principles=tuple(doc["principles"]),
                motifs=dict(doc["motifs"]),
                puzzle_memory=memory,
            ),
            created_at=row["created_at"],
            origin=row["origin"],
        )


class SqliteEvents(_Repository):
    def append(
        self, stream: str, events: Sequence[tuple[str, dict[str, Any]]], recorded_at: str
    ) -> list[Envelope]:
        envelopes = []
        with self._db.tx() as tx:
            seq = tx.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM events WHERE stream = ?", (stream,)
            ).fetchone()[0]
            for event_type, data in events:
                seq += 1
                cursor = tx.execute(
                    "INSERT INTO events (stream, seq, type, recorded_at, data)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (stream, seq, event_type, recorded_at, _dump(data)),
                ).lastrowid
                assert cursor is not None
                envelopes.append(Envelope(cursor, stream, seq, event_type, recorded_at, data))
        return envelopes

    def read(self, streams: Sequence[str], after: int, limit: int) -> list[Envelope]:
        if not streams:
            return []
        marks = ",".join("?" for _ in streams)
        with self._db.tx() as tx:
            rows = tx.execute(
                f"SELECT * FROM events WHERE stream IN ({marks}) AND cursor > ?"  # noqa: S608
                " ORDER BY cursor LIMIT ?",
                (*streams, after, limit),
            ).fetchall()
        return [
            Envelope(
                r["cursor"],
                r["stream"],
                r["seq"],
                r["type"],
                r["recorded_at"],
                json.loads(r["data"]),
            )
            for r in rows
        ]


class SqliteMatches(_Repository):
    def add_match(self, match: MatchRecord) -> None:
        with self._db.tx() as tx:
            tx.execute(
                "INSERT INTO matches (id, profile_id, mode, rated, state, arena, duck_ids, scores,"
                " context_id, job_id, created_at, finished_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    match.id,
                    match.profile_id,
                    match.mode,
                    int(match.rated),
                    match.state,
                    _dump(asdict(match.arena)),
                    _dump(list(match.duck_ids)),
                    _dump(match.scores),
                    match.context_id,
                    match.job_id,
                    match.created_at,
                    match.finished_at,
                ),
            )

    @staticmethod
    def _match(row: sqlite3.Row) -> MatchRecord:
        return MatchRecord(
            id=row["id"],
            profile_id=row["profile_id"],
            duck_ids=tuple(json.loads(row["duck_ids"])),
            arena=arena_from_doc(json.loads(row["arena"])),
            mode=row["mode"],
            rated=bool(row["rated"]),
            state=row["state"],
            context_id=row["context_id"],
            job_id=row["job_id"],
            created_at=row["created_at"],
            finished_at=row["finished_at"],
            scores=json.loads(row["scores"]),
        )

    def get_match(self, match_id: str) -> MatchRecord | None:
        with self._db.tx() as tx:
            row = tx.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        return self._match(row) if row else None

    def list_matches(self, profile_id: str, limit: int) -> list[MatchRecord]:
        with self._db.tx() as tx:
            rows = tx.execute(
                "SELECT * FROM matches WHERE profile_id = ? ORDER BY created_at DESC, id DESC"
                " LIMIT ?",
                (profile_id, limit),
            ).fetchall()
        return [self._match(row) for row in rows]

    def set_match_state(
        self,
        match_id: str,
        state: str,
        finished_at: str | None = None,
        scores: dict[str, float] | None = None,
    ) -> None:
        with self._db.tx() as tx:
            tx.execute(
                "UPDATE matches SET state = ?, finished_at = COALESCE(?, finished_at),"
                " scores = COALESCE(?, scores) WHERE id = ?",
                (state, finished_at, _dump(scores) if scores is not None else None, match_id),
            )

    def add_game(self, game: GameRecord) -> None:
        with self._db.tx() as tx:
            tx.execute(
                "INSERT INTO games (id, match_id, idx, white_duck_id, black_duck_id, seed,"
                " initial_fen, state, white_clock_ms, black_clock_ms, started_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    game.id,
                    game.match_id,
                    game.index,
                    game.white_duck_id,
                    game.black_duck_id,
                    game.seed,
                    game.initial_fen,
                    game.state,
                    game.white_clock_ms,
                    game.black_clock_ms,
                    game.started_at,
                ),
            )

    @staticmethod
    def _game(row: sqlite3.Row) -> GameRecord:
        return GameRecord(
            id=row["id"],
            match_id=row["match_id"],
            index=row["idx"],
            white_duck_id=row["white_duck_id"],
            black_duck_id=row["black_duck_id"],
            seed=row["seed"],
            initial_fen=row["initial_fen"],
            state=row["state"],
            white_clock_ms=row["white_clock_ms"],
            black_clock_ms=row["black_clock_ms"],
            started_at=row["started_at"],
            result=row["result"],
            termination=row["termination"],
            pgn=row["pgn"],
            finished_at=row["finished_at"],
        )

    def get_game(self, game_id: str) -> GameRecord | None:
        with self._db.tx() as tx:
            row = tx.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return self._game(row) if row else None

    def list_games(self, match_id: str) -> list[GameRecord]:
        with self._db.tx() as tx:
            rows = tx.execute(
                "SELECT * FROM games WHERE match_id = ? ORDER BY idx", (match_id,)
            ).fetchall()
        return [self._game(row) for row in rows]

    def add_move(
        self, move: MoveRecord, white_clock_ms: int | None, black_clock_ms: int | None
    ) -> None:
        with self._db.tx() as tx:
            tx.execute(
                "INSERT INTO moves (game_id, ply, color, uci, san, source, cp, mate, nodes, depth,"
                " think_ms, clock_ms, fen_after, event_seq)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    move.game_id,
                    move.ply,
                    move.color,
                    move.uci,
                    move.san,
                    move.source,
                    move.cp,
                    move.mate,
                    move.nodes,
                    move.depth,
                    move.think_ms,
                    move.clock_ms,
                    move.fen_after,
                    move.event_seq,
                ),
            )
            tx.execute(
                "UPDATE games SET white_clock_ms = ?, black_clock_ms = ? WHERE id = ?",
                (white_clock_ms, black_clock_ms, move.game_id),
            )

    def list_moves(self, game_id: str) -> list[MoveRecord]:
        with self._db.tx() as tx:
            rows = tx.execute(
                "SELECT * FROM moves WHERE game_id = ? ORDER BY ply", (game_id,)
            ).fetchall()
        return [MoveRecord(**dict(row)) for row in rows]

    def finish_game(
        self, game_id: str, result: str, termination: str, pgn: str, finished_at: str
    ) -> None:
        with self._db.tx() as tx:
            tx.execute(
                "UPDATE games SET state = 'finished', result = ?, termination = ?, pgn = ?,"
                " finished_at = ? WHERE id = ?",
                (result, termination, pgn, finished_at, game_id),
            )


class SqliteJobs(_Repository):
    def add(self, job: JobRecord) -> None:
        with self._db.tx() as tx:
            tx.execute(
                "INSERT INTO jobs (id, kind, state, params, done, total, error_code, error_detail,"
                " created_at, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._values(job),
            )

    @staticmethod
    def _values(job: JobRecord) -> tuple[Any, ...]:
        return (
            job.id,
            job.kind,
            job.state,
            _dump(job.params),
            job.done,
            job.total,
            job.error_code,
            job.error_detail,
            job.created_at,
            job.started_at,
            job.finished_at,
        )

    @staticmethod
    def _job(row: sqlite3.Row) -> JobRecord:
        values = dict(row)
        values["params"] = json.loads(values["params"])
        return JobRecord(**values)

    def get(self, job_id: str) -> JobRecord | None:
        with self._db.tx() as tx:
            row = tx.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job(row) if row else None

    def save(self, job: JobRecord) -> None:
        with self._db.tx() as tx:
            tx.execute(
                "UPDATE jobs SET kind = ?, state = ?, params = ?, done = ?, total = ?,"
                " error_code = ?, error_detail = ?, created_at = ?, started_at = ?,"
                " finished_at = ? WHERE id = ?",
                (*self._values(job)[1:], job.id),
            )

    def list_unfinished(self) -> list[JobRecord]:
        with self._db.tx() as tx:
            rows = tx.execute(
                "SELECT * FROM jobs WHERE state IN ('queued', 'running') ORDER BY created_at"
            ).fetchall()
        return [self._job(row) for row in rows]


class SqliteRatings(_Repository):
    def save_context(self, context: RatingContext, now: str) -> None:
        with self._db.tx() as tx:
            tx.execute(
                "INSERT OR IGNORE INTO rating_contexts (id, doc, created_at) VALUES (?, ?, ?)",
                (context.id, _dump(asdict(context)), now),
            )

    def get(self, duck_id: str, context_id: str, kind: str) -> Rating | None:
        with self._db.tx() as tx:
            row = tx.execute(
                "SELECT * FROM ratings WHERE duck_id = ? AND context_id = ? AND kind = ?",
                (duck_id, context_id, kind),
            ).fetchone()
        if row is None:
            return None
        return Rating(row["value"], row["deviation"], row["volatility"], row["games"])

    def save(self, record: RatingRecord, game_id: str | None) -> None:
        rating = record.rating
        values = (rating.value, rating.deviation, rating.volatility, rating.games)
        with self._db.tx() as tx:
            tx.execute(
                "INSERT INTO ratings (duck_id, context_id, kind, value, deviation, volatility,"
                " games, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (duck_id, context_id, kind) DO UPDATE SET value = excluded.value,"
                " deviation = excluded.deviation, volatility = excluded.volatility,"
                " games = excluded.games, updated_at = excluded.updated_at",
                (record.duck_id, record.context_id, record.kind, *values, record.updated_at),
            )
            tx.execute(
                "INSERT INTO rating_history (duck_id, context_id, kind, value, deviation,"
                " volatility, games, game_id, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.duck_id,
                    record.context_id,
                    record.kind,
                    *values,
                    game_id,
                    record.updated_at,
                ),
            )

    def list_for_duck(self, duck_id: str) -> list[RatingRecord]:
        with self._db.tx() as tx:
            rows = tx.execute(
                "SELECT * FROM ratings WHERE duck_id = ? ORDER BY updated_at DESC, context_id",
                (duck_id,),
            ).fetchall()
        return [
            RatingRecord(
                r["duck_id"],
                r["context_id"],
                r["kind"],
                Rating(r["value"], r["deviation"], r["volatility"], r["games"]),
                r["updated_at"],
            )
            for r in rows
        ]


class SqliteEngineProfiles(_Repository):
    def list_for(self, engine_id: str) -> list[EngineProfile]:
        with self._db.tx() as tx:
            rows = tx.execute(
                "SELECT * FROM engine_profiles WHERE engine_id = ? ORDER BY name", (engine_id,)
            ).fetchall()
        return [
            EngineProfile(engine_id=r["engine_id"], name=r["name"], **json.loads(r["doc"]))
            for r in rows
        ]

    def save(self, profile: EngineProfile, now: str) -> None:
        doc = {"nodes": profile.nodes, "multipv": profile.multipv, "hash_mb": profile.hash_mb}
        with self._db.tx() as tx:
            tx.execute(
                "INSERT INTO engine_profiles (engine_id, name, doc, created_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (engine_id, name) DO UPDATE SET doc = excluded.doc",
                (profile.engine_id, profile.name, _dump(doc), now),
            )


class SqliteStore:
    """The Store port backed by one SQLite file."""

    def __init__(self, path: Path) -> None:
        self.database = Database(path)
        self.profiles = SqliteProfiles(self.database)
        self.ducks = SqliteDucks(self.database)
        self.events = SqliteEvents(self.database)
        self.matches = SqliteMatches(self.database)
        self.jobs = SqliteJobs(self.database)
        self.ratings = SqliteRatings(self.database)
        self.engine_profiles = SqliteEngineProfiles(self.database)

    def migrate(self, applied_at: str) -> list[int]:
        applied = self.database.migrate(applied_at)
        self.database.hold_open()
        return applied

    def close(self) -> None:
        self.database.close()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        with self.database.tx():
            yield
