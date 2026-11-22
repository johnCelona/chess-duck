# Session briefs

One focused coding session each. Every brief has a goal, dependencies, files to read, areas touched, acceptance criteria, a test plan, risks, and a ready-to-paste prompt. ⚑ marks sessions that need John's product or design input (feel, balance, art, copy); ask him in one batched message at the start.

Milestones follow spec §10. Bullet sparring is pulled into M3 (design 01 §8) because it needs nothing from review.

| # | Milestone | Session | Depends on | Needs John |
| --- | --- | --- | --- | --- |
| [00](00-m0-foundation.md) | M0 | M0 Foundation (done) | none |  |
| [01](01-m1-router-and-duck-pages.md) | M1 | Router, app shell and duck detail page (router done; duck page left) | 00 |  |
| [02](02-m1-hatch-and-duck-editor.md) | M1 | Hatching flow and stat editor (hatching done; editor left) | 01 | ⚑ Art direction for the hatch screen, species list, whether stats are placed freely or by training (Q2), respec rules (Q4). |
| [03](03-m1-live-spectator.md) | M1 | Live spectator view | 01 | ⚑ Layout, look and motion of the spectator view; the emote list (design §6.2). |
| [04](04-m1-duck-files.md) | M1 | Duck file import, export and sharing | 01 |  |
| [05](05-m2-training-door-and-care.md) | M2 | The training door: lessons, XP and stats (game XP done; lessons and stat placement left) | 02 | ⚑ XP per activity; stat placement (design 04 §5). No energy. |
| [06](06-m2-opening-lessons.md) | M2 | Opening School: trained openings, shortlist and Opening Drill (v1 in design 04 §1) | 05 | ⚑ Lesson UX and copy; how many moves a drill teaches at once. |
| [07](07-m2-principles-and-why-panel.md) | M2 | Principles as style rules (v1 in design 04 §2) | 05 | ⚑ Which principles ship first, their names and card copy. |
| [08](08-m3-calibration-harness.md) | M3 | Calibration harness and real ratings | 00 | ⚑ Target rating bands for levels and stages (balance numbers). |
| [09](09-m3-tournaments.md) | M3 | Tournaments: round robin, Swiss, knockout | 08 |  |
| [10](10-m3-league-and-game-modes.md) | M3 | Game modes, League and the ratings UI (series and challengers done; v1 in design 04 §6) | 08 | ⚑ League ladder rules, rival names and art. |
| [11](11-m3-bullet-sparring.md) | M3 | Bullet sparring: the player against their duck (done as Practice Pond and "You play"; handicaps left) | 03, ADR-0015 accepted | ⚑ Sparring defaults (Q6): time odds, relaxed clock, starting handicap; the outgrown celebration (Q11). |
| [12](12-m4-puzzle-packs.md) | M4 | Puzzle packs and the answer-key builder | 00 | ⚑ Puzzle difficulty bands and pack themes. |
| [13](13-m4-candidate-showdown.md) | M4 | Puzzle Arena: Candidate Showdown | 12 | ⚑ Scoring presentation and copy. |
| [14](14-m4-defender-modes-and-tactics.md) | M4 | Defender modes, motif detectors and Tactics Drill | 13 |  |
| [15](15-m5-judge-review.md) | M5 | Judge review and critical moments (v1 in design 04 §3; suggested next) | 08 | ⚑ Review thresholds (inaccuracy, mistake, blunder) and how many moments to show. |
| [16](16-m5-blunder-training.md) | M5 | Blunder Training | 15, 05 | ⚑ Card size and tone (Q8), what happens when the duck's blunder was a taught move (Q9), emotes and copy. |
| [17](17-m5-xp-curve-and-stages.md) | M5 | XP curve, stages and level-up | 08, 16 | ⚑ The XP curve and stage feel; stage names. |
| [18](18-m6-lichess-link.md) | M6 | Lichess link (OAuth with PKCE) | 00 | ⚑ Privacy: what we store about linked accounts and imported games (spec §12, item 8). |
| [19](19-m6-import-games-and-mini-me.md) | M6 | Learn from my games, and save duck games to Lichess | 18, 06, 16 |  |
| [20](20-m7-unity-contract-and-sidecar.md) | M7 | Unity readiness: C# models and the backend sidecar | 00 |  |
| [21](21-m7-unity-vertical-slice.md) | M7 | Unity vertical slice | 20 | ⚑ Everything visual: art, animation, Unity UI, store presence. |
| [22](22-m8-care-cosmetics-and-sharing.md) | M8 | Care tuning, cosmetics and sharing | 05, 13 | ⚑ Everything: feel, rewards, art, copy. |
| [23](23-m8-hosted-mode-study.md) | M8 | Hosted mode: feasibility study (optional) | most of M1–M6 | ⚑ Whether to host at all, and the budget. |

## Suggested order

M1 (01 → 02, 03, 04) → M2 (05 → 06, 07) → M3 (08 → 09, 10; 11 after ADR-0015 is accepted) → M4 (12 → 13 → 14) → M5 (15 → 16 → 17) → M6 (18 → 19) → M7 (20 → 21) → M8.

Sessions without a dependency between them can run in parallel branches. Built so far (2026-11-21): the journey slice, Super Bullet Arena, Practice Pond, game XP. Suggested next, per design 04 §7: Review Room v1 (15), then Opening School (06).

## Recurring commands

`.claude/commands/` has `/check` (run every gate and fix failures), `/session NN` (start a brief) and `/contract-change` (change an API or event schema safely).
