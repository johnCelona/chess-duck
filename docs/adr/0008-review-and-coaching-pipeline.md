# ADR-0008 · Review and coaching pipeline

Status: Proposed · 2026-11-21 · Implements spec 5.5 · Data flow only, no UI

## Context

The review loop is the main source of a duck's growth and of the player's learning: a fixed Judge finds the costly moments in a finished game, the player teaches a better move, and the duck's knowledge changes. It must be deterministic, explainable and must write to Knowledge through one door.

## Options

**Loss metric.** Centipawn loss is simple but saturates in won positions (+9 to +14 is not a blunder). Expected-score loss from the engine's win/draw/loss output treats "still winning" as no loss. Stockfish's WDL model is normalised so that 100 cp is a 50% win chance [1].

**Where fixes are stored.** Always the repertoire; or repertoire for opening positions and a separate puzzle memory for the rest. A single store blurs "opening book" with "position I was taught", which decay and display differently.

**How knowledge is mutated.** Services edit duck fields directly; or every change is a `Lesson` applied by one pure function.

## Decision

```
finished game
   │  job: review(gameId, judgeConfig)
   ▼
Judge pass ── for every ply: stateless search at the Judge's fixed node budget, MultiPV ≥ 2, WDL on
   ▼
per-ply facts: best move, expected score of best, expected score of the move played
   ▼
classify (pure) ── loss = E(best) − E(played); thresholds from the balance table:
                   inaccuracy / mistake / blunder / missed win / missed mate; optional motif tag
   ▼
select (pure) ── top K by loss, spread across the game, K = 3 by default
   ▼
Review + Annotations stored; events: CriticalMomentFound × K, ReviewReady
   ▼
teach the fix ── POST a move for a moment
   ▼
grade (Judge lookup, or one Judge search if the move was not among its lines)
   ▼
Lesson (pure) ── KnowledgeDelta: repertoire entry if the ply is in the opening window,
                 else puzzle-memory entry; motif bump; XP
   ▼
apply_lesson(duck, lesson) -> (duck', events)   events: FixTaught, KnowledgeAdded, maybe DuckLeveledUp
   ▼
lesson check ── run the duck's decision layer on that position with a fixed seed
   ▼
LessonChecked { passed }   a failure is offered as another lesson
```

Rules:

1. **The Judge is a rating-context-like value** (engine, version, node budget, MultiPV). It is stored with the review. Changing the Judge means a new review, never an edit.
2. **Expected score** is `(win + draw / 2) / 1000` from WDL, from the mover's point of view. Mates count as 1 or 0, with distance as the tie-break.
3. **All knowledge changes go through `apply_lesson`.** The lesson log is append-only and every knowledge row records the lesson that produced it, so the game can always answer "why does my duck play this?" and a lesson can be undone.
4. **A player's fix need not be the Judge's first choice.** It is accepted if its expected score is within a tolerance of the best move; otherwise the response says how much it loses and nothing is written. The Judge's own suggestion is revealed only after an attempt.
5. **The lesson check is honest.** It runs the real pipeline with a fixed seed. A low memory stat can make the duck forget; that is a visible, explainable result, not a bug.
6. Sparring games (human against duck) enter the same pipeline; only the source of the game differs.

## Consequences

- Review cost is plies × Judge nodes. An 80-ply game at 1M nodes is roughly a minute and a half on one core of John's machine (about 1M nodes per second measured); it is a job with progress, and the Judge budget is an arena-level setting.
- Because search is stateless (ADR-0006), a review is reproducible and can resume at any ply.
- Knowledge becomes auditable data, which also makes the duck file's lesson log meaningful.

## Not building yet

- Real thresholds, XP values and the opening-window length (balance table; M5, John's input).
- Motif detection on Judge lines (M4/M5).
- "Duck explains" text generation beyond reason codes.
- Reviewing imported human games (M6 reuses this pipeline).
- M0 ships the contract, the pure `classify`/`select`/`apply_lesson` signatures with tests on trivial cases, and no Judge runs.

## Sources

1. Stockfish wiki, WDL model and "Useful data": https://official-stockfish.github.io/docs/stockfish-wiki/Useful-data.html
