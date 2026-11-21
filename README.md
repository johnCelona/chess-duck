# Duck Gambit

Hatch a duck, teach it chess, and send it into battle against other ducks. As your duck learns, you learn too.

Every duck plays with the same engine, Stockfish. **Stockfish itself never learns.** What you train is the duck's *decision layer*: its opening repertoire, the fixes you taught it, its style and how much risk it tolerates. That data decides which of the engine's candidate moves the duck plays, and every choice comes with a reason you can read.

Status: early. The foundation is in place: hatch ducks, run a deterministic 1-minute bullet match between two ducks on real Stockfish, watch it move by move with a "why did it play that" panel, and download the PGN. The product plan is in [`docs/duck-gambit-spec.md`](docs/duck-gambit-spec.md); the roadmap is in [`docs/sessions/`](docs/sessions/).

## Requirements

- Windows, macOS or Linux
- Node.js 22 or newer (26 recommended, see `.nvmrc`)
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python 3.12 for you. On Windows: `winget install astral-sh.uv` or `pip install uv`.

## Run

```bash
npm install
npm run dev
```

This starts the backend (http://127.0.0.1:8000) and the web app (http://localhost:5173) together. Then:

1. **Engines**: install Stockfish 19. It downloads from the official release, is checked against a pinned SHA-256, and is smoke-tested.
2. **Ducks**: hatch two ducks, or run `npm run seed`.
3. **Match**: start a bullet match and watch it. Download the PGN when it ends.

The same ducks, arena and seed always give the same games, on any computer: think time is a virtual clock converted to engine nodes, not real time.

All local data (the database, installed engines, logs) lives in `./data` during development. Delete that folder to start fresh.

## Test

```bash
npm run check        # every gate CI runs: lint, format, types, tests, contracts, build
uv run --project backend pytest backend/tests/real   # extra checks against an installed Stockfish
```

## Licenses

Duck Gambit's code is GPL-3.0-or-later (`LICENSE`). Stockfish (GPL-3.0) runs as a separate program downloaded from its official release; its license and a link to its source are shown on the Engines page. Third-party components are listed in `THIRD_PARTY_LICENSES.md`. Original art is licensed separately (`assets/LICENSE.md`).
