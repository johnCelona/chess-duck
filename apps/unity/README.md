# Unity client (placeholder)

Nothing is built here yet. The plan and the reasons are in `docs/adr/0003-unity-strategy.md`:

- Desktop only at first. The game launches the Python backend as a local sidecar and talks to the same `/api/v1` as the web app.
- The Unity project is a presentation client: it renders events and calls the API. It contains no chess rules, scoring or rating logic.
- **No GPL code in this folder.** Do not port or copy code from Chessground, python-chess or Stockfish. The backend is a separate program.
- The C# models are generated from `contracts/openapi.json` and `contracts/events.schema.json`. Generated code is never edited by hand.

The first Unity session is `docs/sessions/` milestone M7. The readiness checklist in ADR-0003 lists what the backend already guarantees.
