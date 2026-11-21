# Third-party licenses

Duck Gambit's own code is licensed under GPL-3.0-or-later (see `LICENSE`, ADR-0013).

Every dependency, tool and asset is listed here. **Add a row in the same commit that adds the dependency.** Exact versions live in `package-lock.json` and `backend/uv.lock`. No CC BY-NC or unknown-license assets (see `CLAUDE.md`).

## Downloaded at run time (never committed, never bundled)

| Component | License | Source | Notes |
| --- | --- | --- | --- |
| Stockfish 19 | GPL-3.0 | https://github.com/official-stockfish/Stockfish | Separate process, fetched from the official release by the pinned manifest. Its license file is kept beside the installed binary and its source link is shown in the Engines page |

## Backend runtime (Python)

| Package | License | Source | Used for |
| --- | --- | --- | --- |
| chess (python-chess) | GPL-3.0-or-later | https://github.com/niklasf/python-chess | Rules, notation, PGN, UCI protocol. **Copyleft: makes the backend GPL** |
| fastapi | MIT | https://github.com/fastapi/fastapi | HTTP API |
| starlette | BSD-3-Clause | https://github.com/Kludex/starlette | ASGI toolkit (via FastAPI) |
| uvicorn | BSD-3-Clause | https://github.com/Kludex/uvicorn | ASGI server |
| pydantic, pydantic-core | MIT | https://github.com/pydantic/pydantic | Wire schemas |
| pydantic-settings | MIT | https://github.com/pydantic/pydantic-settings | Environment settings |
| httpx | BSD-3-Clause | https://github.com/encode/httpx | Engine downloads |
| platformdirs | MIT | https://github.com/tox-dev/platformdirs | Default data directory |

Transitive runtime packages (anyio, h11, httpcore, idna, certifi (MPL-2.0), click, colorama, sniffio, typing-extensions, typing-inspection, annotated-types, python-dotenv) are MIT, BSD or MPL-2.0 licensed.

## Backend development tools

| Package | License | Source |
| --- | --- | --- |
| uv | MIT OR Apache-2.0 | https://github.com/astral-sh/uv |
| ruff | MIT | https://github.com/astral-sh/ruff |
| mypy | MIT | https://github.com/python/mypy |
| pytest | MIT | https://github.com/pytest-dev/pytest |
| hatchling | MIT | https://github.com/pypa/hatch |

## Web runtime (bundled into the web app)

| Package | License | Source | Used for |
| --- | --- | --- | --- |
| @lichess-org/chessground | GPL-3.0-or-later | https://github.com/lichess-org/chessground | Board UI, including its bundled cburnett piece images (GPLv2+). **Copyleft: makes the web app GPL** |
| react, react-dom | MIT | https://github.com/facebook/react | UI |
| react-router | MIT | https://github.com/remix-run/react-router | Screen routing (hash mode) |
| openapi-fetch | MIT | https://github.com/openapi-ts/openapi-typescript | Typed HTTP client over the generated schema |

## Web and contract development tools

| Package | License | Source |
| --- | --- | --- |
| vite, @vitejs/plugin-react | MIT | https://github.com/vitejs/vite |
| typescript | Apache-2.0 | https://github.com/microsoft/TypeScript |
| vitest | MIT | https://github.com/vitest-dev/vitest |
| @testing-library/react, @testing-library/jest-dom, @testing-library/user-event | MIT | https://github.com/testing-library |
| jsdom | MIT | https://github.com/jsdom/jsdom |
| oxlint | MIT | https://github.com/oxc-project/oxc |
| prettier | MIT | https://github.com/prettier/prettier |
| openapi-typescript | MIT | https://github.com/openapi-ts/openapi-typescript |
| @types/node, @types/react, @types/react-dom | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |

## Data

| Data | License | Source | Notes |
| --- | --- | --- | --- |
| Lichess puzzle database | CC0-1.0 | https://database.lichess.org/#puzzles | Not in the repo. Curated packs built from it credit Lichess (ADR-0009) |

## Art, audio and fonts

See `assets/manifest.json`. Currently empty: the board uses Chessground's bundled pieces and the duck avatar is a placeholder drawn in code.
