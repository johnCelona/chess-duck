# Session 15 · Judge review and critical moments ⚑

Milestone: **M5** · Depends on: 08

## Goal

Analyse finished games with a fixed Judge as a background job, classify mistakes by expected-score loss, and store annotations with best and refutation lines.

## Needs John ⚑

Review thresholds (inaccuracy, mistake, blunder) and how many moments to show.

## Read first

- `docs/adr/0008-review-and-coaching-pipeline.md`
- `backend/src/duckgambit/domain/review.py`
- `docs/design/01-training-minigames-and-bullet-battle.md` §3.3, packages D9

## Areas touched

- services/review.py (job, resumable per ply)
- migration: reviews, annotations (with lines)
- events `CriticalMomentFound`, `ReviewReady`
- `describe_punishment`, `is_drill_eligible`, `coach_note`

## Acceptance criteria

- Every finished game can be reviewed; the review records the Judge config; re-running gives the same annotations.
- Critical moments (default 3) come with the punishing reply and a coach's note mapped to a minigame.

## Test plan

- Fake-engine review tests; golden annotations for the walking-skeleton game; real-engine spot check.

## Risks

- Review cost: plies × Judge nodes; offer a quick-review preset.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 15: Judge review and critical moments.

Goal: Analyse finished games with a fixed Judge as a background job, classify mistakes by expected-score loss, and store annotations with best and refutation lines.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/15-m5-judge-review.md` in full, then the files it lists under "Read first". Confirm the dependencies (08) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
