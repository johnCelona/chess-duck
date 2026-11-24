# ADR-0006 · Strength, virtual time, ratings and progression

Status: Proposed · 2026-11-21 · Implements spec 4.2, 4.4, 6.2, 6.3 · All numbers are placeholders until M3 measures them

## Context

A duck's strength must be real, measured, identical on every machine, and able to grow from about 2000 to about 2500 through play and coaching, while Stockfish itself never changes. This is the hardest design problem in the product.

Facts established on 2026-11-21:

- **Node-limited search is reproducible.** Measured on Stockfish 19 (Windows, Threads 1): `go nodes 20000` returned identical PVs, scores, WDL and node count on repeated fresh processes, and the same with Hash 16 and Hash 64. Stockfish's own test suite asserts run-to-run reproducibility for `ucinewgame` + `go nodes`, and its CI checks one `bench` signature across x86, ARM and other architectures and compilers [1]. There is no written cross-machine guarantee; the CI signature is the evidence. Threads above 1 is not deterministic.
- **`ucinewgame` makes a warm engine behave like a fresh one.** Measured: after an unrelated search, `ucinewgame` + the test search gave exactly the fresh-process result; without the reset it did not (hash carry-over changes the search). Reset cost 3 to 4 ms with a 16 MB hash, about 23 ms with 256 MB.
- **Speed.** 200k nodes takes about 0.2 s here; 2k nodes about 5 ms.
- **Node limits overshoot slightly but deterministically** (20,017 reported for 20,000) because the limit is polled periodically [2].
- **Stockfish's own weakening cannot be seeded.** `Skill Level` and `UCI_Elo` pick moves with a generator seeded from the clock, by design [3]. `UCI_Elo` spans 1320 to 3190 and is described as calibrated at 120s+1s and anchored to CCRL 40/4 [2].
- **Stockfish 19 exits on invalid UCI input** [4], so everything is validated before it is sent.
- **Maia** exists as lc0 weights for 1100 to 1900 (GPL-3.0) used at `go nodes 1`, and as a newer PyTorch/UCI project under AGPL-3.0 [5].

## Options considered

**Clock.** (a) Real time: machine-dependent, rejected by rule 6. (b) Stockfish's `nodestime` option, which runs Stockfish's own time management in nodes: reproducible, but the engine, not the duck, would decide how to spend the clock, so the speed stat would mean nothing. (c) Our own virtual clock that turns a think budget into `go nodes`.

**Engine state between moves.** (a) Keep the hash through a game: slightly stronger, but a move then depends on every earlier search, so a game cannot be resumed mid-way or a single position replayed. (b) Reset before every search: each move is a pure function of (move history, nodes, MultiPV, engine binary).

**Weak play.** (a) `UCI_Elo`/`Skill Level`: unseedable, floor at 1320. (b) Our own seeded filter and sampling over full-strength MultiPV output.

