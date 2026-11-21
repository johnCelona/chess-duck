# Design 02 · Position memory at scale

Status: Proposal for future scope · 2026-11-21 · Touches ADR-0004 (persistence), ADR-0005 (decision layer), ADR-0006 (rating context), ADR-0008 (review)

John asked: *if ducks are going to learn openings and remember past mistakes, do we need much more complex SQL and databases, and is it worth it?*

Short answer: **the part that changes how a duck plays should stay small and simple. The part that needs scale is analysis and UI** (opening trees, mistake history, stats over many games). That part can be built incrementally on the SQLite file we already have. We do not need a second database engine before M6, and probably not after it. Section 2 explains the split, section 3 proposes the architecture, and section 4 lists what we can reuse.

---

## 0. Summary

1. **Two kinds of memory.** *Play memory* is what the decision layer reads: repertoire, puzzle memory, motifs. It must stay tiny, explainable, deterministic, and gated by the Memory stat. *Analysis memory* is what the player looks at: opening trees, "what my duck usually plays here", mistake history. It may be large, approximate and rebuildable. Only play memory affects strength or ratings.
2. **Analysis memory never feeds the decision layer directly.** A tree can *suggest* a repertoire change ("your duck scores 70% with Nf3 here, add it?"), but the change is applied as a `Lesson` through `apply_lesson` (ADR-0008 rule 3). So the duck's play depends only on versioned knowledge, never on query results that change every game.
3. **Shipped now (migration 0002):** `moves.position_key` (the key of the position *before* the move, using the same normalisation as repertoire and puzzle memory) plus the index `moves_by_position (position_key, game_id)`. Older rows are backfilled by a Python step that runs inside the migration transaction. `MatchRepository.moves_at_position(key, duck_id, limit)` answers "what was played here, in which game, with what result". This is the raw material for everything below.
4. **Next (M2, M5):** a per-profile **opening tree** table keyed by a 64-bit Zobrist hash with aggregated counts per (position, move, duck). It is built incrementally when a game finishes, and depth-capped. Also a **mistake card** table with Leitner scheduling, counted in sessions (design 01, section 3.6). Both stay in the same SQLite file.
5. **Later (M6, only if measured):** compact the event log (the real storage growth), and possibly use DuckDB *as a reader* of the same SQLite file for heavy analytics. No server, no second source of truth.
6. **Reuse:** python-chess's `zobrist_hash` and Polyglot reader (GPL-3.0, already a dependency) and the `lichess-org/chess-openings` names dataset (CC0, and its EPD column uses our exact key format). Borrow ideas, not code, from `lila-openingexplorer` (AGPL-3.0). Skip SCID's format.

---

## 1. What exists now and how a duck "remembers"

### 1.1 Stores

| Store | Table / location | Keyed by | Read by play? | Written by |
| --- | --- | --- | --- | --- |
| Repertoire | `repertoire_entries` (duck, color, position_key, move, weight, source, lesson_id) | exact position key | Yes: book step | Opening Drill, blunder fixes in the opening window, `apply_lesson` |
| Puzzle memory | `puzzle_memory` (duck, position_key, move, lesson_id), unique per (duck, key) | exact position key | Yes: memory step (`source = "memory"`) | teach-the-fix (ADR-0008) |
| Principles, motifs | `ducks.doc` JSON | rule id / motif name | Yes: style score | lessons, drills |
| Moves | `moves` (game, ply, uci, san, source, eval, nodes, clock, **position_key** since 0002) | (game_id, ply); index on position_key | No | match runner |
| Events | `events` (stream, seq, type, data JSON) | (stream, seq) | No | everything; `MoveChosen` holds full candidate lists |
| Games | `games` (seed, initial_fen, result, PGN) | id | No | match runner |

`position_key` is `board.epd(en_passant="legal")`: pieces, side to move, castling rights, and en passant only when a capture is legal. Move counters are ignored. So the same position reached by a different move order is the same key. That makes it **transposition-tolerant for exact matches**: a key lookup finds the position however it was reached.

### 1.2 How memory reaches a move today

`plan()` (ADR-0005) runs: puzzle memory (exact key) → repertoire (exact key, color) → forced move → engine search. Recall is a per-decision seeded draw against `book_recall_permille = 500 + 5 × memory` (capped at 1000). The runner loads each duck's whole `Knowledge` when the match job starts, and `book_moves` and `taught_move` are linear scans over in-memory tuples.

