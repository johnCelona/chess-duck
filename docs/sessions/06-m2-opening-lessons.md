# Session 06 · Opening School: trained openings, shortlist and Opening Drill ⚑

Milestone: **M2** · Depends on: 05

## Goal

Build Opening School: teach a duck a named opening (play a line on the board or paste a PGN), store it as an `Opening` with its repertoire entries, pick a pre-game shortlist of up to 3 trained openings from saved data and the game seed (ADR-0016), and run the Opening Drill minigame (teach, quack-back recall) from design 01 §2.3.

## Needs John ⚑

Lesson UX and copy; how many moves a drill teaches at once; the preference numbers in ADR-0016; where opening names come from (own list or a public catalogue, license check).

## Read first

- `docs/duck-gambit-spec.md` §5.1
- `docs/adr/0016-trained-openings-and-pre-game-shortlist.md`
- `docs/design/03-player-journey.md` §4
- `docs/design/01-training-minigames-and-bullet-battle.md` §2.3, package D3
- `docs/design/02-position-memory-at-scale.md` (if present)
- `backend/src/duckgambit/domain/decision.py` (book step)

## Areas touched

- an interactive board (legal destinations from the server: `legalDestinations` per position)
- API for lesson positions and PGN import
- domain/lessons.py (opening kind), domain/knowledge.py (`Opening`, `RepertoireEntry.opening_id`), a pure `shortlist()` in the domain
- migration: `openings` table, `repertoire_entries.opening_id`, games' opening ids; duck doc and duck file version bumps with upcasters
- match runner: snapshot shortlist inputs at match creation, emit `OpeningsChosen`; DECISION_LAYER_VERSION and Balance.version bumps

## Acceptance criteria

- The player plays moves on a board; the server supplies legal destinations and SAN; the client has no rules.
- Finishing a drill adds an `Opening` (or +1 `times_trained`); a PGN with variations becomes that opening's entries, deduplicated, each tied to its lesson.
- A duck with no trained openings plays from the engine from move 1.
- Before each game the duck shortlists up to 3 trained openings (Black: at most one defence per White first move first); the same match and seed always give the same shortlist, also on replay.
- In a match, the duck plays only shortlisted lines (source `book`, reason names the opening) subject to its memory stat, and plays from the engine once off the line.

## Test plan

- Domain tests for PGN-to-repertoire, transpositions (same `position_key`), recall, preference terms and the seeded shortlist (fixed expected picks); a replay test that the shortlist is identical; API test for legal destinations; a service test where a taught line is played.

## Risks

- Large PGNs: cap entries per lesson; consider the opening-tree design in design 02 before importing thousands of games.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 06: Opening School: trained openings, shortlist and Opening Drill.

Goal: Build Opening School: teach a duck a named opening (play a line on the board or paste a PGN), store it as an `Opening` with its repertoire entries, pick a pre-game shortlist of up to 3 trained openings from saved data and the game seed (ADR-0016), and run the Opening Drill minigame (teach, quack-back recall) from design 01 §2.3.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/06-m2-opening-lessons.md` in full, then the files it lists under "Read first". Confirm the dependencies (05) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
