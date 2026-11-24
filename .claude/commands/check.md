---
description: Run every gate CI runs, fix what fails, and report
---

Run `npm run check` from the repo root (it runs, in order: ruff check, ruff format check, mypy, pytest, contract drift check, oxlint, prettier check, vitest, vite build).

If a step fails:
1. Read the failure and fix the cause, not the symptom. Never weaken a test, add a blanket `noqa`/`type: ignore`, or skip a check to get green.
2. Formatting failures: `npm run format`.
3. Contract drift: if you changed an API or event schema on purpose, run `npm run gen` and include `contracts/` and `apps/web/src/api/generated/` in the commit; otherwise find out what changed the schema.
4. Golden-file failures: only if the change is intended, run `uv run --project backend pytest backend/tests/api --update-golden`, review the diff, and explain it in the commit. If a duck could now play a different move for the same inputs, bump `DECISION_LAYER_VERSION`.
5. Re-run `npm run check` until it passes.

If Stockfish is installed in `./data`, also run `uv run --project backend pytest backend/tests/real`.

Report: which steps failed, what you changed, and the final result. $ARGUMENTS
