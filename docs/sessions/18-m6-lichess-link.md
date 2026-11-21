# Session 18 · Lichess link (OAuth with PKCE) ⚑

Milestone: **M6** · Depends on: 00

## Goal

Implement the Lichess HTTP adapter behind `LichessPort`, OAuth with PKCE in the backend, a SecretStore on the OS credential store, and link/unlink with revoke.

## Needs John ⚑

Privacy: what we store about linked accounts and imported games (spec §12, item 8).

## Read first

- `docs/adr/0010-lichess-integration.md` (whole)
- `backend/src/duckgambit/services/lichess.py`
- `backend/src/duckgambit/adapters/lichess/fake.py`

## Areas touched

- adapters/lichess/http.py (one request at a time, User-Agent, 429 back-off)
- adapters/secrets (keyring or a user-only file fallback)
- API `/integrations/lichess/*`
- migration: integration_links (never tokens)

## Acceptance criteria

- Off unless `DG_LICHESS_ENABLED=true`; zero scopes requested; tokens never appear in the database, logs or any response.
- Unlink revokes the token and deletes it locally even if revoke fails.
- Re-verify the Lichess facts in ADR-0010 against the live docs before building.

## Test plan

- Contract tests run the same suite against the fake and (manually, opt-in) the real adapter; log redaction test.

## Risks

- Lichess accepting `http://127.0.0.1` redirects is implementation behaviour, not documented contract.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 18: Lichess link (OAuth with PKCE).

Goal: Implement the Lichess HTTP adapter behind `LichessPort`, OAuth with PKCE in the backend, a SecretStore on the OS credential store, and link/unlink with revoke.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/18-m6-lichess-link.md` in full, then the files it lists under "Read first". Confirm the dependencies (00) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
