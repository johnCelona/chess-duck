# ADR-0012 · Quality system

Status: Proposed · 2026-11-21

## Context

At commit `9daabb4`: six backend tests that only run from inside `backend/`; `npm test` exits 1 because there are no test files; no CI; no Python linter, formatter or type checker; Python dependencies declared nowhere. CLAUDE.md requires lint, web tests, build and backend tests to pass before a task is done, and that CI never needs a real Stockfish.

## Options

- **Type checker**: mypy 2.4 (mature, strict mode); pyright (fast, needs Node, already present); ty (Astral; its README says beta with no stable API [1]). Choose the boring one.
- **Python environment**: pip plus a requirements file (no lockfile for transitive pins without extra tooling) or uv 0.13 (lockfile, cross-platform `uv run`, installs Python itself) [2].
- **Fake engine**: only an in-process fake (fast, but never exercises the real subprocess code) or also a fake UCI program (tests the adapter, pool, timeouts and kill paths without Stockfish).
- **Contract tests**: schema drift check only; or property-based fuzzing with schemathesis as well.
- **End to end**: a browser test (Playwright) or an in-process API walk-through.

## Decision

### Test pyramid

| Level | What | Engine | Runs in CI |
| --- | --- | --- | --- |
| Domain unit | Decision layer, clock, Glicko-2, PGN, scoring, upcasters. Plain values, fixed seeds, named by behaviour | none | yes |
| Architecture | Import rules of ADR-0001; "no string-typed engine option is settable" | none | yes |
| Service | Match runner, jobs, repositories (in-memory and SQLite on a temp file) | `FakeEngine` (in-process, deterministic: scores derive from a hash of the position and move) | yes |
| Adapter | UCI adapter and pool against `fake_uci.py`, a small script that speaks UCI over stdin/stdout and can be told to hang, crash or answer slowly | fake UCI process | yes |
| Contract | `contracts/` regenerated and compared; responses validated against their schemas through the test client; the event union round-trips | fake | yes |
| End-to-end smoke | One test through the HTTP API: hatch two ducks, create a match, read the event stream to `MatchFinished`, fetch the PGN | fake | yes |
| Golden | The smoke match's PGN and event log (`stream`, `seq`, `type`, `data`) compared to committed files; `--update-golden` rewrites them | fake | yes |
| Real engine | A handful of tests marked `real_engine`: handshake, reproducibility of a known search, a full short game | Stockfish | skipped when not installed; never in CI |
| Web | Vitest and Testing Library for components; `tsc` over the generated client | none | yes |

A golden change is a behaviour change: it must be explained in the commit, and if it could alter a move for the same inputs it bumps `DECISION_LAYER_VERSION` (ADR-0005).

### Tooling

- **uv** manages the backend environment with a committed `uv.lock`; `pyproject.toml` stays standard so `pip install -e "backend[dev]"` also works.
- **ruff** for lint and format (replacing the `prettier ... backend` script, which never touched Python).
- **mypy**, strict for `domain` and `services`, standard elsewhere.
- **pytest** with the anyio plugin for async tests.
- Web: oxlint, prettier, `tsc -b`, vitest (unchanged tools; add the missing tests and a vitest config).
- **pre-commit** config (ruff, prettier, oxlint, contract drift) is provided and optional; CI is the gate.

### CI (GitHub Actions)

One workflow on push and pull request. Matrix: `ubuntu-latest`, `windows-latest`, `macos-latest`; Python 3.12; Node 26 (current LTS). Steps: install (uv sync, npm ci), ruff check, ruff format check, mypy, pytest, contract drift, oxlint, prettier check, tsc, vitest, vite build. Actions pinned to current majors (checkout v7, setup-node v7, setup-uv v10) [3]. No job downloads or runs Stockfish.

### Definition of done for any session

`npm run check` at the root runs everything CI runs. A phase is not done until it passes and the changed behaviour has been exercised against the running app.

## Consequences

- Two fakes to maintain. The in-process one keeps most tests in milliseconds; the process-level one is the only way to test kill-on-timeout honestly.
- John needs uv installed (one command). Without it, pip still works but does not use the lockfile.
- Three-OS CI catches path and process differences early, which matters because the first user machine is Windows and the first CI machine is Linux.

## Not building yet

- Browser end-to-end tests, visual regression, load tests.
- schemathesis fuzzing (add when the API is larger than a handful of routes).
- Coverage thresholds, mutation testing.
- Release automation and packaging.

## Sources

1. ty: https://github.com/astral-sh/ty
2. uv: https://docs.astral.sh/uv/
3. GitHub runner images and action releases: https://github.com/actions/runner-images
