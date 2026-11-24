# ADR-0005 · The decision layer

Status: Accepted (John, 2026-11-21) · 2026-11-21 · Implements spec 6.1

## Context

Every duck uses the same engine; what differs is the pipeline that turns engine candidates into a move: book, filter, style score, sampling. The spec requires it to be pure, deterministic, unit-testable, to explain itself, and to offer a ranked top-5 mode for puzzles. The pipeline needs an engine search in the middle, which is I/O.

## Options

1. **Pass an engine object into the domain function.** Simple to read, but the domain becomes async and impure, and tests need an engine double for every case.
2. **Two pure steps around the search** (functional core, imperative shell). The domain first returns either a finished decision (book or forced move) or a *search request*; the runner performs the search through the `Engine` port; the domain then turns the result into a decision.
3. Generators/coroutines that yield the search request. Equivalent to 2 with more machinery.

## Decision

Option 2. The public surface of `duckgambit.domain.decision`:

```python
plan(position, mind, clock, seed)        -> BookDecision | ForcedDecision | SearchRequest
choose(position, mind, search, seed)     -> Decision        # play: one move, sampled
rank(position, mind, search, top=5)      -> RankedDecision  # puzzles: ordered list, no sampling
```

- `position` is a board with its move history. `mind` is a `MindParams` value derived from the duck by a pure function (ADR-0006) plus read-only views of its knowledge. `search` is the engine's `SearchResult`. Nothing here imports the engine, the database or a clock.
- **Pipeline** (each stage records what it did):
  1. *Book.* Look up `position_key` in the repertoire. With probability `bookRecall` (from the memory stat) pick an entry by weight; otherwise "forget" and fall through. Illegal stored moves are ignored.
  2. *Forced.* One legal move: play it, no search.
  3. *Search request.* Nodes and MultiPV come from the arena and the clock (ADR-0006).
  4. *Filter.* Drop candidates more than `blunderToleranceCp` below the best. The best candidate always survives.
  5. *Style score.* Each registered rule looks at (board, move) and may add an `Adjustment(ruleId, kind, delta, reason)`. Kinds: `aggression`, `solidity`, `principle`, `motif`. Rules are small pure functions in a registry; a duck's weights decide which ones count.
  6. *Sample.* Softmax over final scores with temperature from creativity. Temperature 0 is argmax. Ties break by engine rank, then by UCI string.
- **Determinism details.**
  - Randomness comes from a per-decision generator seeded with `sha256(gameSeed, ply, purpose)`. A decision therefore does not depend on how many random numbers earlier moves consumed, so any single position can be replayed alone (the lesson check in spec 5.5 needs exactly this).
  - Only `Random.random()` is used, whose sequence Python guarantees for a given seed. Sampling weights are converted to integers before the cumulative draw, so a last-bit difference in `exp` between platforms cannot change the chosen move.
  - Scores are integer centipawns. Mates map to a large value that shrinks with distance, so a shorter mate outranks a longer one.
  - The `Engine` port guarantees that all candidates come from the **same completed search depth**. Measured on Stockfish 19 with MultiPV 5 at 20k nodes: the final `info` lines for PVs 4 and 5 were from depth 7 while PVs 1 to 3 were from depth 8, so taking "the last line per PV" mixes depths.
- **Output.** `Decision` holds the chosen move, the source (`book`, `forced`, `engine`), every candidate with engine score, WDL, adjustments, final score, probability and filter verdict, and reason entries `{code, params, text}`. It maps one-to-one onto the `MoveChosen` event (ADR-0002).
- **Versioning.** `DECISION_LAYER_VERSION` is bumped whenever a change could alter a move for the same inputs. It is part of the rating context (ADR-0006), so ratings from different versions are never mixed silently.

M0 implements the full pipeline shape with a handful of rules (capture, check, castle, retreat) so reasons flow end to end. Principles and motif detectors are registry entries added in M2 and M4.

## Consequences

- The whole layer is tested with plain values: a board, a `MindParams`, a hand-written `SearchResult`, a seed. No engine, fake or real.
- The runner owns the search, so engine concurrency, budgets and timeouts stay out of the domain.
- The filter works in centipawns as the spec says. In clearly won positions centipawn gaps are meaningless (+9 against +14); moving the filter and softmax onto win-chance units is a contained change behind `DECISION_LAYER_VERSION`, to be decided with calibration data in M3.

## Not building yet

- Principle and motif detectors (M2, M4), opening-name lookup, tablebase step (endgame school).
- Per-duck learned weights beyond the stats and knowledge in the spec.
- Any tuning of weights or temperature curves: placeholders now, measured in M3.

## Amendments (2026-11-21, M0 build)

- **Taught fixes come first.** `plan` takes the duck's `taught_move` for the exact position (puzzle memory, written by ADR-0008's lessons) and recalls it with the same memory-stat chance as the book, before the book. `Decision.source` is now `memory | book | forced | engine`. Without this, fixes outside the opening would never change play (design 01, delta A5).
- **One candidate per move.** `_score` ignores a repeated move, so a duplicate can never be counted twice when sampling. The engine adapter also stopped producing duplicates (ADR-0007 amendment).
- **Base-2 softmax is interpolated** between the 16 table steps, so weights fall smoothly with the gap.
- `DECISION_LAYER_VERSION` is now `decision-2`.
