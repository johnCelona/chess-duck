# Session 03 · Live spectator view ⚑

Milestone: **M1** · Depends on: 01

## Goal

Make watching a match good: eval bar from the mover-independent WDL, step forward and back, jump to any move, opening name, emote hooks, and the thinking panel showing why each move was played.

## Needs John ⚑

Layout, look and motion of the spectator view; the emote list (design §6.2).

## Read first

- `docs/duck-gambit-spec.md` §7.3
- `docs/design/01-training-minigames-and-bullet-battle.md` §6.2
- `apps/web/src/match/playback.ts`

## Areas touched

- apps/web/src/pages/MatchPage.tsx and new components
- an emote table data file (design package D16)
- possibly `MoveMade` gains an eval for the bar (additive)

## Acceptance criteria

- Eval bar, step controls (previous, next, start, end), clickable move list, and replay of any past match by link.
- The thinking panel shows candidates, style adjustments, filtered moves and reasons for the selected ply, not only the latest.
- An emote table maps event types to emote names as data; the duck avatar component receives an emote name (art comes later).

## Test plan

- Playback reducer tests for stepping and seeking; web tests for the panel with recorded events (reuse the walking-skeleton golden events).

## Risks

- Opening names need a dataset (lichess-org/chess-openings is CC0); compute names server-side, not in the client.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 03: Live spectator view.

Goal: Make watching a match good: eval bar from the mover-independent WDL, step forward and back, jump to any move, opening name, emote hooks, and the thinking panel showing why each move was played.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/03-m1-live-spectator.md` in full, then the files it lists under "Read first". Confirm the dependencies (01) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