### 1.3 Honest limits

1. **Exact-position matching only.** A taught fix helps only in that exact position. Design 01 (section 3.7) already says it plainly: a middlegame position almost never recurs. Puzzle memory therefore pays off in openings, in lesson checks and in replays from a stored ply, and otherwise mainly through XP. Generalisation needs *guards* (motif-level penalties), which is a decision-layer feature, not a database one.
2. **No tree.** We store keys, not edges. There is no table that says "from position P, these moves were played N times with these results". With 0002 we can *compute* that per position with one indexed query. We still cannot cheaply walk a whole tree or aggregate across thousands of games without scanning `moves`.
3. **No aggregation and no cross-duck stats.** Win rates per opening, "this duck's most common mistake", and "how do all my ducks handle the Sicilian" all need group-bys over `moves` joined to `games`. That is fine at hundreds of games and gets slow and repetitive at tens of thousands.
4. **Event log growth.** ADR-0004 estimates 1 to 2 KB per ply for `MoveChosen` with candidates: an 80-ply game is 80 to 160 KB, and 1,000 games are 80 to 160 MB. This is by far the largest table and the first to need a policy. Position keys add about 10% (section 3.6).
5. **Knowledge is not snapshotted per game.** The arena is snapshotted into the match, but ducks are reloaded from the store when a match job starts or resumes. If a lesson lands between a cancel and a resume, the resumed game uses newer knowledge. Replaying an old game later also uses whatever the duck knows *now*. Today this is rare, but "remember mistakes" makes knowledge change often, so it will matter (section 3.5).
6. **SQLite is single-writer.** WAL lets readers run alongside one writer. All writes go through short `BEGIN IMMEDIATE` transactions with a 10 s busy timeout. A long backfill or tree rebuild inside one transaction would block the match runner. Bulk jobs must commit in batches.
7. **Linear in-memory lookups.** `book_moves` scans every repertoire row each ply. At 5,000 entries × 80 plies that is 400k comparisons per game: negligible. At a 50,000-row imported repertoire it is worth turning into a dict, which is a domain-only change with no schema impact.

---

## 2. Is it worth it?

### 2.1 What actually makes a duck stronger

Every duck searches with the same Stockfish. Strength differences come only from the decision layer:

| Lever | Effect on results | Needs scale? |
| --- | --- | --- |
| Node budget (Calculation, level) | Large: the main strength axis | No |
| Blunder tolerance (level, stage) | Large: how far below the best move the duck may wander | No |
| Repertoire hits | Real but bounded: book moves are instant (bullet clock) and avoid low-node opening slips. Only in the first ~10 to 15 moves | Hundreds to low thousands of rows per duck |
| Puzzle memory hits | Small in real play (exact recurrence is rare). Visible in lesson checks and replays | Dozens to hundreds of rows |
| Guards / motifs | Potentially general, unmeasured | Tiny maps |
| Opening tree statistics | **None directly.** Only through a suggestion the player accepts, which becomes repertoire | Can be large |
| Mistake history and stats | **None.** Presentation and motivation | Can be large |

So the memory that changes play is small by nature: a well-taught duck might have 500 to 2,000 repertoire rows. That fits in RAM and in one SQLite table with no tuning. The memory that grows with games played (trees, history, stats) is presentation. It is valuable for the game loop and for the player's learning, but it is not where strength comes from. We should say that honestly in the UI copy.

### 2.2 Should play memory read big tables?

No. If the decision layer read live aggregate statistics ("play the move that scored best in my last 200 games"):

- A move would depend on the order in which every earlier game finished. That is still deterministic in principle, but nobody can explain or reproduce it, and a resume after a crash could see different counts.
- Ratings would drift inside one rating context without any versioned input changing. ADR-0006 says anything that can change a move belongs in the context.
- The Memory stat would no longer budget what the duck knows. A duck that plays a lot would learn for free.

The recommended rule: **the tree proposes, a lesson disposes.** Aggregates live in analysis tables. Promoting a tree move into the repertoire is an explicit `Lesson` (kind `opening-from-games`) applied through `apply_lesson`, with a lesson id on the row and an undo path. If we ever want automatic learning ("the duck learns from its own games"), it is a scheduled job that *emits lessons* under a per-session cap tied to Memory. It is never a live query.

