# Session 05 · The training door: lessons, XP and stats ⚑

Milestone: **M2** · Depends on: 02

## Goal

Turn `domain/lessons.apply_lesson` into the single door for every training change (knowledge, stat placement, XP) and persist lessons. No energy or care loop: out of scope (John, 2026-11-21; design 03 §7 Q3).

## Needs John ⚑

XP per activity, how much faster a coached duck grows (design 01 Q10). Energy is out of scope: nothing may slow the player down.

## Read first

- `docs/design/01-training-minigames-and-bullet-battle.md` §2, §5, §7.1 (A6, A10), package D1; `docs/design/03-player-journey.md` §2.1 (the top bar must visibly update)
- `docs/adr/0008-review-and-coaching-pipeline.md`
- `backend/src/duckgambit/domain/lessons.py`

## Areas touched

- domain/lessons.py, domain/duck.py
- migration for `lessons` (append-only) and lesson ids on knowledge rows
- services/training.py, API `POST /ducks/{id}/training-sessions`
- events `XpGained`, `StatTrained` on the `duck:{id}` stream (the Pond's top bar refetches on them)

## Acceptance criteria

- Every knowledge, stat or XP change goes through one domain function and leaves a lesson row; the duck file includes the lesson log.
- No energy, timers or limits on how often the player can train; nothing decays and nothing is ever lost (pillar: never punish).
- Level-ups fire `DuckLeveledUp` with points granted and blunder tolerance before/after.

## Test plan

- Domain tests for every lesson kind with fixed `now` values; migration test; API tests; golden event stream for one training session.

## Risks

- Balance numbers are placeholders; keep them in the balance table with a version bump.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 05: The training door: lessons, XP and stats.

Goal: Turn `domain/lessons.apply_lesson` into the single door for every training change (knowledge, stat placement, XP) and persist lessons. No energy or care loop: out of scope (John, 2026-11-21; design 03 §7 Q3).

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/05-m2-training-door-and-care.md` in full, then the files it lists under "Read first". Confirm the dependencies (02) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
