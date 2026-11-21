# Session 12 · Puzzle packs and the answer-key builder ⚑

Milestone: **M4** · Depends on: 00

## Goal

Build curated packs from a locally downloaded Lichess puzzle CSV and key every legal move with the Judge, with resume and parallel leases.

## Needs John ⚑

Puzzle difficulty bands and pack themes.

## Read first

- `docs/adr/0009-puzzle-arena-data-pipeline.md`
- `backend/src/duckgambit/domain/puzzles.py`
- `backend/src/duckgambit/services/answer_keys.py`

## Areas touched

- cli `duckgambit puzzles build`, `duckgambit answer-keys` (resume, checkpoints, parallel leases)
- a starter pack (decide: committed vs release asset)
- pack goal type `fix-blunder` (design B5)

## Acceptance criteria

- A 500-puzzle pack builds reproducibly from the CSV and a seed; the first database move is applied; themes and rating filters work.
- Answer keys resume after interruption and record the Judge's engine, version, fingerprint and node budget.
- CC0 source credited in the pack and THIRD_PARTY_LICENSES.md.

## Test plan

- Tests on a tiny CSV fixture; fake-engine keys; one real run documented.

## Risks

- Keying time: about a minute per puzzle at 2M nodes per move on one core; budget it.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 12: Puzzle packs and the answer-key builder.

Goal: Build curated packs from a locally downloaded Lichess puzzle CSV and key every legal move with the Judge, with resume and parallel leases.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/12-m4-puzzle-packs.md` in full, then the files it lists under "Read first". Confirm the dependencies (00) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