### 2.3 Recommendation by milestone

| Milestone | Build | Why then |
| --- | --- | --- |
| Now (done) | `moves.position_key` + index + `moves_at_position` | Every later feature needs "what was played here"; backfilling later costs more as games accumulate |
| M2 openings | Opening names from `lichess-org/chess-openings` (lookup by EPD key). A per-profile opening tree (section 3.2) limited to own games, depth ≤ 30 plies. "Suggest repertoire from my games" as a lesson. Dict index for repertoire lookups if rows exceed ~10k | Opening Drill needs names and "what does my duck usually play here" |
| M3 tournaments | `recordDetail: compact` for events (already planned in ADR-0004). Record a knowledge revision per game (section 3.5) | Tournaments are where event volume explodes and where replays matter |
| M5 review / Blunder Training | `drill_cards` table with Leitner boxes counted in sessions; mistakes keyed by position key plus Zobrist; "has my duck made this mistake before?" via `moves_at_position` | Design 01 B1; the scheduling already exists on paper |
| M6 Lichess import | Imported games feed the same tree (source `import`), batch-committed. Optional Polyglot `.bin` export of a duck's repertoire. Measure before adding DuckDB | Imports are the first time a profile can have 10k+ games |
| Not planned | A separate server database, a transposition graph, cross-profile stats | Not needed by a local single-player game |

---

## 3. Proposed architecture

### 3.1 Keys: one canonical position, two encodings

- **Knowledge key (exists):** `position_key(board)`, the EPD text. Human-readable, already used by repertoire, puzzle memory and duck files. It stays the canonical key for anything the decision layer reads.
- **Tree key (new):** a signed 64-bit integer from `chess.polyglot.zobrist_hash`, stored as SQLite `INTEGER` (8 bytes against ~55 bytes of text, and integer index compares are cheaper).