**Rating system.** Elo (one number, no uncertainty) or Glicko-2 (deviation handles new ducks; spec's leading choice). Library or hand-written: the PyPI packages are small and rarely released; the algorithm is about 100 lines with a published worked example to test against [6].

## Decision

### 1. Stateless, single-threaded search for anything that affects a result

Threads 1, fixed Hash, `ucinewgame` + `isready` before every search, full move history in the `position` command (so repetition is seen). `Skill Level`, `UCI_LimitStrength` and `UCI_Elo` are never set in rated play. Parallelism comes from running several games at once (ADR-0007), never from threads inside one search.

This buys three properties: a game can be resumed at any ply; the lesson check ("replay this position with a fixed seed") reproduces exactly what would happen in a game; and a search result can be cached by its inputs.

### 2. Stats become parameters through one pure, data-driven function

`derive_mind(stats, growth, balance) -> MindParams`. The balance table is a versioned JSON document shipped with the backend; its version is part of the rating context.

| Stat (0 to 100) | Parameter | Shape (placeholder) |
| --- | --- | --- |
| Calculation | `nodeMultiplier` | Geometric: each fixed step of points doubles the nodes |
| Memory | `bookRecall` | Probability of recalling a taught move, rising toward 1 |
| Aggression, Solidity | Rule weights | Linear |
| Creativity | `temperature` | 0 at 0 points, rising |
| Speed | `speedFactor` and the time policy | Lower factor means quicker moves and more reserve |
| (growth: level, stage) | `blunderToleranceCp`, stat budget, stat caps | Tolerance narrows as level rises |

Blunder tolerance is not one of the six stats in the spec. It is derived from level and stage, so that growth, not point allocation, removes blunders. **This is a balance choice for John.**

### 3. Virtual clock, in integers

```
thinkMs   = clamp(remainingMs / expectedMovesLeft + incrementShare * incrementMs, minThinkMs, maxThinkMs) * speedFactor
nodes     = clamp(thinkMs * virtualNps / 1000 * nodeMultiplier, minNodes, serverMaxNodes)
remaining = remaining - thinkMs - moveOverheadMs + incrementMs
```

- Time charged is the *budgeted* `thinkMs`, not the nodes actually used, so the clock does not depend on engine internals.
- Book and forced moves cost a small fixed time.
- A side whose remaining time reaches zero loses on time. With a minimum think time, a slow duck in a long game can flag, which is what makes the speed stat matter in bullet.
- `virtualNps` belongs to the arena and is the same for both ducks. With `equalEngine: true` the node multiplier is ignored.
- The server never sleeps. A 1-minute bullet game computes in a few seconds; clients pace playback from the `thinkMs` in each event (ADR-0007).

### 4. Rating means "measured in a context"

A rating context is: engine id, version and binary sha256; limit type; `virtualNps`; Threads and Hash; MultiPV; decision-layer version; balance version. Ratings and histories are stored per (duck, context, kind). A new Stockfish release or a balance change creates a new context; old ratings stay visible as history but are not continued.

Glicko-2, hand-written in the domain, tested against Glickman's worked example. New ducks are provisional until their deviation falls below a threshold.

### 5. Calibration harness

`duckgambit calibrate` runs headless, seeded games through the same match runner:

- **Anchor ducks** are fixed configurations of our own pipeline (for example pure engine at 500, 2k, 8k, 32k nodes with zero temperature, and the same with a set blunder tolerance). They are deterministic and live in a committed table.
- The anchors are rated against each other with a large round robin, then **tied to an external scale** by a one-off run against Stockfish at several `UCI_Elo` settings. Those games are not reproducible, so they are used only in bulk, offline, to place the anchor pool on an Elo-like axis; the result is committed as data with its sample sizes.
- The harness then fits a simple curve from parameters (nodes per move, tolerance, temperature) to rating. That curve gives a new duck its provisional rating and lets the balance table be designed so that a given level lands near a target rating.
- Until the harness has run, the walking skeleton shows a provisional rating from a stub and labels it as such.

### 6. How a duck climbs from 2000 to 2500

Full-strength Stockfish is expected to be well above 2500 even at a few thousand nodes per move (unmeasured; the harness will confirm). If so, the ceiling is not the problem: every duck is a deliberately handicapped engine, and growth removes handicap in ways the player caused:

1. **Level** raises the stat budget: more Calculation is more nodes.
2. **Level and stage** narrow blunder tolerance: fewer bad candidates survive the filter.
3. **Knowledge**: repertoire moves are instant and correct, which saves clock in bullet and avoids low-node opening errors; puzzle-memory entries from "teach the fix" repair specific mistakes; motif bonuses tilt choices.
4. **Speed and clock policy**: fewer losses on time.

XP amounts, the level curve, budget per level, and stage thresholds are rows in the balance table. Each lever's rating effect is measured by the harness before any number is promised.

### 7. Honest limits

- The engine does not learn. Training edits the duck's data.
- "2000" means 2000 on our anchor scale, tied approximately to Stockfish's `UCI_Elo` labels, which are themselves approximate. It is not a FIDE or Lichess rating.
- A handicapped Stockfish does not blunder like a human. The filter and sampling make errors plausible, not human. A human-like engine such as Maia can be added as another manifest entry behind the same `Engine` port; it would be its own rating context.
- Cross-machine determinism rests on Stockfish's CI signature check and our own measurement, not on a written guarantee. The runner records the engine's binary hash with every game, and a real-engine test compares a known position's result against a committed expectation so that drift is noticed.

## Consequences

- Resetting the engine each move gives up some strength at a given node count; calibration absorbs that, since every duck and anchor plays under the same rule.
- Ratings fragment by context. That is correct, and the UI must show which context a rating belongs to.
- Balance changes are data changes with a version, so they can be reviewed, tested and rolled back.

## Not building yet

- The harness itself, anchor table and curve fit (M3). M0 ships the virtual clock, `derive_mind`, Glicko-2 and a clearly labelled rating stub.
- Real balance numbers, XP curve and stage rules (M3, M5; John's input).
- Maia or any second engine; tablebases; pondering; multi-threaded "analysis" contexts.
- Win-chance-based filtering (see ADR-0005).

## Sources

1. Stockfish `tests/reprosearch.sh`, `tests/signature.sh`, CI workflow: https://github.com/official-stockfish/Stockfish/tree/sf_19/tests
2. Stockfish wiki, UCI and commands: https://official-stockfish.github.io/docs/stockfish-wiki/UCI-Protocol-and-Stockfish-Commands.html
3. Stockfish `src/search.cpp`, `Skill::pick_best`: https://github.com/official-stockfish/Stockfish/blob/sf_19/src/search.cpp
4. Stockfish 19 release notes: https://stockfishchess.org/blog/2026/stockfish-19/
5. Maia: https://github.com/CSSLab/maia-chess and https://github.com/CSSLab/maia3
6. Glickman, "Example of the Glicko-2 system": http://www.glicko.net/glicko/glicko2.pdf

## Amendments (2026-11-21, M0 build)

- **The clock policy is part of the balance table** (`Balance.clock`, `domain/balance.py`), so one version (`balance-0.2-placeholder`) covers every tunable number.
- **Retuned defaults: `expected_game_moves` 60, `min_moves_left` 30.** With the first values (40 and 10) a default duck in a 1+0 game ran out of virtual time around move 64; most real games then ended on time rather than on the board. Simulated with the integer formula: a speed-40 duck now flags only after about move 125; with speed 0 after about move 105. Still placeholders for M3 calibration.
- **Measured on real Stockfish 19 (Windows x86-64):** two runs of the same seeded bullet match (127 plies) produced identical moves, node counts, evaluations, clocks and event streams. A 40-ply real game replays identically in `backend/tests/real`. Cross-machine and cross-OS equality is still unverified beyond Stockfish's own CI evidence.
- The calibration stub shows every new duck at 1500, provisional, with no rating context, until it plays a rated game.
