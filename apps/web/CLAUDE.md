# Web client rules

React 19 + Vite + TypeScript. This is a thin client (root `CLAUDE.md`, rule 2).

- **No chess rules, scoring or rating math here.** Positions (FEN), SAN, legal moves, clocks and results all come from the API and events. There is deliberately no chess.js. When a board becomes interactive, legal destinations come from the server.
- **`src/api/generated/` is generated** from `contracts/openapi.json` by `npm run gen`. Never edit it. Call the API through `src/api/client.ts` (`api.GET/POST/...` plus `unwrap`), which turns problem responses into `ApiError`.
- Every write is sent as JSON (the backend refuses anything else); `client.ts` already does this.
- Live and replayed matches are the same thing: subscribe to the event stream (`src/api/events.ts`), fold events with `applyEvent`, pace them with `createPlayer` (`src/match/playback.ts`). The server never waits; pacing is a client concern.
- Clients must ignore unknown event types and fields.
- Styling is functional only. Visual design, animation and copy belong to John; do not polish unless asked.
- Tests: vitest + Testing Library (`npm test -w apps/web`). Stub `fetch` as in `src/App.test.tsx`; test pure logic directly as in `src/match/playback.test.ts`.
- Format with prettier (`.prettierrc.json`), lint with oxlint; both run in `npm run check`.
