# ADR-0007 · Match and arena runtime

Status: Accepted (John, 2026-11-21) · 2026-11-21 · Implements spec 7.1 to 7.3

## Context

Matches, tournaments, reviews and answer-key builds are long, CPU-heavy and must be reproducible. Today there is one lazily started engine process per engine id and nothing that queues, bounds or cancels work.

Problems in the current engine adapter (commit `9daabb4`) that this design must remove:

- **Overlapping commands cancel each other.** python-chess runs one command per engine and cancels the in-flight one when another arrives; the adapter's lock covers only start and stop. Two simultaneous analyses on one engine make the first fail.
- **Timeouts do not clean up.** The search thread and the engine keep running after a timeout; the process is never killed.
- **No crash recovery.** A dead process is never replaced.
- **Option overrides are sticky**, so one request changes the next one's result.
- **Caps are per request**, not totals across processes.
- **Candidates can mix search depths** (see ADR-0005).

## Options

**Job execution.** (a) An in-process asyncio runner with a persisted `jobs` table; (b) a separate worker process; (c) an external queue (Celery, RQ, Redis). The product is local-first and ships as a sidecar: (c) adds a service to install, (b) adds inter-process plumbing we do not need while one machine runs everything.

**Engines per game.** (a) One process per duck; (b) one process per game, shared by both sides. With stateless search (ADR-0006) no state survives between moves, so sharing is free and fair.

**Live watching.** (a) The server paces the game in real time; (b) the server computes as fast as it can and clients pace playback.

## Decision

### Engine port and pool

```python
class Engine(Protocol):
    async def describe(self) -> EngineInfo                       # id, version, advertised options
    async def search(self, request: SearchRequest) -> SearchResult
    async def close(self) -> None
```

`SearchRequest` is a value: move history, limit (`nodes` or `depth`), MultiPV, WDL flag. There is no "configure" call; options are part of how an engine is leased. Implementations: `UciEngine` (asyncio subprocess through python-chess's async API), `FakeEngine` (in-process, deterministic), and a fake UCI executable for adapter tests (ADR-0012). Duck search, Judge and Defender are leases with different settings, not different code.

`EnginePool`:

- Leases are exclusive: one lease, one process, one caller. This removes the cancellation hazard by construction.
- Budget: at most `maxEngines` processes (default: CPU cores minus one, capped), each Threads 1 for result-affecting work; total Hash across live processes is capped. A lease that would exceed the budget waits.
- Every search has a deadline derived from its node count. On deadline, cancellation or protocol error the process is **killed** and replaced; the lease reports a typed error.
- Idle processes are reaped after a short time. Shutdown kills everything. Requests are validated before they reach the engine because Stockfish 19 exits on malformed input.

### Jobs

- `jobs` rows: kind, params, seed, state (`queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`), progress, error, timestamps.
- An in-process runner executes jobs as asyncio tasks, bounded by the pool. Progress is published as `JobProgressed` events on `job:{id}`.
- **Cancel** is cooperative: a flag checked between plies and between games; the current search is stopped and the lease released.
- **Resume**: on startup, any job left `running` becomes `interrupted`. Resumable kinds restart from their last durable checkpoint. For a match the checkpoint is the last finished game; a half-played game is replayed from move one with the same seed, and because search is stateless the replay must reproduce the stored moves exactly. A mismatch is logged as a determinism failure.
- API: `POST /matches` returns a match and its job; `GET /jobs/{id}`; `POST /jobs/{id}/cancel`.

### Match runner

A service that loops: `plan` (domain) → `search` (pool) → `choose` (domain) → apply move, update the virtual clock, persist the move row and events, publish. It contains no chess judgment of its own.

- Seeds: the arena seed derives a seed per game (`sha256(matchSeed, gameIndex)`), which derives a seed per decision (ADR-0005).
- Game end: checkmate, stalemate, insufficient material, threefold repetition and the fifty-move rule (claimed automatically), loss on virtual time, and a ply cap that scores a draw. No evaluation-based adjudication.
- One engine lease per game.
- Arena settings are snapshotted into the match at creation and cannot change mid-game.

### Instant simulation and live watching are one code path

The server always runs at full speed and appends events. "Live" is a client following the stream and pacing each move by its `thinkMs`; "instant" is a client that waits for `MatchFinished`; replay is the same stream read from the start. No wall-clock time exists on the server side of a game.

### PGN

Generated by a pure domain function from the game record. Standard seven tags plus `TimeControl`, `Seed`, `RatingContext`, engine name and version; per-move comments with `[%eval]`, `[%clk]` and a short source note (`book`, or the top reason). Golden-file tested. `GET /games/{id}/pgn` returns it as a download.

## Consequences

- One process serves API and jobs. A crash interrupts running jobs; they resume on restart. Acceptable locally.
- Killing engines on any anomaly is blunt but keeps the system honest; engine startup is cheap.
- Client-paced playback means spectators of the same match are not synchronised with each other. Fine for local play; a hosted mode would add a shared "broadcast clock" on top of the same events.
- The pool bounds CPU: a 100-game tournament runs `maxEngines` games at a time and the UI stays responsive.

## Not building yet

- Tournament scheduling (round robin, Swiss, knockout): interface and stub in M0, real pairing in M3.
- Worker processes, distributed execution, priorities, scheduled jobs.
- Handicap matches, best-of-N UI, mid-match arena changes between games.
- Evaluation-based adjudication, tablebase adjudication, opening books for arenas.
- A search cache (the stateless design allows it; add it when a profile shows it is worth it).

## Amendments (2026-11-21, M0 build)

- **Engine lines are collected by root move, not by MultiPV line number.** Watching a real game showed one move listed on two lines: while an iteration is in progress Stockfish re-sorts its lines and reprints unfinished ones under the previous depth, so one line number can name different moves within a depth. The adapter now keys lines by move, takes the deepest depth with a full set, and orders by score. Regression tests: the fake UCI engine's `reorder` mode, the decision layer, and `backend/tests/real`.
- **Engine I/O runs on its own event loop thread**, independent of the web server's loop (uvicorn's reloader on Windows uses a loop that cannot start subprocesses).
- **Shutdown does not wait for open event streams**: readers are woken when the event log closes, and uvicorn's graceful shutdown is capped at 3 seconds.
- The section "No wall-clock time exists on the server side of a game" is narrowed by ADR-0015 for unrated games with a human player.
