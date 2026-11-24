# Session 17 · XP curve, stages and level-up ⚑

Milestone: **M5** · Depends on: 08, 16

## Goal

Replace placeholder XP and stage numbers with tuned values, add stage advancement (`StageAdvanced`) and its unlocks, and make the growth from 2000 toward 2500 measurable with the harness.

## Needs John ⚑

The XP curve and stage feel; stage names.

## Read first

- `docs/adr/0006-strength-time-and-progression.md` §6
- `backend/src/duckgambit/domain/balance.py`

## Areas touched

- domain/balance.py (new version)
- events `StageAdvanced`
- harness runs per level

## Acceptance criteria

- Each lever (calculation, tolerance, knowledge) has a measured rating effect recorded as data.
- A documented path shows how many sets, fixes and League games move a duck from about 2000 to about 2500 in one rating context.

## Test plan

- Domain tests for level and stage math; a recorded harness run.

## Risks

- Do not promise numbers before measuring them (spec §6.3).

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 17: XP curve, stages and level-up.

Goal: Replace placeholder XP and stage numbers with tuned values, add stage advancement (`StageAdvanced`) and its unlocks, and make the growth from 2000 toward 2500 measurable with the harness.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/17-m5-xp-curve-and-stages.md` in full, then the files it lists under "Read first". Confirm the dependencies (08, 16) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
