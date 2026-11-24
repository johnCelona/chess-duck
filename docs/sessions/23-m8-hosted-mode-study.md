# Session 23 · Hosted mode: feasibility study (optional) ⚑

Milestone: **M8** · Depends on: most of M1–M6

## Goal

Decide whether and how to host Duck Gambit for friends without installs, using the hosted checklist in ADR-0011 and the WebGL/mobile constraints in ADR-0003. Output is an ADR, not code.

## Needs John ⚑

Whether to host at all, and the budget.

## Read first

- `docs/adr/0011-security.md` ("If the service is ever hosted")
- `docs/adr/0003-unity-strategy.md`
- `docs/adr/0004-persistence-and-data-model.md` (Postgres adapter)

## Areas touched

- docs/adr/ (new ADR)

## Acceptance criteria

- A costed recommendation: accounts, per-user quotas, engine sandboxing, Postgres adapter, privacy, hosting cost per active player.

## Test plan

- n/a (study)

## Risks

- Hosting changes the threat model completely; it is not a configuration switch.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 23: Hosted mode: feasibility study (optional).

Goal: Decide whether and how to host Duck Gambit for friends without installs, using the hosted checklist in ADR-0011 and the WebGL/mobile constraints in ADR-0003. Output is an ADR, not code.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/23-m8-hosted-mode-study.md` in full, then the files it lists under "Read first". Confirm the dependencies (most of M1–M6) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
