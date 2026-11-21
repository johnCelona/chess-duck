# Session 10 · Game modes, League and the ratings UI ⚑

Milestone: **M3** · Depends on: 08

## Goal

Add `mode` and `rated` to games (design delta A2): training games between your own ducks pay XP but do not move ratings; League games against named anchor rivals do. Show ratings with their context and a leaderboard.

## Needs John ⚑

Q1 (do own-duck games move ratings?), League names and rival art.

## Read first

- `docs/design/01-training-minigames-and-bullet-battle.md` §4.2, §9 Q1, packages D7
- `docs/adr/0006-strength-time-and-progression.md`

## Areas touched

- migration: games.mode, games.rated
- services/matches.py (rate only when rated)
- anchor rivals with names and avatars
- web leaderboard

## Acceptance criteria

- Own-duck training matches never change ratings; League matches do.
- Every rating shown names its context; ratings from different contexts are never mixed.

## Test plan

- Service tests for rated vs unrated; contract tests for new fields.

## Risks

- Spec 7.2 says results update ratings; design Q1 recommends otherwise; John decides.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 10: Game modes, League and the ratings UI.

Goal: Add `mode` and `rated` to games (design delta A2): training games between your own ducks pay XP but do not move ratings; League games against named anchor rivals do. Show ratings with their context and a leaderboard.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/10-m3-league-and-game-modes.md` in full, then the files it lists under "Read first". Confirm the dependencies (08) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
