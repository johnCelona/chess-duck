# Session 11 · Bullet sparring: the player against their duck ⚑

Milestone: **M3** · Depends on: 03, ADR-0015 accepted

## Goal

Implement ADR-0015: an interactive game session where the player plays their own duck at 1+0, with a real clock for the human, the duck on its virtual clock, handicaps and the fair-fight staircase.

## Needs John ⚑

Sparring defaults (Q6): time odds, relaxed clock, starting handicap; the outgrown celebration (Q11).

## Read first

- `docs/adr/0015-human-players-and-real-time-clocks.md`
- `docs/design/01-training-minigames-and-bullet-battle.md` §4.1, §4.3, packages D5, D6

## Areas touched

- services/sparring.py (not a job)
- API `POST /sparring`, `POST /games/{id}/moves`, `resign`, `claim-timeout`
- interactive board with server-supplied legal moves, one premove
- events `TrainerOutgrown`

## Acceptance criteria

- The duck's moves never depend on the human's time; a stored sparring game replays the duck's moves exactly (golden test).
- Sparring games are unrated; handicap is one number ("younger duck"); the staircase suggests the next handicap.
- The thinking panel is hidden during play and shown afterwards.

## Test plan

- Domain tests with recorded `elapsedMs`; service tests with an injected clock; replay golden test.

## Risks

- Latency and fairness on slow machines (formula in ADR-0015).

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 11: Bullet sparring: the player against their duck.

Goal: Implement ADR-0015: an interactive game session where the player plays their own duck at 1+0, with a real clock for the human, the duck on its virtual clock, handicaps and the fair-fight staircase.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/11-m3-bullet-sparring.md` in full, then the files it lists under "Read first". Confirm the dependencies (03, ADR-0015 accepted) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
