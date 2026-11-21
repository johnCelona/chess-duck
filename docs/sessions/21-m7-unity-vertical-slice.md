# Session 21 · Unity vertical slice ⚑

Milestone: **M7** · Depends on: 20

## Goal

Hatching and match playback in Unity with John's art: the duck reacts to events through the emote table.

## Needs John ⚑

Everything visual: art, animation, Unity UI, store presence.

## Read first

- `docs/adr/0003-unity-strategy.md`
- `docs/design/01-training-minigames-and-bullet-battle.md` §6.2
- `assets/README.md`

## Areas touched

- apps/unity/

## Acceptance criteria

- A desktop build launches the sidecar, hatches a duck, plays and watches a bullet match, and exits cleanly with no orphaned processes.

## Test plan

- Manual test plan plus the C# contract tests.

## Risks

- Signing and antivirus false positives for the frozen backend.

## Prompt (paste into a new session)

```text
You are working on Duck Gambit (repo root: this folder). Session 21: Unity vertical slice.

Goal: Hatching and match playback in Unity with John's art: the duck reacts to events through the emote table.

Rules for this session:
- Read `CLAUDE.md` (and the folder `CLAUDE.md` files you touch), this brief, and the documents listed under Read first.
- Plan before coding if you touch more than three files or any contract. Ask John only about the items marked ⚑, batched into one message.
- Keep the layering: pure domain, services with ports, adapters, thin API, thin client. Anything that affects a result is seeded and node-limited.
- A contract change means `npm run gen` and committing `contracts/` plus the generated TypeScript. A new event needs a domain dataclass and a wire schema.
- Small commits with imperative messages. Never push without asking.
- Done means: `npm run check` passes, the acceptance criteria below are met, and the change was tried in the running app (`npm run dev`).

Start by reading `docs/sessions/21-m7-unity-vertical-slice.md` in full, then the files it lists under "Read first". Confirm the dependencies (20) are done; if not, stop and say so. Then plan, build, test, and finish with a short report: what changed, how to try it, anything that needs John.
```
