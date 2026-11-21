# Session 05 · The training door: lessons, XP, stats and care v1 ⚑

Milestone: **M2** · Depends on: 02

## Goal

Turn `domain/lessons.apply_lesson` into the single door for every training change (knowledge, stat placement, XP, energy), persist lessons, and add the first care loop (energy, feeding).

## Needs John ⚑

Care pacing (design Q3), energy costs and food rewards, how much faster a coached duck grows (Q10).

## Read first

- `docs/design/01-training-minigames-and-bullet-battle.md` §2, §5, §7.1 (A6, A10), packages D1, D2
- `docs/adr/0008-review-and-coaching-pipeline.md`
- `backend/src/duckgambit/domain/lessons.py`

## Areas touched

- domain/lessons.py, domain/duck.py (care, food)
- migration for `lessons` (append-only) and lesson ids on knowledge rows
- services/training.py, API `POST /ducks/{id}/training-sessions`, `POST /ducks/{id}/feed`
- events `XpGained`, `StatTrained`, `CareChanged`, `DuckFed`

## Acceptance criteria

- Every knowledge, stat or XP change goes through one domain function and leaves a lesson row; the duck file includes the lesson log.
- Energy limits how many lessons fit; feeding refills it; nothing decays and nothing is ever lost (pillar: never punish).
- Level-ups fire `DuckLeveledUp` with points granted and blunder tolerance before/after.

## Test plan

- Domain tests for every lesson kind and care rule with fixed `now` values; migration test; API tests; golden event stream for one training session.

## Risks

- Balance numbers are placeholders; keep them in the balance table with a version bump.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 05: The training door: lessons, XP, stats and care v1.

Goal: Turn `domain/lessons.apply_lesson` into the single door for every training change (knowledge, stat placement, XP, energy), persist lessons, and add the first care loop (energy, feeding).

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/05-m2-training-door-and-care.md` in full, then the files it lists under "Read first". Confirm the dependencies (02) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
