# Session 01 · Router, app shell and duck detail page

Milestone: **M1** · Depends on: 00

## Goal

Replace the hash switch with a real router and give each duck its own page: profile, stats, knowledge summary, rating with its context, recent games.

## Read first

- `apps/web/CLAUDE.md`
- `docs/adr/0002-contract-and-events.md`

## Areas touched

- apps/web/src/App.tsx
- apps/web/src/pages/*
- a new `GET /api/v1/ducks/{id}/games` (or a query on `/matches`)
- THIRD_PARTY_LICENSES.md (react-router)

## Acceptance criteria

- Routes: `/ducks`, `/ducks/:id`, `/match`, `/match/:id`, `/engines`; links and reloads work; unknown routes show a friendly page.
- Duck page shows level, stage, stat budget used/available, repertoire and puzzle-memory counts, rating with "provisional" and its rating context, and its last 10 games with result and PGN link.
- No chess logic added to the client.

## Test plan

- Web tests for routing and the duck page with a stubbed API.
- API test for the new games query, including ordering and paging.

## Risks

- Keep the router choice boring (react-router); it is a new dependency to record.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 01: Router, app shell and duck detail page.

Goal: Replace the hash switch with a real router and give each duck its own page: profile, stats, knowledge summary, rating with its context, recent games.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/01-m1-router-and-duck-pages.md` in full, then the files it lists under "Read first". Confirm the dependencies (00) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
