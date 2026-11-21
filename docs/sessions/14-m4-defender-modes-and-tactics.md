# Session 14 · Defender modes, motif detectors and Tactics Drill

Milestone: **M4** · Depends on: 13

## Goal

Add Mate in N, Convert the Win and Survive against a fixed Defender, motif detectors as style rules, and the Tactics Drill minigame.

## Read first

- `docs/duck-gambit-spec.md` §5.1, §7.4
- `docs/design/01-training-minigames-and-bullet-battle.md` §2.4, package D8

## Areas touched

- services/puzzle_arena.py (play-out modes via the match runner with goal end conditions)
- domain/rules.py (fork, pin, back-rank motifs)
- training door (motif lessons)

## Acceptance criteria

- Goal modes end on the goal (mate within N, win chance above threshold, eval above floor) and are reproducible.
- Motif bonuses come only from training and appear as reasons.

## Test plan

- Domain tests per detector on fixed positions; service tests for each goal mode on the fake engine.

## Risks

- Detectors misfire by design; measure their rating effect with the harness.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 14: Defender modes, motif detectors and Tactics Drill.

Goal: Add Mate in N, Convert the Win and Survive against a fixed Defender, motif detectors as style rules, and the Tactics Drill minigame.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/14-m4-defender-modes-and-tactics.md` in full, then the files it lists under "Read first". Confirm the dependencies (13) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
