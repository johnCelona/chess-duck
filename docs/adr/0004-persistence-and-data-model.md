# ADR-0004 · Persistence and data model

Status: Accepted (John, 2026-11-21) · 2026-11-21

## Context

Nothing is persisted today except loose profile JSON files with no version, written inside the source tree. The product is local-first, single-user per machine, and must also run as a packaged sidecar (ADR-0003).

## Options

| Option | For | Against |
| --- | --- | --- |
| JSON files per entity | Trivial, human-readable | No transactions, no queries (standings, rating history, "all games of this duck"), concurrent writers corrupt files |
| SQLite, stdlib `sqlite3`, numbered SQL migrations | Zero dependencies, one file, transactional, ships in Python, trivial to bundle | We write our own 40-line migrator and repositories |
| SQLite through SQLAlchemy 2 + Alembic | Mature migrations, portable to Postgres | Two heavy dependencies and an ORM whose models tend to leak into the domain; overkill for one local file |
| Postgres | Needed if hosted | Not local-first |

## Decision

**SQLite with the standard library driver and forward-only numbered SQL migrations.** Repositories are Protocols defined in `services`; `adapters/sqlite` implements them; an in-memory implementation backs unit tests. If a hosted mode ever needs Postgres, it is a second adapter behind the same ports.

Mechanics:

- One file, `<data dir>/duckgambit.db`, WAL mode, `foreign_keys=ON`.
- Migrations are `adapters/sqlite/migrations/NNNN_name.sql`, applied in order inside a transaction at startup, recorded in `schema_migrations`, mirrored to `PRAGMA user_version`. A database newer than the code refuses to open. The file is copied to `duckgambit.db.bak-<version>` before any migration runs.
- Repositories are synchronous and open a connection per unit of work. Async callers (the match runner) hop to a thread.
- **Shape rule:** columns for identity, ownership and anything queried or joined; a `doc` JSON column for nested values that are only read whole (stats, care, cosmetics, arena settings, event data). Every JSON document carries `schemaVersion` and is upgraded by a chain of pure `upcast_vN` functions on read.

### Entities

| Entity | Storage | Notes |
| --- | --- | --- |
| Profile | `profiles` | The local player. One row now; the foreign key exists so accounts are not a rewrite |
| Duck | `ducks` (id, profile_id, name, created_at, doc) | `doc`: avatar and cosmetics, growth (stage, level, xp, stat budget), stats, care state, principles, motifs |
| Repertoire | `repertoire_entries` (duck_id, colour, position_key, move_uci, weight, source, lesson_id) | Separate table because "learn from my games" can add thousands of rows. `position_key` is the first four FEN fields with en passant only when a capture is legal |
| Puzzle memory | `puzzle_memory` (duck_id, position_key, move_uci, lesson_id) | Written by teach-the-fix |
| Lesson log | `lessons` (append-only) | Every knowledge row points at the lesson that created it, so knowledge is explainable and reversible |
| EngineProfile | `engine_profiles` | Replaces the JSON files; options are validated against the allowlist before storing (today a saved profile can contain `EvalFile` or `Debug Log File`) |
| Rating context | `rating_contexts` (id = hash of its fields) | Engine id, version and binary sha256; limit type; `virtualNps`; threads; hash; multiPV; decision-layer version; balance-config version |
| Rating | `ratings` (duck_id, context_id, kind) and `rating_history` | `kind` is `game` or `puzzle`. Value, deviation, volatility, games, provisional flag |
| Match | `matches` | Arena settings snapshot, seed, state, participants |
| Game | `games` | match_id, colours, seed, result, termination, context_id, final PGN text |
| Move | `moves` (game_id, ply) | Compact row: uci, san, source, eval, nodes, think ms, clock after, and the `seq` of its `MoveChosen` event. Candidate detail lives once, in the event |
| Event | `events` (cursor autoincrement, stream, seq, type, recorded_at, data) | Unique (stream, seq). Feeds SSE, replay and the thinking panel |
| Job | `jobs` | kind, params, state, progress, seed, error, timestamps (ADR-0007) |
| Tournament | `tournaments`, `tournament_rounds`, `pairings` | Created by its session (M3) |
| Puzzle pack | Files on disk (ADR-0009) plus `puzzle_attempts` | Packs are read-only data, not rows |
| Review | `reviews`, `annotations` | Created by its session (M5) |
| Integration link | `integration_links` | Provider, external user id and name, scopes, linked_at. **Never the token** (ADR-0010) |

M0 creates only the tables the walking skeleton uses: profiles, ducks, repertoire_entries, engine_profiles, rating_contexts, ratings, rating_history, matches, games, moves, events, jobs. The rest arrive as migrations in their sessions; that is what migrations are for.

### Duck file

A portable export, `*.duck.json`:

```json
{
  "format": "duck-gambit.duck",
  "schemaVersion": 1,
  "exportedAt": "2026-11-21T18:00:00Z",
  "exportedBy": { "app": "duck-gambit", "version": "0.1.0" },
  "duck": { "id": "duck_…", "name": "…", "avatar": {}, "growth": {}, "stats": {}, "knowledge": { "repertoire": {}, "principles": [], "motifs": {}, "puzzleMemory": [], "lessonLog": [] }, "ratings": {} }
}
```

Import rules: validate against the schema, upcast old versions, **re-check the stat budget against the level** (a hand-edited file cannot exceed it), assign a new local id and keep the original as `origin`, reset care state, and treat imported ratings as a claim: the value is kept but the deviation is reset to provisional, because a rating only means something in the local rating context. Files are size-capped and never executed.

### Game record

Three views of one game, each with one job: `moves` rows for queries and review; the event log for replay and the thinking panel; a PGN string for humans and other tools. PGN uses the standard `[%eval]` and `[%clk]` comment annotations plus `Seed` and `RatingContext` headers, and is covered by a golden-file test.

## Consequences

- No ORM: SQL is written by hand in one adapter, which is a feature for a schema this small and keeps the domain free of persistence types.
- Event rows with full candidate lists cost roughly 1 to 2 KB per ply. A 1,000-game tournament is on the order of 150 MB if recorded in full, so the arena gets a `recordDetail: full | compact` setting when tournaments arrive (M3).
- Forward-only migrations mean a bad migration is fixed by another migration; the automatic backup is the undo.

## Not building yet

- Accounts, sync, cloud saves, multi-profile UI.
- Postgres adapter.
- Duck-file signing or anti-tamper beyond the budget check (anti-cheat is out of scope through M5).
- Event-log compaction and retention policy.
- Tables for tournaments, puzzles and reviews.
