# Session 19 · Learn from my games, and save duck games to Lichess

Milestone: **M6** · Depends on: 18, 06, 16

## Goal

Import a player's Lichess games to build a "mini-me" repertoire, feed their mistakes into Blunder Training, and save duck games to their Lichess account one at a time.

## Read first

- `docs/duck-gambit-spec.md` §5.3, §8
- `docs/design/02-position-memory-at-scale.md` (opening tree)
- `docs/design/01-training-minigames-and-bullet-battle.md package D15`

## Areas touched

- services/import.py (job, size caps)
- opening-tree aggregation (design 02)
- "Save to Lichess" action per game (public, unrated, rate-limited)

## Acceptance criteria

- Import works without linking (public games); linking only raises throughput.
- A mini-me duck plays the player's most frequent moves, weighted, subject to its memory stat.
- Saving is one explicit action per game; PGN download remains the fallback.

## Test plan

- Fake-adapter tests with recorded PGNs; repertoire-building tests on transpositions.

## Risks

- Thousands of games: use the aggregated tree from design 02 rather than one repertoire row per occurrence.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 19: Learn from my games, and save duck games to Lichess.

Goal: Import a player's Lichess games to build a "mini-me" repertoire, feed their mistakes into Blunder Training, and save duck games to their Lichess account one at a time.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/19-m6-import-games-and-mini-me.md` in full, then the files it lists under "Read first". Confirm the dependencies (18, 06, 16) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
