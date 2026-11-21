# ADR-0014 · Developer experience, configuration and data directory

Status: Accepted (John, 2026-11-21) · 2026-11-21

## Context

Running the app takes two terminals and the Windows-only `py` launcher (on John's machine `python` is the Microsoft Store stub). Host, port and reload are hard-coded. Data paths are computed from `__file__`, so engines and profiles are written inside `backend/`, which cannot work for a packaged sidecar and makes tests write next to the code. There is no logging setup and no way to get sample data.

## Decision

### One command

- `npm run dev` at the root runs `scripts/dev.mjs`, a small Node script with no dependencies that starts the backend (`uv run duckgambit serve --reload`) and Vite together, prefixes their output, and stops both when either exits or on Ctrl+C. It sets `DG_DATA_DIR=./data` and `DG_ENV=dev`.
- `npm run check` runs every gate CI runs (ADR-0012). `npm run gen` regenerates contracts and the TypeScript client.
- `uv run` is the cross-platform launcher: it finds or installs Python 3.12 and uses the locked environment, so nobody types `py` or `python`.
- The backend has one entry point, `duckgambit`, with subcommands: `serve`, `seed`, `export-contracts`, and later `calibrate` and `puzzles`.

### Configuration

One typed settings object (pydantic-settings), read from environment variables with the `DG_` prefix and an optional `.env` file (gitignored). Nothing else reads the environment.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DG_ENV` | `prod` | `dev` enables reload and the dev origin |
| `DG_HOST`, `DG_PORT` | `127.0.0.1`, `8000` | Bind address. Port `0` picks a free port and prints it (for the sidecar) |
| `DG_DATA_DIR` | per-user application data directory | Root of all mutable state |
| `DG_API_TOKEN` | unset | If set, required as a bearer token (ADR-0011) |
| `DG_ALLOWED_ORIGINS` | empty (`http://localhost:5173` and `http://127.0.0.1:5173` in dev) | Origin allowlist |
| `DG_MAX_ENGINES`, `DG_MAX_HASH_MB_TOTAL` | cores minus one (max 8), 1024 | Pool budget (ADR-0007) |
| `DG_LOG_LEVEL`, `DG_LOG_FORMAT` | `INFO`, `text` (`json` available) | Logging |
| `DG_LICHESS_ENABLED` | `false` | ADR-0010 |
| `DG_FAKE_ENGINE` | `false` | Use the in-process fake engine (tests, demos without Stockfish) |

### Data directory

All mutable state lives under one root, never in the source tree:

```
<data dir>/
  duckgambit.db          SQLite (ADR-0004), plus automatic pre-migration backups
  engines/<id>/<version>/  installed engine binaries and their license files
  packs/                 puzzle packs (ADR-0009)
  exports/               PGN and duck files written on request
  logs/
  tmp/                   downloads and staging; emptied at startup
  secrets/               fallback secret store, user-only permissions (ADR-0010)
```

In development the root is `./data` (gitignored). The engine manifest stays in the package because it is code-reviewed configuration, not data. The existing `backend/engines/installed` and `backend/config` folders are abandoned: both are gitignored day-one data on one machine; Stockfish is reinstalled into the new location with one click (or the folder is moved by hand).

### Logging

Standard-library logging, configured once: human-readable lines in development, one JSON object per line when `DG_LOG_FORMAT=json`, each with timestamp, level, logger, message and context fields (`job`, `match`, `game`, `engine`). A filter redacts authorization headers and token-shaped values. No extra dependency.

### Seed data

`duckgambit seed` creates a profile and two default ducks with different stat spreads, idempotently, so a fresh clone has something to play with. `--reset` wipes the development database first and refuses to run unless `DG_ENV=dev`.

### Folder-level context

Each top-level folder gets a short `CLAUDE.md` with the rules that apply there (`backend/`: layering and determinism; `apps/web/`: thin client, generated code is read-only; `contracts/`: generated, never edited by hand). The root `CLAUDE.md` stays under about 150 lines. Personal notes go in `CLAUDE.local.md` or `docs/architecture/`, both gitignored.

## Consequences

- John installs uv once (`winget install astral-sh.uv` or `pip install uv`).
- A fresh clone is `npm install`, `npm run dev`: uv creates the Python environment on first run.
- Because every path and port is a setting, tests run against a temporary data directory and the sidecar can run from a read-only install location.

## Not building yet

- Docker, dev containers, installers, auto-update.
- A settings UI; settings are environment only.
- Log shipping or metrics.
