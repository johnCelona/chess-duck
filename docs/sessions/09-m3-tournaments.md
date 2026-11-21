# Session 09 · Tournaments: round robin, Swiss, knockout

Milestone: **M3** · Depends on: 08

## Goal

Run multi-duck tournaments as background jobs with standings, using the `Scheduler` interface in `domain/tournament.py`.

## Read first

- `docs/duck-gambit-spec.md` §7.2
- `backend/src/duckgambit/domain/tournament.py`
- `docs/adr/0007-match-and-arena-runtime.md`

## Areas touched

- domain/tournament.py (Swiss with Buchholz tie-break, knockout with armageddon or replay rule)
- migration for tournaments, rounds, pairings
- events `RoundStarted`, `StandingsUpdated`
- API and a standings page

## Acceptance criteria

- A tournament is resumable at any game, like a match; pairings are seeded and reproducible.
- Standings update live through events; ratings update per rated game.

## Test plan

- Domain tests for pairing rules (no repeat pairings in Swiss, colour balance); service test of a small tournament on the fake engine; golden standings.

## Risks

- Event-log growth: consider the compact record mode from ADR-0004 for big tournaments.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 09: Tournaments: round robin, Swiss, knockout.

Goal: Run multi-duck tournaments as background jobs with standings, using the `Scheduler` interface in `domain/tournament.py`.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/09-m3-tournaments.md` in full, then the files it lists under "Read first". Confirm the dependencies (08) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
