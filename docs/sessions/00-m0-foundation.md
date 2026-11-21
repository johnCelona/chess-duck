# Session 00 · M0 Foundation (done)

Milestone: **M0** · Depends on: none

## Goal

Audit, architecture decisions, contracts, domain and persistence skeleton, decision layer, deterministic match runner, walking skeleton, CI. Completed on branch `m0-foundation`; this file records what exists so later sessions can rely on it.

## Read first

- `docs/adr/README.md`
- `docs/design/01-training-minigames-and-bullet-battle.md`

## Areas touched

- everything

## Acceptance criteria

- Hatch a duck in the web UI; it is persisted with a default stat spread and a provisional rating (1500?).
- Start a duck-vs-duck bullet match on a virtual 1-minute clock with the installed Stockfish; watch it stream onto a chessground board with clocks and a thinking panel; stop and resume it.
- The game is saved with per-move metadata and a downloadable PGN with evals, clocks, seed and rating context.
- The same ducks, arena and seed reproduce the same game, move for move and node for node (verified on real Stockfish 19, Windows).
- `npm run check` passes; CI runs it on Linux, Windows and macOS without an engine.

## Test plan

- Backend: unit, architecture, adapter (fake UCI process), service, API, contract and golden tests; `backend/tests/real` against an installed engine.
- Web: playback reducer and player, page tests with a stubbed API.

## Risks

- Cross-OS node determinism is only verified on Windows; `backend/tests/real` on macOS and Linux will tell.
- uvicorn's code reload did not complete in an automated, non-interactive shell; verify `npm run dev` reload in a normal terminal.

## Notes

Reading order for newcomers: spec → ADR-0001, 0002, 0005, 0006, 0007 → `backend/CLAUDE.md` → `apps/web/CLAUDE.md`.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 00: M0 Foundation (done).

Goal: Audit, architecture decisions, contracts, domain and persistence skeleton, decision layer, deterministic match runner, walking skeleton, CI. Completed on branch `m0-foundation`; this file records what exists so later sessions can rely on it.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/00-m0-foundation.md` in full, then the files it lists under "Read first". Confirm the dependencies (none) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
