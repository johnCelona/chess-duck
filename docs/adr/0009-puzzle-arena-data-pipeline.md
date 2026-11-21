# ADR-0009 · Puzzle Arena data pipeline

Status: Proposed · 2026-11-21 · Implements spec 7.4

## Context

In Puzzle Arena every duck answers the same position and a fixed Judge grades the answers. Grading live would be slow and would vary with settings; the spec recommends an offline answer key. Puzzle data comes mainly from the Lichess puzzle database.

Verified on 2026-11-21 [1]:

- Lichess database exports, including puzzles, are released under **CC0**: "You can download, modify and redistribute them, without asking for permission." No attribution is required. Redistributing a curated subset is allowed.
- 6,193,530 puzzles (file dated 2026-11-11). Columns: `PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags,DailyDate`.
- The FEN is the position *before* the opponent's move: apply the first move in `Moves` to get the position shown; the second move starts the solution. Mate-in-one puzzles accept any mating move.

## Options

**Answer key.** (a) One search of the puzzle position with MultiPV equal to the number of legal moves: one call, but effort is split unevenly and weak moves are searched shallowly. (b) One Judge search per legal move, on the position after that move: uniform effort, trivially parallel and resumable.

**Pack storage.** (a) Rows in SQLite; (b) versioned JSON files. Packs are read-only reference data that must be shareable and diffable.

## Decision

### Pack format

`<pack-id>/pack.json`:

```json
{
  "format": "duck-gambit.puzzle-pack",
  "schemaVersion": 1,
  "id": "starter-tactics",
  "title": "Starter tactics",
  "license": "CC0-1.0",
  "source": { "name": "Lichess puzzle database", "url": "https://database.lichess.org/#puzzles", "retrieved": "2026-11-11" },
  "judge": { "engine": "stockfish", "version": "19", "binarySha256": "…", "limit": { "type": "nodes", "value": 2000000 }, "wdl": true },
  "puzzles": [
    {
      "id": "lichess:00sHx",
      "fen": "<position shown to the solver>",
      "goal": { "type": "find-best" },
      "themes": ["fork", "middlegame"],
      "rating": 1510, "ratingDeviation": 75,
      "solution": ["e4d6", "…"],
      "answerKey": { "e4d6": { "wdl": [962, 36, 2], "cp": 412, "mate": null, "rank": 1 }, "…": {} }
    }
  ]
}
```

`fen` is already the solver's position (the first database move has been applied). `answerKey` has one entry for **every legal move**. We credit Lichess in the pack although CC0 does not require it.

### Tools (CLI, offline, deterministic)

1. `duckgambit puzzles build --csv <path> --themes … --rating-range … --count N --seed S` reads a locally downloaded CSV, filters, samples with the seed, applies the first move, and writes a pack without answer keys. The CSV itself is never committed.
2. `duckgambit puzzles answer-key <pack>` leases Judge engines from the pool and, for each legal move of each puzzle, runs a stateless search on the resulting position at the Judge's node budget with WDL on. It records WDL, centipawns and mate distance from the solver's point of view, ranks the moves, and writes after each puzzle so it can resume.

### Scoring (pure domain functions)

- `win_chance(entry)`: from WDL; mate found is 1.0 with shorter mates ranked first.
- `keeps_win(entry)`: win chance at or above a threshold (0.90 by default).
- `score_showdown(ranked5, answerKey, rules)`: the spec's 3/2/1/0/−1 scheme, where "best" means any move whose result ties the top entry. Returns points plus idea stats (agreement, original idea, trap count).
- Goal-based modes (Mate in N, Convert the Win, Survive) are played out against the **Defender**, an engine lease with fixed settings, by the match runner with a different end condition. Head-to-head is an ordinary game from a custom start position.
- Puzzle rating: Glicko-2 for a duck against each puzzle's rating and deviation, stored with `kind = puzzle` and scoped to the pack.

In play, grading is a lookup in `answerKey`; only the ducks search.

### What is committed

A tiny hand-made sample pack (our own positions) with its answer key lives in the repo for tests. Curated packs built from Lichess data are release assets produced by the tools; whether a small starter pack (around 1 MB) is committed is decided in M4.

## Consequences

- Building a key costs (legal moves × Judge nodes) per puzzle: roughly 35 searches of 2M nodes, on the order of a minute of CPU per puzzle on this machine, so 500 puzzles is an overnight job on one core or under two hours on eight. Done once per pack and per Judge.
- A pack is tied to its Judge. A new engine version means regenerating keys; the pack records which Judge wrote it.
- The Judge accepts any move that keeps the evaluation, which matches the spec and avoids penalising alternative solutions.

## Not building yet

- The real builder and key generator (M4). M0 ships the pack schema, the pure scoring functions with tests against the sample pack, and a script skeleton.
- Replay puzzles mined from duck games, hand-built puzzle editor, daily puzzle.
- Motif drills (M4) and the Defender play-out modes.

## Sources

1. Lichess open database, puzzles and license: https://database.lichess.org/#puzzles
