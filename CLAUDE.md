# Duck Gambit

A chess training game. Players hatch a duck, teach it chess, and battle other ducks; the player learns as the duck does. Every duck runs on the same base engine (Stockfish). Stockfish does not learn, so "training" shapes a **decision layer** on top of it: opening book, principles, tactic motifs, blunder tolerance, style.

Status: early skeleton. Built: Python engine service plus an Engines page (install Stockfish from a pinned manifest, tune settings, "Test engine"). Planned: ducks, matches and tournaments, Puzzle Arena, review and coaching, a Lichess link, and possibly a Unity front end. The product spec is in `docs/`. Layout and other decisions are recorded in `docs/adr/`.

## Commands

- Install web deps: `npm install`
- Web dev server: `npm run dev` (http://localhost:5173, proxies `/api` to 127.0.0.1:8000)
- Backend (Python 3.12): `cd backend && python run.py` (Windows launcher: `py run.py`)
- Web tests: `npm test` (vitest). Backend tests: `python -m pytest backend/tests`
- Lint: `npm run lint` (oxlint). Format web code: `npm run format`
- Before calling a task done, all of these must pass: lint, `npm test`, `npm run build`, backend tests.

## Layout (verify before relying on it)

- `src/`: web app (Vite, React, TypeScript, chess.js for rules, chessground for the board)
- `backend/`: Python service (engines, API) with tests in `backend/tests`
- `docs/`: spec, architecture notes, ADRs (`docs/adr/`), session briefs (`docs/sessions/`)
- `engines/installed/`: downloaded engine binaries. Gitignored, never commit.

If this file and the repo disagree, say so and fix whichever is wrong.

## Tracked vs local notes

- **Tracked (committed, changed by commits):** `CLAUDE.md` here and in any folder, the spec, ADRs (`docs/adr/`), session briefs (`docs/sessions/`). Anything a future session must rely on goes here.
- **Local (gitignored, stays on this PC):** `docs/architecture/` (investigation and working notes such as audits and research), `CLAUDE.local.md` in any folder, any `*.local.md`.
- A tracked file must stand on its own: never make it depend on a local note. Copy the conclusion into the ADR instead of linking to the note.

## Architecture rules

These are the load-bearing ones. Break one only with an ADR in `docs/adr/`.

1. **Layering.** Domain (pure Python: ducks, knowledge, move selection, scoring, ratings) has no I/O and no framework imports. Services orchestrate. Adapters wrap the outside world (UCI engines, database, Lichess). The API is thin. Dependencies point inward.
2. **Clients are thin.** The React app now and a possible Unity app later only call the versioned API and render events. No game rules, scoring, or rating math in a client.
3. **The domain emits semantic events** (e.g. `DuckHatched`, `MoveChosen`, `MatchFinished`, `DuckLeveledUp`). It never knows about animation or UI. Clients decide how to present events.
4. **Contract first.** API and event schemas are the source of truth. Generated clients are never hand-edited.
5. **Engines are replaceable** behind one `Engine` interface. The duck's search, the Judge (grader) and the Defender (fixed opponent) are configurations of that interface, not forks of code.
6. **Determinism.** Anything that affects a result (move choice, scoring, tournaments) takes an explicit seed and uses node or depth limits, never wall-clock time. Bullet clocks use a virtual clock, not real time.
7. **Local-first persistence** with schema versions and migrations. Never change a stored shape without a migration.
8. **External services sit behind ports** and are off by default. Lichess is optional. Tests use fakes. Tokens never go in the repo, logs, or the client bundle.

## Engine safety (non-negotiable)

- Never forward raw UCI text from a user. Only allowlisted options are user-settable, each clamped to the engine's advertised range and to server-side caps.
- Options that take file paths or write files (`EvalFile`, `SyzygyPath`, `Debug Log File`, etc.) are server-controlled only.
- Engines are downloaded only from the committed manifest, with pinned sha256, extracted safely (guard against path traversal).
- Cap total Threads and Hash across all running engines. Always time out and clean up subprocesses.

## Testing

- Use the fake UCI engine in tests. CI must never need a real Stockfish. Real-engine tests are skipped when none is installed.
- Domain logic gets plain unit tests with fixed seeds. Name tests by behavior.
- Anything user-visible in a result (PGN, event streams) gets a golden-file test.

## Licensing and assets

- Stockfish and Chessground are GPL-3.0. Record every new dependency or asset license in `THIRD_PARTY_LICENSES.md`.
- No CC BY-NC (non-commercial) or unknown-license assets. Piece sets must be GPL-compatible or our own art. Ask John first.
- Keep Stockfish a separate downloaded process; do not vendor binaries into the repo.

## How to work here

- Plan first for anything that touches more than three files or a public contract. Record architectural decisions as short ADRs.
- Small commits with imperative messages. No drive-by refactors. Keep moves and renames in their own commits.
- Decide mechanical engineering questions yourself and record why. Ask John (lead developer) about game feel, balance numbers, art, copy, licensing, and anything that changes the product. Batch questions into one message.
- Research current facts (Lichess API and terms, UCI options, library versions) instead of trusting memory. Cite sources in ADRs.
- Do not do UI polish or animation unless asked; John owns that.
- Keep this file short (under about 150 lines). Move detail into `docs/` and link to it.

## Glossary

- **Duck**: a player's trainable chess agent: stats, knowledge, growth state.
- **Decision layer**: the pipeline that picks a duck's move: book, engine candidates, blunder-tolerance filter, style/principle/motif scoring, seeded sampling.
- **Knowledge**: a duck's repertoire (keyed by normalized FEN), principles, motifs, puzzle memory.
- **Judge**: fixed, stronger engine setting that grades moves identically for every duck.
- **Defender**: fixed engine opponent used in convert-the-win and survive exercises.
- **Arena**: match settings shared by all ducks (engine, limit, lines, threads, hash, format).
- **Answer key**: precomputed Judge score for every legal move of a puzzle position.
- **Candidate Showdown**: puzzle mode where each duck submits ranked top-5 moves.
