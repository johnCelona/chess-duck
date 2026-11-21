# Session 08 · Calibration harness and real ratings ⚑

Milestone: **M3** · Depends on: 00

## Goal

Make ratings mean something: anchor ducks, a headless calibration tournament, a one-off tie to Stockfish UCI_Elo, a fitted curve from settings to rating, and replace the 1500 stub with a provisional rating from the curve.

## Needs John ⚑

Target rating bands for levels and stages (balance numbers).

## Read first

- `docs/adr/0006-strength-time-and-progression.md` (whole)
- `backend/src/duckgambit/domain/rating.py`
- `backend/src/duckgambit/services/matches.py`

## Areas touched

- cli `duckgambit calibrate`
- committed anchor table and fitted curve as data
- services for anchor matches using the job runner

## Acceptance criteria

- Anchor ducks are fixed, deterministic configurations; their round robin is reproducible from the seed.
- The UCI_Elo tie is offline, bulk, and recorded with sample sizes (it is not reproducible by nature).
- New ducks show a provisional rating predicted from their settings; the stub is gone.
- Clock policy and blunder-tolerance placeholders are revisited with measurements and the balance version bumped.

## Test plan

- Fake-engine tests for the harness mechanics; a documented real run with results committed as data.

## Risks

- CPU time: a meaningful calibration is hours of engine time; use the pool budget and resume.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 08: Calibration harness and real ratings.

Goal: Make ratings mean something: anchor ducks, a headless calibration tournament, a one-off tie to Stockfish UCI_Elo, a fitted curve from settings to rating, and replace the 1500 stub with a provisional rating from the curve.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/08-m3-calibration-harness.md` in full, then the files it lists under "Read first". Confirm the dependencies (00) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
