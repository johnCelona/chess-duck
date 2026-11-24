# Session 13 · Puzzle Arena: Candidate Showdown ⚑

Milestone: **M4** · Depends on: 12

## Goal

Ducks submit ranked top-5 ideas on the same puzzles; score by answer-key lookup; show arrows, an idea map and puzzle ratings.

## Needs John ⚑

Scoring presentation and copy.

## Read first

- `docs/duck-gambit-spec.md` §7.4
- `backend/src/duckgambit/domain/puzzles.py` (score_showdown)
- `backend/src/duckgambit/domain/decision.py` (rank)

## Areas touched

- services/puzzle_arena.py (job)
- events `PuzzleStarted`, `CandidatesSubmitted`, `PuzzleScored`
- puzzle ratings (Glicko-2, kind `puzzle`, scoped to pack)
- web arena view

## Acceptance criteria

- Every duck searches with the same arena settings (`equalEngine`); scoring is a lookup.
- Spectators see each duck's arrows (thick for #1), the Judge's verdict on any clicked move, and the scoreboard.
- "Beat the duck": the player answers first, then sees the ducks' ideas.

## Test plan

- Service test on the sample pack with the fake engine; golden event stream; web tests for arrows data.

## Risks

- Puzzle ratings only compare within one pack.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 13: Puzzle Arena: Candidate Showdown.

Goal: Ducks submit ranked top-5 ideas on the same puzzles; score by answer-key lookup; show arrows, an idea map and puzzle ratings.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/13-m4-candidate-showdown.md` in full, then the files it lists under "Read first". Confirm the dependencies (12) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
