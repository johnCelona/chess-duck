# ADR-0015 · Human players and real-time clocks

Status: Accepted (defaults decided 2026-11-21) · 2026-11-21 · Source: `docs/design/01-training-minigames-and-bullet-battle.md` section 4.1

## Context

Sparring and Bullet Battle (the player against their own duck, 1+0) put a human on a real clock. CLAUDE.md rule 6 and ADR-0007 say no wall-clock time may affect a result and that the server never measures time inside a game. Both rules were written for duck-versus-duck play. This ADR records the narrow exception a human player needs, so that it does not erode the rule for everything else.

## Options

1. **Treat the human's time as virtual too** (a fixed charge per move). Deterministic, but bullet without a real clock is not bullet.
2. **Measure the human's time in the domain.** Breaks the pure domain and makes duck decisions depend on wall-clock time.
3. **Measure in the service layer, pass it to the domain as data.** The human's move arrives as `(uci, elapsedMs)`; the domain charges it like any other number.

## Decision

Option 3, with these limits:

- **Where:** wall-clock time may be read only by an *interactive game session* service, through an injectable `Clock` port, and only to measure the human's elapsed time per move. Never in the domain, never in the match runner, never for a duck.
- **What the domain sees:** `HumanMove(uci, elapsed_ms)`. Charging, flag checks and end conditions are the same pure functions as for ducks. The duck's decision is a function of move history, its virtual clock, the seed and its mind, never of the human's time.
- **Never rated.** Games with a human participant carry `mode = sparring` and `rated = false`. No rating, anchor result or rating context may depend on them.
- **Replayable.** The stored game (human moves with their `elapsedMs`, the seed, the duck's settings) replays exactly; a golden test re-runs a stored sparring game and compares the duck's moves.
- **Fair start of the human's clock:** `humanElapsed = arrival − max(duckMovePublishedAt, previousHumanArrival + duckThinkMs)`, with a floor (placeholder 100 ms). A slow machine makes the game feel slower but charges neither side.
- **Not a job.** Sparring is an interactive session that waits for the human; it reuses the domain functions of ADR-0005/0006 but not the background runner of ADR-0007.
- **Contract (additive):** `MoveMade.by` already allows `human`; add `elapsedMs`. `GameFinished.termination` already reserves `resignation` and `abandoned`. Games gain `mode` and `rated` columns (migration with the session that builds this).
- **Thinking panel** is hidden during a sparring game and shown afterwards (client behaviour; no enforcement needed locally).

Defaults, decided 2026-11-21 (John, and built in `services/sparring.py`):
- **Practice Pond:** untimed by default; the player may pick a time control for both sides (presets 30s to 10 min, plus increment).
- **"You play" in Super Bullet Arena:** 30+0 for both sides, best of N with Armageddon (same rules as `domain/series.py`).
- **Timeout:** if the opponent has insufficient mating material, running out of time is a draw, as in standard rules.
- **Leaving:** an untimed game simply waits and can be resumed. In a timed game your clock keeps running; reopening it, or a timeout claim, ends it on time.
- **The human's clock** starts when the duck's move is recorded. The client shows it at once, a simplification of the formula above.
- **Promotion:** the client offers a choice when untimed and auto-queens when timed.
- **Storage:** sparring games use their own tables (`sparring_games`, `sparring_moves`, `sparring_series`, migration 0005), not `games`, because their rows do not name two ducks.
- **Not added:** `MoveMade.elapsedMs`. For a human move, `thinkMs` carries the measured time.
- **No relaxed clock yet.**

## Consequences

- Rule 6 stays absolute for everything a duck decides and every rated result; the exception is local and testable.
- Bullet Battle needs a second service and a few endpoints (`POST /sparring`, `POST /games/{id}/moves`, `resign`, `claim-timeout`), designed in its session.
- Online play between two humans is still out of scope; this ADR covers one human against their local duck.

## Not building yet

- The interactive session service, endpoints, premoves, handicaps and the staircase (design 01 packages D5, D6).
- Any hosted or multiplayer clock synchronisation.
