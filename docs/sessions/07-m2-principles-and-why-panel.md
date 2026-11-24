# Session 07 · Principles as style rules ⚑

Milestone: **M2** · Depends on: 05

## Goal

Add the first principles (develop minors, castle early, fight for the centre, don't move the queen early) as style rules in the registry, let players adopt them by flipping a card ("Rules of the Pond", no quiz; design 03 §5), and show them in the "why" panel.

## Needs John ⚑

Which principles ship first, their names and card copy; how many a duck holds active at once (placeholder 3).

## Read first

- `docs/duck-gambit-spec.md` §5.2
- `docs/adr/0005-decision-layer.md`
- `backend/src/duckgambit/domain/rules.py`

## Areas touched

- domain/rules.py (principle rules, weights from knowledge)
- lesson kind `principle`
- DECISION_LAYER_VERSION bump

## Acceptance criteria

- Each principle is a pure rule on (board, move) with a label and reason code; a duck applies only principles it has learned.
- The thinking panel shows principle bonuses like style bonuses.
- Flipping a principle card (design package D4) adds it through the training door; a duck holds a limited number active, and swapping is free.

## Test plan

- Unit tests per rule on hand-picked positions; golden files updated with an explanation.

## Risks

- Rules can make a duck weaker; measure with the harness once M3 exists.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 07: Principles as style rules.

Goal: Add the first principles (develop minors, castle early, fight for the centre, don't move the queen early) as style rules in the registry, let players adopt them by flipping a card ("Rules of the Pond", no quiz; design 03 §5), and show them in the "why" panel.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/07-m2-principles-and-why-panel.md` in full, then the files it lists under "Read first". Confirm the dependencies (05) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
