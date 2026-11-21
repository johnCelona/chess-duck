# ADR-0013 · Licensing and assets

Status: **Open: John decides the license** · 2026-11-21 · Not legal advice

## Context

The repo has no LICENSE and no `THIRD_PARTY_LICENSES.md`. The code already depends on GPL software:

| Component | License | How we use it | Effect |
| --- | --- | --- | --- |
| python-chess (`chess`) | GPL-3.0-or-later [1] | Imported by the backend (rules, PGN, UCI) | The backend, as distributed, must be GPL-3.0-compatible |
| Chessground | GPL-3.0-or-later; its README: "your combined work may be distributed only under the GPL" [2] | Bundled into the web app | The web app, as distributed, must be GPL |
| Stockfish | GPL-3.0 [3] | Separate process, downloaded at run time from the official release | Our code is not a derivative; if we ever bundle or mirror the binary we must ship its license and source pointer |
| FastAPI, Starlette, uvicorn, pydantic, httpx, React, Vite, TypeScript, vitest, oxlint, prettier | MIT, BSD or Apache-2.0 | Libraries and tools | Notices only |

So the GPL question is already decided by dependencies for both existing programs, independent of Stockfish. Avoiding it would mean replacing python-chess (a large rewrite of rules, PGN and UCI handling) and Chessground (a new board).

## Options

1. **GPL-3.0-or-later for the whole repo.** Matches both dependencies. Anyone may use, modify and redistribute, including commercially, provided they pass on the source. John can still sell the game; he cannot stop others from redistributing the code.
2. **AGPL-3.0-or-later.** As 1, plus anyone who *hosts* a modified version must publish the source. Lichess uses it. Relevant only if hosted clones are a worry.
3. **Proprietary or permissive.** Not available while python-chess and Chessground are in the tree.

A Unity client is a separate question (ADR-0003): a separate program speaking HTTP to the backend is, on the FSF's published reading, normally a separate work, so it could carry a different license. Bundling the GPL backend with it still obliges us to provide the backend's source and license text.

**Art is not code.** Images, animation sources and audio can be licensed separately from the GPL code they ship beside, as Lichess does. That keeps John's duck art under his control even though the code is GPL.

## Recommendation (the default if John has no objection)

- **Code: GPL-3.0-or-later**, `LICENSE` at the root, SPDX identifier in `package.json` and `pyproject.toml`.
- **Original art and audio: all rights reserved for now**, stated in `assets/LICENSE.md`, to be revisited before any public release. Nothing forces an early choice.
- **Unity client license: undecided until M7.** Keep it GPL-free so the choice stays open.

## Decision (mechanical parts, not waiting on John)

1. **`THIRD_PARTY_LICENSES.md`** at the root lists every runtime dependency, dev tool and asset with name, version, license and source URL. Adding a dependency without a line there fails review. The Engines page keeps showing Stockfish's license and source link.
2. **Switch to the maintained Chessground package.** The unscoped `chessground` on npm stopped at 9.2.1; current releases are `@lichess-org/chessground` (10.5.0) [2].
3. **Remove the Vite template leftovers** (`hero.png`, `react.svg`, `vite.svg`, `icons.svg`): unused third-party logos of unclear license.
4. **Asset rules**: nothing under CC BY-NC or an unknown license. Piece sets must be our own or GPL-compatible. From Lichess's set list [4]: cburnett, merida and mono (GPLv2+), mpchess (GPLv3+), fantasy, spatial and celtic (MIT), chessnut (Apache-2.0) and rhosgfx (CC0) are usable; horsey, california, maestro, staunty and most of the popular ones are CC BY-NC-SA and are not. Until John supplies art, the board uses Chessground's bundled default (cburnett).
5. **Art pipeline and naming**, consumable by web and Unity:

   ```
   assets/
     LICENSE.md                      license of our own art
     manifest.json                   one entry per asset: id, path, author, license, source
     ducks/<species>/<skin>/         idle.svg, thinking.svg, victory.svg, sulk.svg, portrait.svg
     pieces/<set>/                   wK.svg wQ.svg wR.svg wB.svg wN.svg wP.svg bK.svg … bP.svg
     boards/<theme>/                 board.svg or light.svg + dark.svg
     animations/<name>/              source/ (editor files) and export/ (sprite sheets or JSON)
     audio/<name>.ogg
   ```

   Lowercase kebab-case names; SVG as the vector source of truth with square view boxes; states named after the events that trigger them (`victory` for `MatchFinished`, and so on), so both clients map events to art the same way. The web app reads from `assets/` through a build alias; Unity imports the same files. The avatar in a duck is a set of ids (`species`, `skin`, `accessories`), never a file path.

## Consequences

- Under GPL the project is open source in practice; a "closed" commercial release of the current stack is not possible.
- Keeping art separately licensed preserves the main thing a clone could not copy.
- The manifest makes license audits a file read, and gives Unity a stable index of assets.

## Not building yet

- Any art, animation or audio. M0 adds the folders, the manifest schema with zero or placeholder entries, and the rules.
- Contributor agreements, trademark, store listings.
- A decision on the Unity client's license.

## Sources

1. python-chess: https://github.com/niklasf/python-chess
2. Chessground: https://github.com/lichess-org/chessground
3. Stockfish: https://github.com/official-stockfish/Stockfish
4. Lichess asset licenses: https://github.com/lichess-org/lila/blob/master/COPYING.md
5. GNU GPL FAQ: https://www.gnu.org/licenses/gpl-faq.en.html
