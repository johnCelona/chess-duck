# Session 16 · Blunder Training ⚑

Milestone: **M5** · Depends on: 15, 05

## Goal

John's minigame: show the duck's blunder, the opponent's punishing reply and why it hurts; the player finds the fix; the duck learns it (puzzle memory) and proves it in a lesson check; spaced re-checks follow.

## Needs John ⚑

Card size and tone (Q8), what happens when the duck's blunder was a taught move (Q9), emotes and copy.

## Read first

- `docs/design/01-training-minigames-and-bullet-battle.md` §3 (whole), packages D10, D11, D12
- `backend/src/duckgambit/domain/decision.py` (memory source)

## Areas touched

- migration: drill_items, drill_attempts
- services/blunder_training.py
- API for cards, attempts, hints, checks
- events `FixAttempted`, `HintRevealed`, `FixTaught`, `LessonChecked`, `DrillItemScheduled`
- web card flow with emote hooks

## Acceptance criteria

- A card never reveals the best move before an attempt; any move that keeps the evaluation is accepted.
- A taught fix is written through the training door and is played by the duck in a lesson check with a fixed seed (source `memory`).
- Failing costs nothing; hints reduce the reward; re-checks are scheduled in sessions, not days.
- Blunder tolerance still comes only from level and stage; training it is through XP.

## Test plan

- Domain tests for eligibility, scheduling and grading; service tests on the fake engine; a golden card session.

## Risks

- Exact-position memory only fires in the same position; see design 02 for generalisation.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 16: Blunder Training.

Goal: John's minigame: show the duck's blunder, the opponent's punishing reply and why it hurts; the player finds the fix; the duck learns it (puzzle memory) and proves it in a lesson check; spaced re-checks follow.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/16-m5-blunder-training.md` in full, then the files it lists under "Read first". Confirm the dependencies (15, 05) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
