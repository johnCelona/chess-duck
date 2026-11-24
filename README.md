# Chess Duck

*Codename: Duck Gambit. The code, paths and packages keep that name.*

Raise a duck, learn chess together, and send it into battle against other ducks. Chess Duck is for people learning chess: you play **minigames** that teach it one idea at a time, and as your duck learns, you learn too.

> **Early development.** The game runs locally and everything may change.

## What you can do now

- **Hatch ducks** and switch between them at the Pond.
- **Play your duck** in the Practice Pond, with or without a clock.
- **Super Bullet Arena:** send your duck against challengers, or play a fast series against it yourself.
- **Minigame tests:** sixteen rough minigames to try, from how the pieces move to forks, checkmates and pawn endings. They are experiments: they save nothing and do not train your duck yet.
- **See why:** every move a duck makes comes with reasons you can read.

## Where it is going

- **Minigames that teach chess,** polished from the experiments that turn out to be fun, and tied to what your duck learns.
- **A story mode** about personally raising a duck, from its egg, learning the basics of chess along the way.
- **A duck that starts as a beginner.** See the limitation below.
- **Maybe later:** a choice of beginner or experienced start, and a full version with real art.

## Known limitation: new ducks are too strong

Every duck plays with the same engine, Stockfish, and **Stockfish itself never learns.** What you train is the duck's *decision layer*: its openings, the fixes you taught it, its style and how much risk it tolerates. That layer chooses among the engine's best moves, so even a newly hatched duck can be hard to beat.

The goal is a duck that plays like a real beginner, without random moves, and gets stronger as it finishes its training. The thinking so far is in [`docs/design/06-beginner-duck-and-starting-point.md`](docs/design/06-beginner-duck-and-starting-point.md).

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

1. Open the **Lab** (⚙), then **Engines**, and install Stockfish 19. It downloads from the official release, is checked against a pinned SHA-256, and is smoke-tested.
2. Go back to the title and **hatch a duck** (or run `npm run seed` for two demo ducks).
3. Try the **Practice Pond**, the **Arena**, or **Minigame tests** (the minigames need no engine).

The same ducks, arena and seed always give the same games, on any computer: think time is a virtual clock converted to engine nodes, not real time.

All local data (the database, installed engines, logs) lives in `./data` during development. Delete that folder to start fresh.

## More

Product plan: [`docs/duck-gambit-spec.md`](docs/duck-gambit-spec.md). Design: [`docs/design/`](docs/design/). Decisions: [`docs/adr/`](docs/adr/).

## Test

```bash
npm run check        # every gate CI runs: lint, format, types, tests, contracts, build
uv run --project backend pytest backend/tests/real   # extra checks against an installed Stockfish
```

## Licenses

Chess Duck's code is GPL-3.0-or-later (`LICENSE`). Stockfish (GPL-3.0) runs as a separate program downloaded from its official release; its license and a link to its source are shown on the Engines page. Third-party components are listed in `THIRD_PARTY_LICENSES.md`. Original art is licensed separately (`assets/LICENSE.md`).
