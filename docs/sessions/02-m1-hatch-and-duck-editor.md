# Session 02 · Hatching flow and stat editor ⚑

Milestone: **M1** · Depends on: 01

## Goal

A real hatching flow (name, species and skin from `assets/manifest.json`, starting stat spread within the level-1 budget) and a stat editor that respects budget and stage caps, with the server as the only judge of validity.

## Needs John ⚑

Art direction for the hatch screen, species list, whether stats are placed freely or by training (Q2), respec rules (Q4).

## Read first

- `docs/duck-gambit-spec.md` §4
- `docs/design/01-training-minigames-and-bullet-battle.md` §2.1 and §9 (Q2, Q4)
- `backend/src/duckgambit/domain/duck.py`
- `docs/adr/0013-licensing-and-assets.md`

## Areas touched

- new `PUT /api/v1/ducks/{id}/stats` (validated by `validate_stats`)
- apps/web hatch and editor screens
- assets/manifest.json (placeholder entries)

## Acceptance criteria

- Hatching lets the player name the duck, pick an avatar from the manifest, and spend the starting budget; the server rejects anything over budget or cap with a clear message.
- The editor shows remaining budget and caps from the API (`growth.statBudget`, `growth.statCap`), never computed in the client.
- Respec rules follow John's answer to Q2/Q4 (default: free until first stage change).
- `DuckHatched` and a new `StatsChanged` (or the design's `StatTrained`) event are emitted.

## Test plan

- Domain tests for respec rules; API tests for budget errors; web test for the hatch flow.

## Risks

- Placing stats by minigame (design Q2) may replace free editing later; keep the endpoint usable for respec.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 02: Hatching flow and stat editor.

Goal: A real hatching flow (name, species and skin from `assets/manifest.json`, starting stat spread within the level-1 budget) and a stat editor that respects budget and stage caps, with the server as the only judge of validity.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/02-m1-hatch-and-duck-editor.md` in full, then the files it lists under "Read first". Confirm the dependencies (01) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
