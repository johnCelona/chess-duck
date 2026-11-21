# ADR-0001 · Layering and repository layout

Status: Accepted (John, 2026-11-21) · 2026-11-21

## Context

At commit `9daabb4` the backend has one layer: API handlers hold state in module globals, validate, and call adapters directly. There is no domain, no service layer and no `Engine` interface, so nothing above the adapter can be tested without Stockfish. The web app sits at the repo root, the Python package is called `app`, tests only import from inside `backend/`, and user data is written into the source tree. We want a second client (Unity) later and a pure domain now.

## Options

1. **Leave the web app at the root**, add folders beside it. No move, but root config (tsconfig, vite, oxlint, index.html) stays mixed with backend, contracts and docs, and a second client has no obvious home.
2. **`web/` beside `backend/`.** Fine for one client.
3. **`apps/web` and `apps/unity`**, with the root `package.json` reduced to an npm workspace that forwards `dev`, `test`, `lint`, `build`. Clients are siblings; root commands keep working.

For Python: keep `backend/app/` (a generic name that collides with everything and is not installable) or move to a `src` layout with a real package name.

## Decision

Option 3, and a `src` layout for Python.

```
apps/
  web/                 React client (moved from the root, unchanged)
  unity/               README placeholder only (ADR-0003)
backend/
  pyproject.toml       dependencies, ruff, mypy, pytest config
  src/duckgambit/
    domain/            pure: ducks, knowledge, decision, clock, ratings, scoring, pgn, events
    services/          use cases and ports (Protocols): matches, ducks, jobs, engines
    adapters/          uci engine, fake engine, sqlite, installer, lichess (fake), secrets
    api/               FastAPI app, /api/v1 routers, wire schemas, error format
    cli/               headless tools: serve, seed, export-contracts, calibrate, answer-keys
  tests/               unit/, adapters/, api/, golden/
contracts/             generated openapi.json and events.schema.json, committed, drift-checked
assets/                art sources and their license manifest (ADR-0013)
scripts/               dev runner and codegen helpers (Node, no extra dependencies)
docs/                  spec, architecture/, adr/, sessions/
data/                  default dev data directory, gitignored (ADR-0014)
```

Dependency rule, enforced by a test that parses imports:

| Layer | May import |
| --- | --- |
| `domain` | standard library, `chess` and `chess.pgn` (pure rules and notation). Never `chess.engine`, `fastapi`, `pydantic`, `sqlite3`, `httpx`, `asyncio`, `datetime.now`, `random` module-level functions |
| `services` | `domain`, its own ports |
| `adapters` | `domain`, `services` ports, third-party I/O libraries |
| `api`, `cli` | everything; they are the composition roots |

The domain takes time (`now`), randomness (a seed) and ids as arguments; it never reads a clock or generates an id itself.

python-chess is GPL-3.0+, so the domain is GPL-3.0+ (ADR-0013). That is acceptable because clients never link the domain; they speak HTTP.

Moves happen in commits of their own with no content changes, per CLAUDE.md.

## Consequences

- One mechanical commit touches every path today; from then on a Unity client, a second web surface or a CLI all have a place.
- `npm run dev|test|lint|build` at the root keep working through the workspace, so CLAUDE.md's commands stay valid.
- `pip install -e backend` (or `uv sync`) makes `duckgambit` importable from anywhere, which fixes the broken documented pytest command.
- Folder-level `CLAUDE.md` files (`backend/`, `apps/web/`, `contracts/`) carry local rules so the root file stays short.

## Not building yet

- No monorepo tooling (Nx, Turborepo); npm workspaces are enough for one web app.
- No separate Python packages per layer; folders plus the import test are enough until something needs to ship alone.
- No `apps/unity` content beyond a README and the readiness checklist.
