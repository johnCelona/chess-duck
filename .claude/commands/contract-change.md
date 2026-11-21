---
description: Change an API or event schema safely (ADR-0002)
argument-hint: <what should change>
---

Make this contract change: $ARGUMENTS

Rules (ADR-0002, `contracts/CLAUDE.md`):
- Prefer additive changes: new optional fields, new endpoints, new event types. Clients ignore unknown fields and events, so additive changes stay in `/api/v1`. A breaking change needs `/api/v2` or a new event name; stop and ask John first.
- Wire schemas live in `backend/src/duckgambit/api/schemas/` (camelCase on the wire; request bodies use `WireIn`). A new event needs both a dataclass in `domain/events.py` and a wire envelope in `api/schemas/events.py` (added to the `EventEnvelope` union). `tests/api/test_contracts.py` checks they match.
- No raw UCI, wall-clock limits, filesystem paths or tokens in any schema.

Steps:
1. Change the domain/service code and the wire schema together; add or update API tests.
2. Run `npm run gen`. Review the diff of `contracts/openapi.json`, `contracts/events.schema.json` and `apps/web/src/api/generated/schema.d.ts`; it should contain only what you meant to change.
3. Update the web client to use the new types if needed (never edit the generated file).
4. If event data changed, golden files will change: update them with `--update-golden` and explain the change in the commit.
5. Run `/check`. Commit the contract files with the code that produced them.
