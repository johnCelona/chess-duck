# Web client rules

React 19 + Vite + TypeScript. This is a thin client (root `CLAUDE.md`, rule 2).

- **No chess rules, scoring or rating math here.** Positions (FEN), SAN, legal moves, clocks and results all come from the API and events. There is deliberately no chess.js. When a board becomes interactive, legal destinations come from the server.
- **`src/api/generated/` is generated** from `contracts/openapi.json` by `npm run gen`. Never edit it. Call the API through `src/api/client.ts` (`api.GET/POST/...` plus `unwrap`), which turns problem responses into `ApiError`.
- Every write is sent as JSON (the backend refuses anything else); `client.ts` already does this.
- Live and replayed matches are the same thing: subscribe to the event stream (`src/api/events.ts`), fold events with `applyEvent`, pace them with `createPlayer` (`src/match/playback.ts`). The server never waits; pacing is a client concern.
- Clients must ignore unknown event types and fields.
- **Routes** (react-router, hash mode, in `src/App.tsx`): the player's journey (`/` title, `/hatch`, `/pond`, `/pond/practice/:gameId?`, `/pond/:tile` placeholders, `/arena` hub, `/arena/super-bullet/:matchId?`, `/arena/super-bullet/you/:seriesId`, `/arena/custom/:matchId?`) and the Lab (`/lab/ducks|match|engines`), the developer screens. Old `#/ducks`, `#/match/:id`, `#/engines` links redirect into the Lab. The map is `docs/design/03-player-journey.md`.
- **One art slot per thing.** Every duck is drawn by `components/DuckSprite.tsx` (skin + pose) and the egg by `components/Egg.tsx`; screens never draw art. Skin ids come from `assets/manifest.json` (`ducks/skins.ts`). Swapping in real art means changing those files only. Animations live in those components' CSS and must stop under `prefers-reduced-motion`.
- **Playable boards:** `Board` with `legalMoves` and `onMove`. Destinations come from the server's legal moves (`components/boardMoves.ts`); Chessground binds input only at creation, so a playable board is created interactive. Live games against a duck: `play/useSparringGame.ts` and `play/SparringGameView.tsx`.
- **The active duck is saved on the server** (`GET /profile`, `PUT /profile/active-duck`), never in local storage; `ducks/usePond.ts` loads it and refetches when the duck's event stream reports a change.
- Styling is functional only. Visual design, animation and copy belong to John; do not polish unless asked.
- Tests: vitest + Testing Library (`npm test -w apps/web`). Stub the API with `src/test/api.ts` (`stubApi`, `aDuck`, `SilentEventSource`) as in `src/pages/journey.test.tsx`; test pure logic directly as in `src/match/playback.test.ts`.
- Format with prettier (`.prettierrc.json`), lint with oxlint; both run in `npm run check`.
