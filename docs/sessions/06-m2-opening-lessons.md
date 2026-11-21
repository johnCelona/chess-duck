# Session 06 · Opening lessons and Opening Drill ⚑

Milestone: **M2** · Depends on: 05

## Goal

Teach a duck openings: play a line on the board or paste a PGN, store it as repertoire, and run the Opening Drill minigame (teach, quack-back recall) from design 01 §2.3.

## Needs John ⚑

Lesson UX and copy; how many moves a drill teaches at once.

## Read first

- `docs/duck-gambit-spec.md` §5.1
- `docs/design/01-training-minigames-and-bullet-battle.md` §2.3, package D3
- `docs/design/02-position-memory-at-scale.md` (if present)
- `backend/src/duckgambit/domain/decision.py` (book step)

## Areas touched

- an interactive board (legal destinations from the server: `legalDestinations` per position)
- API for lesson positions and PGN import
- domain/lessons.py (opening kind)

## Acceptance criteria

- The player plays moves on a board; the server supplies legal destinations and SAN; the client has no rules.
- A PGN with variations becomes repertoire entries for the chosen colour, deduplicated, each tied to its lesson.
- In a match, the duck plays taught moves (source `book`) subject to its memory stat, visible in the thinking panel.

## Test plan

- Domain tests for PGN-to-repertoire, transpositions (same `position_key`), and recall; API test for legal destinations; a service test where a taught line is played.

## Risks

- Large PGNs: cap entries per lesson; consider the opening-tree design in design 02 before importing thousands of games.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 06: Opening lessons and Opening Drill.

Goal: Teach a duck openings: play a line on the board or paste a PGN, store it as repertoire, and run the Opening Drill minigame (teach, quack-back recall) from design 01 §2.3.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/06-m2-opening-lessons.md` in full, then the files it lists under "Read first". Confirm the dependencies (05) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
