# ADR-0002 · Client-agnostic contract and event vocabulary

Status: Proposed · 2026-11-21

## Context

Today the API is unversioned, returns bare dicts (so OpenAPI carries no response schemas) and the web client hand-copies types that have already drifted. A Unity client must be able to consume exactly what the web client consumes, and neither may contain chess rules, scoring or rating math (CLAUDE.md rule 2).

## Options

**Authoring.** (a) Hand-written OpenAPI YAML with code generated on both sides; (b) pydantic models as the authoring format, with the exported document committed and treated as the contract. (a) is purer but doubles the work for a two-person project; (b) gives the same reviewable artifact.

**Streams.** (a) WebSocket; (b) Server-Sent Events; (c) polling only. Streams here are one-way (server to client); commands are ordinary requests. SSE has built-in reconnect with `Last-Event-ID`, which maps directly onto a persisted event log. Browser `EventSource` cannot send custom headers and HTTP/1.1 allows six connections per origin [1][2].

**TypeScript generator.** openapi-typescript + openapi-fetch (types only, no generated runtime, MIT, OpenAPI 3.1) [3]; @hey-api/openapi-ts (self-described as initial development) [4]; orval (heavier, more features than we need) [5].

## Decision

1. **REST under `/api/v1`**, JSON, **camelCase on the wire** (the spec's examples already are), snake_case in Python via a pydantic alias generator. Resource-style paths; actions that start long work create a job or a match resource.
2. **Schemas are pydantic models in `duckgambit/api/schemas`**. `duckgambit export-contracts` writes `contracts/openapi.json` (OpenAPI 3.1) and `contracts/events.schema.json`. Both are committed. CI regenerates and fails on any diff, so a contract change is always a visible, reviewed diff.
3. **Generated clients are never edited.** TypeScript: openapi-typescript into `apps/web/src/api/generated/`, called through openapi-fetch. C#: generated from the same file when Unity starts (ADR-0003).
4. **Streams are SSE plus a pollable JSON twin of the same log.**
   - `GET /api/v1/events?stream=match:{id}&after={cursor}` returns a page of events (works in any client, including one with no streaming support).
   - `GET /api/v1/events/stream?stream=...&stream=...` is the same data as `text/event-stream`, several streams multiplexed on one connection (one connection per tab avoids the six-connection limit). The SSE `id:` is the global cursor, so reconnect resumes exactly.
   - Replay and live watching are the same endpoint read from different cursors.
5. **Event envelope.**

   ```json
   { "cursor": 4182, "stream": "match:mat_9f2c", "seq": 17, "type": "MoveMade", "recordedAt": "2026-11-21T18:02:11Z", "data": { } }
   ```

   `data` is produced by the domain and is fully deterministic for a given seed. `cursor` and `recordedAt` are added by the service; golden tests compare `stream`, `seq`, `type`, `data` only. `type` is the discriminator of a tagged union, one schema per event.
6. **Events carry everything a rule-free client needs.** `MoveMade` includes `uci`, `san`, `fenAfter`, capture/check/castle/promotion flags and both clocks. Any position where a human may move comes with `legalMoves` from the server. The web app therefore drops `chess.js`; chessground is fed `fen` and `dests` from the API.
7. **Reasons are data.** `MoveChosen` lists candidates with their engine score, each adjustment (`ruleId`, `kind`, `delta`), the final score, the sampling probability, and reason entries of the form `{ code, params, text }`. `text` is a default English sentence; clients may render from `code` instead. Copy belongs to John.
8. **Errors are RFC 9457 problem documents** with a stable machine code:

   ```json
   { "type": "about:blank", "title": "Engine is not installed", "status": 409, "code": "engine.not_installed", "detail": "...", "errors": [] }
   ```

   Internal exception text is never sent to a client.
9. **Versioning.** Additive changes (new optional fields, new event types) stay in v1; clients must ignore unknown fields and unknown event types. A breaking change means `/api/v2` or a new event type name. Stored documents carry `schemaVersion` (ADR-0004).
10. **Ids** are opaque prefixed strings (`duck_…`, `mat_…`, `game_…`, `job_…`) generated at the service edge by an injectable generator.

### Vocabulary (v1)

| Group | Events | In M0 |
| --- | --- | --- |
| Duck | `DuckHatched`, `DuckFed`, `DuckRested`, `StageAdvanced`, `DuckLeveledUp`, `KnowledgeAdded` | `DuckHatched` |
| Training | `LessonStarted`, `LessonCompleted`, `FixTaught`, `LessonChecked` | schema only (stubs) |
| Match | `MatchCreated`, `MatchStarted`, `GameStarted`, `MoveChosen`, `MoveMade`, `GameFinished`, `MatchFinished` | all |
| Tournament | `RoundStarted`, `StandingsUpdated` | schema only |
| Review | `ReviewReady`, `CriticalMomentFound` | schema only |
| Puzzles | `PuzzleStarted`, `CandidatesSubmitted`, `PuzzleScored` | schema only |
| Ratings | `RatingUpdated` | emitted with the calibration stub |
| Integrations | `LichessLinked`, `GameImported`, `GameExported` | schema only |
| Jobs | `JobProgressed`, `JobFinished` | yes |

`GameStarted`/`GameFinished` are added to the spec's list because a match contains several games (best-of-N, colour swaps).

## Consequences

- One source of truth, two generated clients, and a drift check that makes contract changes deliberate.
- No WebSocket means no bidirectional channel. Sparring (a human playing the duck) uses a request per move plus the stream; that is ample for chess.
- camelCase wire names are a one-time break of the existing `/api/engines` shapes, done together with the `/api/v1` move.
- `EventSource` cannot send an auth header. In sidecar mode with a launch token (ADR-0011) the web client reads the stream with `fetch`; Unity sets headers normally.

## Not building yet

- WebSocket transport, binary formats, GraphQL.
- The C# client (only the path to it).
- Server-side localisation of reason text.
- Event payloads beyond those marked "In M0"; the others get schemas with their stubs and real payloads in their sessions.

## Sources

1. MDN, EventSource: https://developer.mozilla.org/en-US/docs/Web/API/EventSource
2. WHATWG, Server-sent events: https://html.spec.whatwg.org/multipage/server-sent-events.html
3. openapi-typescript 7.13.0 / openapi-fetch 0.17.0: https://openapi-ts.dev/introduction
4. @hey-api/openapi-ts 0.99.0: https://heyapi.dev/openapi-ts/get-started
5. orval 8.48.0: https://github.com/orval-labs/orval
6. FastAPI server-sent events (native since 0.135): https://fastapi.tiangolo.com/tutorial/server-sent-events/
7. RFC 9457, Problem Details for HTTP APIs: https://www.rfc-editor.org/rfc/rfc9457