**Caveat, verified in python-chess 1.11.2 source:** `zobrist_hash` hashes the en passant file whenever a capturing pawn is *adjacent*, "legality of the potential capture is irrelevant" (Polyglot's rule). Our EPD key includes en passant only when the capture is *legal*. In rare positions (the capturing pawn is pinned) the two keys disagree: one EPD key maps to two hashes. Fix: compute the tree key from a normalised copy, in the domain:

```python
def tree_key(board: chess.Board) -> int:
    """Polyglot Zobrist hash of the position as position_key sees it (en passant only if legal)."""
    if board.ep_square is not None and not board.has_legal_en_passant():
        board = board.copy(stack=False)
        board.ep_square = None
    value = chess.polyglot.zobrist_hash(board)
    return value - (1 << 64) if value >= 1 << 63 else value  # fit SQLite's signed INTEGER
```

Checked on 2026-11-21 with python-chess 1.11.2. After `...d7d5`, with White's e5 pawn pinned along the fifth rank, the raw `zobrist_hash` differs from the same position set up without an en passant square. `position_key` and `tree_key` both treat the two as equal. The start position hashes to `0x463b96181691fc9c`, the published Polyglot reference key. A unit test should keep asserting that `tree_key` and `position_key` partition the same positions. With that normalisation, our tree keys equal standard Polyglot keys in every position where the en passant capture is legal or absent. Polyglot books therefore stay interoperable except in pinned-pawn edge cases.

**Collisions.** For n distinct positions the chance of any 64-bit collision is about n² / 2⁶⁵. For 1 million positions: 10¹² / 3.7 × 10¹⁹ ≈ 3 × 10⁻⁸. Lichess uses 96-bit keys only because it indexes ~500 billion positions. A collision would corrupt a displayed statistic, never a move, because the play path uses the EPD key.

### 3.2 Opening tree (analysis memory)

```sql
-- sketch, migration 00NN_opening_tree.sql
CREATE TABLE tree_edges (
    profile_id  TEXT    NOT NULL REFERENCES profiles (id),
    duck_id     TEXT    NOT NULL,              -- the duck that moved; '*' rows are not stored, sum instead
    tree_key    INTEGER NOT NULL,              -- tree_key(board before the move)
    move_uci    TEXT    NOT NULL,
    source      TEXT    NOT NULL,              -- 'match' | 'import' | 'sparring'
    games       INTEGER NOT NULL DEFAULT 0,
    wins        INTEGER NOT NULL DEFAULT 0,    -- from the mover's point of view
    draws       INTEGER NOT NULL DEFAULT 0,
    losses      INTEGER NOT NULL DEFAULT 0,
    last_game_id TEXT,
    PRIMARY KEY (profile_id, tree_key, duck_id, source, move_uci)
) WITHOUT ROWID;

CREATE TABLE tree_ingested (                   -- idempotency: each game counted once
    game_id     TEXT PRIMARY KEY,
    tree_version INTEGER NOT NULL,
    ingested_at TEXT NOT NULL
);
```

- **Incremental build.** When a game finishes (`_finish_game`, same transaction as the result), replay its first `TREE_MAX_PLY` plies (30 [PH]) and upsert one edge per ply: `INSERT ... ON CONFLICT DO UPDATE SET games = games + 1, ...`, then insert into `tree_ingested`. Imports run the same function in a job, committing every 200 games so the match runner is never blocked for long.
- **Why depth-capped.** After ~15 moves almost every game is unique, so deeper edges are mostly count-1 rows that cost space and tell the player nothing. Lichess makes the same observation and keeps positions seen once in a separate "cold" store (section 4). Below the cap, `moves_at_position` already answers "what happened here" from the raw moves.
- **Rebuildable.** The tree is derived data. A version bump (`tree_version`) means: drop the rows, clear `tree_ingested`, re-ingest in a background job. Nothing else depends on it.
- **Queries.** "Moves from here for this duck" is one primary-key range scan. Cross-duck stats are `GROUP BY move_uci` over the same range. No transposition graph is needed: keys are positions, so transpositions merge automatically. "Children" are found by pushing each move and hashing, which is a few microseconds in python-chess.

### 3.3 Mistake memory (Blunder Training)

```sql
CREATE TABLE drill_cards (
    id            TEXT PRIMARY KEY,
    duck_id       TEXT NOT NULL REFERENCES ducks (id) ON DELETE CASCADE,
    position_key  TEXT NOT NULL,      -- EPD: what puzzle_memory will be keyed by
    tree_key      INTEGER NOT NULL,   -- joins to tree_edges and fast "seen before?" checks
    bad_move      TEXT NOT NULL,
    origin_game   TEXT, origin_ply INTEGER, annotation_id TEXT,
    box           INTEGER NOT NULL DEFAULT 1,   -- Leitner 1..3, 4 = mastered
    due_session   INTEGER NOT NULL,             -- per-duck session counter, not wall clock
    attempts      INTEGER NOT NULL DEFAULT 0,
    state         TEXT NOT NULL,                -- new | learning | mastered | dismissed
    UNIQUE (duck_id, position_key, bad_move)
);
CREATE INDEX drill_cards_due ON drill_cards (duck_id, state, due_session);
```

- Scheduling is a pure domain function `schedule_next(box, passed) -> (box, sessions_until_due)` (design 01 B3). Counting sessions instead of days keeps it deterministic and testable without a clock.
- The UNIQUE constraint turns "the duck made this exact mistake again" into an upsert, which bumps `attempts` and drops the card back to box 1. `moves_at_position(position_key, duck_id)` shows every game where it happened.
- Accepting a fix still writes `puzzle_memory` (or the repertoire in the opening window) through `apply_lesson`. The card is the *schedule*; puzzle memory is the *knowledge*. Keeping them separate means a mastered card retires without touching play.
- Size: K = 3 cards per reviewed game. 10,000 games give 30,000 rows of about 150 bytes ≈ 4.5 MB.

### 3.4 Event detail: compaction and retention

The event log is the real growth problem (section 1.3 item 4). Proposal for M3/M5:

1. `recordDetail: compact` (ADR-0004) keeps the top 2 candidates in `MoveChosen` instead of all of them. That roughly halves bytes per ply [estimate, measure].
2. **Retention after review.** Once a game is reviewed and older than N sessions [PH], rewrite its `MoveChosen` events to compact form in a background job, batch-committed. The `moves` row and the PGN stay whole. Annotations keep what the review found.
3. **Never delete what we cannot regenerate.** Full detail is reproducible only if the game can be replayed exactly: seed, arena, engine binary hash (all stored today) **and the duck's knowledge as of that game** (not stored today, see 3.5). Until 3.5 exists, compaction is lossy and should be opt-in.
4. Run `VACUUM` (or `PRAGMA incremental_vacuum` with `auto_vacuum = INCREMENTAL`, set by a migration) after large compactions, since SQLite does not shrink the file by itself.

### 3.5 Determinism: knowledge revisions

Anything that can change a move must be versioned input (ADR-0005, ADR-0006). The tree and cards respect that by construction (they never feed `plan`). Learning makes knowledge change often, which exposes the gap from section 1.3 item 5. Proposal:

- Add `knowledge_rev INTEGER` to the duck, incremented by `apply_lesson`. Record each side's revision on the game (`games.white_knowledge_rev`, `black_knowledge_rev`) at `GameStarted`.
- On resume, refuse (or warn) if a duck's revision changed mid-game. Alternatively, snapshot the knowledge into the match like the arena. A snapshot is simpler and is only a few KB per match.
- The lesson log (ADR-0004 "Lesson log") plus `knowledge_rev` lets any game's knowledge be reconstructed for exact replay. That is what makes event compaction safe.
- Rating context stays as is: knowledge is per duck and is *supposed* to change the duck's rating. What must not change silently is the *rules* (decision-layer version, balance version, `tree_version` only if a tree ever feeds play, which this design says it should not).

### 3.6 Storage and scale estimates

Assumptions: average game 80 plies; EPD key ~56 bytes; SQLite per-row overhead ~5 to 10 bytes; numbers are order-of-magnitude, to be measured.

| Item | Per ply | Per game | 1,000 games | 10,000 games |
| --- | --- | --- | --- | --- |
| Events (full detail, ADR-0004) | 1–2 KB | 80–160 KB | 80–160 MB | 0.8–1.6 GB |
| `moves` row without key | ~100 B | ~8 KB | 8 MB | 80 MB |
| + `position_key` text (0002) in row and in index (56 + 56 + game_id ~13 + rowid 8) | ~135 B | ~11 KB | 11 MB | 110 MB |
| Tree edges, 30-ply cap, worst case one new edge per ply (8 + ~13 + 4 + 5 + 4×4 B + overhead ≈ 60 B) | — | ≤ 1.8 KB | ≤ 1.8 MB | ≤ 18 MB |
| Drill cards (3 per game × ~150 B) | — | 450 B | 0.45 MB | 4.5 MB |

Reading the table:

- The 0002 key costs about 7 to 14% on top of events. Acceptable, and it buys indexed position lookup. If space ever matters, a later migration can add an 8-byte `tree_key` and drop the text index. That would cut the index from ~80 to ~30 bytes per ply.
- The tree is small. In practice it is far below the worst case because early plies repeat: a duck with a 4-move repertoire shares its first 8 edges across every game.
- Even 10,000 games with full events are ~1 to 2 GB, which SQLite handles fine. Compaction is about disk courtesy and backup size (`*.bak-vN` copies the whole file before each migration), not performance.
- A heavy Lichess user importing 50,000 games, tree only (no events, since imports have no `MoveChosen`): ≤ 90 MB of edges, plus `moves` rows if we keep them (~550 MB with keys). Recommendation: for imports, store PGN plus tree edges and *not* per-ply `moves` rows unless the game is opened for review.

### 3.7 When (if ever) DuckDB or a second file

- **Not now.** Every query above is a primary-key range scan or a small group-by. SQLite does these in milliseconds at the sizes in 3.6.
- **Trigger to reconsider:** an analysis screen that does full-table aggregation over more than ~5 million `moves` rows and takes over 1 s after indexing. That is about 60,000 fully recorded games.
- **How, if triggered:** DuckDB can `ATTACH 'duckgambit.db' (TYPE sqlite)` and query the live file directly (read and write supported; SQLite's own locking applies; one writer at a time). So it can be an optional analytics *reader* in an adapter behind a port, with no export step and no second source of truth. A separate Parquet or DuckDB file for imported Lichess archives is the next step only if imports reach millions of games.
- **Cost:** DuckDB is MIT-licensed (compatible), but it is a ~20 to 40 MB native wheel [unverified size] in a desktop sidecar. That is the main reason to wait.

### 3.8 Data flow

```
match game finishes ─┬─► moves (position_key per ply)          [exists, 0002]
                     ├─► tree_edges upsert (≤ 30 plies)         [M2]
                     └─► review job ─► annotations ─► drill_cards upsert   [M5]
Lichess import job ──────► games + PGN ─► tree_edges (batched)  [M6]

player opens Opening Drill ─► tree_edges + chess-openings names ─► "suggest" ─► Lesson ─► apply_lesson ─► repertoire_entries
player opens Blunder Training ─► drill_cards due ─► fix ─► Lesson ─► apply_lesson ─► puzzle_memory / repertoire
decision layer (plan) reads ONLY: repertoire_entries, puzzle_memory, motifs/principles   [versioned via knowledge_rev]
```

---

## 4. Prior art to reuse

Project license: GPL-3.0-or-later. Licenses below were checked on 2026-11-21 against the GitHub API's `license.spdx_id` or the project's own site.

| Tool | What it does | License | Fit | Recommendation |
| --- | --- | --- | --- | --- |
| **python-chess** `chess.polyglot` ([docs](https://python-chess.readthedocs.io/en/latest/polyglot.html), [repo](https://github.com/niklasf/python-chess)) | `zobrist_hash(board)`, `open_reader(path)` with `find_all`, `weighted_choice`; `POLYGLOT_RANDOM_ARRAY` | GPL-3.0 (already a dependency, 1.11.2) | Exact: tree keys and reading third-party books. **No writer**: the docs list reading only | **Reuse.** Write our own `.bin` exporter if needed: 16-byte big-endian records sorted by key, about 30 lines |
| **Polyglot book format** ([spec by H.G. Muller](http://hgm.nubati.net/book_format.html)) | 16-byte entries: key u64, move u16, weight u16, learn u32; sorted by key; 781-entry Zobrist array | The spec says the algorithm may be freely implemented; sample code is public domain | Good interchange format for exporting or importing a duck's repertoire | **Borrow the format** for M6 export/import. Not as internal storage: it has no results, no per-duck data, and keys only |
| **lila-openingexplorer** ([repo](https://github.com/lichess-org/lila-openingexplorer)) | Lichess opening explorer: ~500 billion positions, LSM key-value store (SST files, merge operators), 96-bit Zobrist-based `PositionKey`, stats bucketed by month/rating/speed, positions seen once kept in a separate cold table that points at candidate games, which are replayed at query time | **AGPL-3.0** | Rust server at a scale 10⁶× ours | **Borrow ideas only:** Zobrist keys, pre-aggregated per-move counters summed at query time, a depth or frequency cutoff with fallback to replaying games (our `moves_at_position` is that fallback). Do not copy code: AGPL's network clause adds obligations we do not want in the desktop app |
| **lichess-org/chess-openings** ([repo](https://github.com/lichess-org/chess-openings)) | ECO code, name, PGN, UCI moves and **EPD** per named opening, in `a.tsv`..`e.tsv` | **CC0-1.0** | Its EPD includes en passant "only if legal", the same normalisation as our `position_key`, so names join directly on our key | **Reuse** in M2: ship the TSVs (or a generated table) as packaged data; record in `THIRD_PARTY_LICENSES.md` |
| **openingtree.com** ([repo](https://github.com/openingtree/openingtree)) | Builds an opening tree with win rates from a player's Lichess/chess.com/PGN games, in a web UI | GPL-3.0 | JavaScript client app; the README does not document how the tree is stored [unverified] | **Borrow UX ideas** (filters, per-move win bars) for John. No code reuse: our clients stay thin |
| **chess-opening-trees** ([repo](https://github.com/isofarro/chess-opening-trees)) | Python; builds an opening tree in SQLite from PGN incrementally; per-move games, W/D/L, last played, performance; FEN lookups | **No license file found**: all rights reserved by default | Closest to our design, but tiny (0 stars) | **Skip code.** Its per-move fields confirm our `tree_edges` columns are the useful ones |
| **pgn-extract** ([site](https://www.cs.kent.ac.uk/~djb/pgn-extract/)) | C command-line tool to filter, clean, dedupe and convert PGN | GPL-3.0-or-later since 2017 (author's site, Debian copyright) | Useful for cleaning big Lichess dumps offline | **Dev tool only.** Not a runtime dependency: python-chess's PGN reader suffices in the app |
| **jja** ([docs.rs](https://docs.rs/crate/jja/latest)) | Rust CLI: compile PGN to Polyglot, convert CTG/ABK books, merge books | GPL-3.0-or-later (per a talkchess post by the author) [verify LICENSE file before use] | Book tooling for curating starter repertoires | **Dev tool only**, optional |
| **SCID / Scid vs. PC** ([site](https://scidvspc.sourceforge.net/)) | Desktop chess database; `.si4/.sn4/.sg4` binary format with name and game files | GPL-2.0 per SourceForge (SCID: sources disagree between GPL and LGPL) [unverified; check the source headers] | Mature but a bespoke binary format in Tcl/C++, built for millions of master games | **Skip.** GPL-2.0-only code would also be incompatible with GPL-3.0-or-later; idea-level only |
| **DuckDB** ([repo](https://github.com/duckdb/duckdb), [SQLite extension](https://duckdb.org/docs/2.0/core_extensions/sqlite.html)) | In-process columnar analytics; `ATTACH '...db' (TYPE sqlite)` reads and writes SQLite files directly | MIT | Analytics over large `moves` and imports without exporting | **Defer** (section 3.7). Revisit at M6 with measurements |
| PGN-to-SQLite importers (`chess-to-sqlite`, `pgn-to-sqlite` on PyPI) | Load PGN or fetched games into SQLite tables | Not checked | Store games, no tree or position index | **Skip.** Our import is ADR-0010's job, behind a port |

Not found: a maintained, permissively licensed Python library that builds an incremental, Zobrist-keyed opening tree in SQLite. The tree in section 3.2 is about 100 lines on top of python-chess, so building it is cheaper than adapting anything above.

---

## 5. Open questions for John

| # | Question | Recommended default |
| --- | --- | --- |
| Q1 | Should a duck ever learn from its own games automatically, or only through lessons the player accepts? | Only through accepted lessons in M2 to M5. Revisit an automatic "duck studies its games" activity later as a capped, energy-costing lesson source |
| Q2 | How deep should the opening tree go? | 30 plies (15 moves) [PH], matching the opening window used for repertoire fixes |
| Q3 | Should the tree mix all of a profile's ducks, or show one duck at a time? | Store per duck; the UI defaults to "this duck", with an "all my ducks" toggle (a group-by, no extra storage) |
| Q4 | Should imported Lichess games show in the same tree as duck games? | Yes, with a source filter that defaults to duck games only, so the player's human games do not blur the duck's identity |
| Q5 | How long do we keep full thinking-panel detail for old games? | Full detail for unreviewed games and the latest 200 [PH]; compact after review. Requires knowledge revisions (3.5) first |
| Q6 | Should a duck's repertoire export to Polyglot `.bin` so players can use it in other GUIs? | Yes in M6, export only. Import from `.bin` would be a lesson with a size cap, like duck-file import |
| Q7 | Should opening names appear on the board and in move lists? | Yes in M2 from the CC0 dataset; names are presentation only and never affect play |
| Q8 | Do we tell players plainly that trees and mistake history do not make the duck stronger by themselves? | Yes. Copy along the lines of "your duck plays what you teach it; this is what it has actually played". It keeps the honesty principle from design 01 |

---

## 6. Sources

- python-chess Polyglot docs: https://python-chess.readthedocs.io/en/latest/polyglot.html (`zobrist_hash` en passant rule read from the installed 1.11.2 source, `chess/polyglot.py`, `hash_ep_square`)
- Polyglot book format: http://hgm.nubati.net/book_format.html
- lila-openingexplorer README (storage, 96-bit keys, cold positions, sizes): https://github.com/lichess-org/lila-openingexplorer
- lichess-org/chess-openings (CC0, EPD column): https://github.com/lichess-org/chess-openings
- openingtree: https://github.com/openingtree/openingtree
- chess-opening-trees: https://github.com/isofarro/chess-opening-trees
- pgn-extract: https://www.cs.kent.ac.uk/~djb/pgn-extract/ and Debian copyright https://sources.debian.org/src/pgn-extract/19.04-1/copyright
- jja: https://docs.rs/crate/jja/latest
- Scid vs. PC: https://scidvspc.sourceforge.net/ and https://sourceforge.net/projects/scidvspc
- DuckDB SQLite extension: https://duckdb.org/docs/2.0/core_extensions/sqlite.html ; DuckDB license: https://github.com/duckdb/duckdb
- Licenses for GitHub repos: GitHub REST API `GET /repos/{owner}/{repo}` → `license.spdx_id`, queried 2026-11-21
