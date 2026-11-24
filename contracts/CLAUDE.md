# Contracts

`openapi.json` (OpenAPI 3.1) and `events.schema.json` are **generated** from the backend's pydantic wire schemas (`backend/src/duckgambit/api/schemas/`). They are the source of truth every client is generated from (ADR-0002). Never edit them by hand.

- Regenerate: `npm run gen` (also regenerates `apps/web/src/api/generated/schema.d.ts`).
- CI and `npm run check` fail when either file, or the generated TypeScript, is out of date.
- A contract change is a visible diff: review it like code. Additive changes stay in v1; a breaking change needs `/api/v2` or a new event type.
- `package.json` here pins the TypeScript generator (openapi-typescript) separately from the web app's TypeScript version.
- A C# client for Unity will be generated from the same files in M7 (ADR-0003).
