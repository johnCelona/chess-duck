# Session 04 · Duck file import, export and sharing

Milestone: **M1** · Depends on: 01

## Goal

Let players share ducks as files: export, import with validation, and fix the imported-rating hazard noted in design 01 §7.3.

## Read first

- `docs/adr/0004-persistence-and-data-model.md` (duck file)
- `backend/src/duckgambit/domain/duckfile.py`

## Areas touched

- apps/web import UI (file picker → JSON → `POST /api/v1/ducks/imports`)
- domain/duckfile.py and services/ducks.py

## Acceptance criteria

- Import shows a clear error for a tampered or newer file; success shows the new duck with its origin.
- Imported ratings are never trusted: the duck starts provisional in every local context (document the rule in ADR-0004).
- Round trip (export → import) keeps name, avatar, stats, repertoire, puzzle memory, principles and motifs.

## Test plan

- Domain tests already cover validation; add API and web tests for the flow.

## Risks

- File size: enforce a cap before parsing (the API already caps bodies at 8 MB).

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 04: Duck file import, export and sharing.

Goal: Let players share ducks as files: export, import with validation, and fix the imported-rating hazard noted in design 01 §7.3.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/04-m1-duck-files.md` in full, then the files it lists under "Read first". Confirm the dependencies (01) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
