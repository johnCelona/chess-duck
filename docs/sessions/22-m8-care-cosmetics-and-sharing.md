# Session 22 · Care tuning, cosmetics and sharing ⚑

Milestone: **M8** · Depends on: 05, 13

## Goal

Tune the care loop from play data, add cosmetics unlocked by play, a daily puzzle, and shareable duck links or files.

## Needs John ⚑

Everything: feel, rewards, art, copy.

## Read first

- `docs/duck-gambit-spec.md` §4.3, §4.5
- `docs/design/01-training-minigames-and-bullet-battle.md` §5, package D17

## Areas touched

- balance table (care)
- assets manifest (cosmetics)
- daily puzzle selection (seeded by date as data)

## Acceptance criteria

- Cosmetics never affect play; care never removes knowledge; no dark patterns.

## Test plan

- Domain tests for unlocks and care rules.

## Risks

- Scope creep: keep each addition small and optional.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 22: Care tuning, cosmetics and sharing.

Goal: Tune the care loop from play data, add cosmetics unlocked by play, a daily puzzle, and shareable duck links or files.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/22-m8-care-cosmetics-and-sharing.md` in full, then the files it lists under "Read first". Confirm the dependencies (05, 13) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
