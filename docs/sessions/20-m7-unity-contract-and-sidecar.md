# Session 20 · Unity readiness: C# models and the backend sidecar

Milestone: **M7** · Depends on: 00

## Goal

Generate C# models from the contracts, package the backend as a PyInstaller one-folder sidecar, and prove the launch protocol (free port, launch token, health check, kill on exit).

## Read first

- `docs/adr/0003-unity-strategy.md` (readiness checklist)
- `contracts/CLAUDE.md`
- `docs/adr/0011-security.md` (launch token)

## Areas touched

- clients/ or apps/unity/ generator setup (models only; hand-written transport and event dispatcher)
- packaging scripts and a CI job that builds the sidecar
- backend: `DG_PORT=0` prints the chosen port; parent-PID watchdog

## Acceptance criteria

- A tiny C# console (or Unity editor test) hatches a duck and plays back a match from the events, against the packaged sidecar.
- No GPL code in the Unity folder; the bundle ships the backend's license and source pointer.

## Test plan

- Contract tests from the C# side; a sidecar smoke test in CI on Windows.

## Risks

- IL2CPP cannot start processes (use Mono or a native launcher); OpenAPI Generator's Unity mode is experimental.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 20: Unity readiness: C# models and the backend sidecar.

Goal: Generate C# models from the contracts, package the backend as a PyInstaller one-folder sidecar, and prove the launch protocol (free port, launch token, health check, kill on exit).

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/20-m7-unity-contract-and-sidecar.md` in full, then the files it lists under "Read first". Confirm the dependencies (00) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
