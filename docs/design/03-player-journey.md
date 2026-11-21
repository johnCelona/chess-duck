# Design 03 · The player journey

*2026-11-21 · From John's end-to-end vision and his answers to the open questions · Status: Proposed. Decisions in §7 are John's and settled; everything else is a proposal. Place names (Pond, Dojo, School…) are placeholders.*

This document is the map. The details of each activity live elsewhere and are linked, not copied:
- Design 01: training minigames, Blunder Training and Bullet Battle.
- Design 02: position memory at scale.
- The ADRs in `docs/adr/`.

---

## 0. Summary

You hatch an egg, name your duck, and raise it. You teach it the chess you know, train it in minigames, and send it to battle other ducks. Every duck runs on the same engine, so wins come from what you taught it and how you tuned it, not from a faster computer. On the surface it is a casual pet game. Underneath it is real chess improvement: as the duck gets better, so does the player.

You will usually raise **several ducks** and have them battle each other. Hatching never replaces a duck.

**Rules every feature follows:**

1. **Anything that changes how a duck plays is saved data or comes from a seed.** Never live randomness, never a clock. Real time is only for the player's own clock (ADR-0015).
2. **The replay test.** For every minigame, ask: what does it change in the duck's data, and could a player see that change in a replay?
3. **No pay-to-win.** Nothing buys strength.
4. **Nothing slows the player down.** No energy, no timers, no waiting to play (John, 2026-11-21). Anything added later must obey this too.
5. **Nothing is ever lost.** Knowledge never decays and failing never takes anything away (design 01 §3.5).

---

## 1. The opening flow

| Step | The player sees | Written | Where it lives |
| --- | --- | --- | --- |
| Title | "Duck Gambit" logo (animation slot), **Play**, **Hatch a new egg**, gear icon for the Lab | Nothing | `/` |
| Story | 3 to 5 skippable panels. **Later**; an empty slot exists | Nothing | `/hatch` (slot) |
| The egg | An egg. Tap or click it: it wobbles and cracks over three taps | The **egg seed** is made on the first tap and kept for this hatch | `/hatch` |
| Hatch | The shell splits and the duck pops out. A short celebration | Nothing yet | `/hatch` |
| Name | Name the duck and optionally pick a skin | `POST /ducks { name, eggSeed, avatar.skin }`, then the duck becomes active | `/hatch` |
| The Pond | The hub, with the new duck active | | `/pond` |

**Play:**
- Goes to the Pond with the active duck.
- On first launch, with no ducks, it goes straight to the egg.

**Hatch a new egg:**
- Runs the same flow from the title or from the duck switcher.
- There is no duck cap. A soft "pond size" for the interface may come later.

**The egg seed:**
- It is stored on the duck (`eggSeed`).
- It decides the duck's starting stats: a small tilt off the even spread, so every duck starts a little different. The tilt sizes are placeholders in the balance table.
- All later stat points come from training (design 01 §2.1).
- The seed never feeds move choice directly. Stats do, as for every duck.
- The same egg seed always hatches the same stats.
- Ducks hatched in the Lab without an egg seed keep the even spread.

**Later: the Shell Puzzle.** You crack the shell by solving a mate-in-one. It becomes the tutorial's first puzzle. v1 is tap to crack.

---

## 2. The Pond (the hub)

### 2.1 Top bar: the duck's attributes

All of it comes from `GET /api/v1/ducks/{id}` (`DuckOut`). Nothing is computed in the client.

| Shown | Field | Note |
| --- | --- | --- |
| Name, sprite | `name`, `avatar.skin` | The sprite is drawn by one component (§6) |
| Level and stage | `growth.level`, `growth.stage` | Stages: hatchling, duckling, duck, champion (placeholders) |
| XP bar | `growth.xp`, `growth.xpForNextLevel` | `xpForNextLevel` is derived from the balance table. It is null at the maximum level |
| Rating | `rating.value`, `rating.provisional`, `rating.games` | Shown as provisional until calibrated |
| Stats | `stats.{calculation, memory, aggression, solidity, creativity, speed}` | The six existing stats; no new ones |
| Stat budget | `growth.statBudget`, sum of `stats` | Points earned but not yet placed (design 01 §2.1) |

`care` exists in the data model but is not shown: energy is out of scope (§7, Q3).

**The payoff:**
- The top bar refetches whenever the duck's event stream (`duck:{id}`) reports a change, so a minigame result visibly moves it.
- Today only rated games change anything (the rating). XP starts moving when the training door ships (design 01 D1, session 05).

### 2.2 Duck switcher

- A dropdown on the duck's name. It lists every duck (name and level) and ends with **+ Hatch a new egg**.
- Picking a duck makes it active. The choice is saved on the profile (`profiles.active_duck_id`, `PUT /api/v1/profile/active-duck`), so a future Unity client shares it.
- Each duck keeps its own egg seed, stats and knowledge.

### 2.3 The four tiles

| Tile | The player does | Changes in the duck's data | Visible in a replay as | Detail |
| --- | --- | --- | --- | --- |
| **Tactics Dojo** | Motif drills (fork, pin, back-rank mate…). Later, Candidate Showdown: several ducks get the same position and you compare each duck's top 5 on the eval bar. Later, a door to Blunder Training | Motif weights, puzzle memory, puzzle rating (M4) | Different candidates and reasons in the "why" panel; a remembered fix (`source: memory`) | Design 01 §2.4; ADR-0009; sessions 12 to 14 |
| **Arena** | Pick **any two of your ducks**, or later one of yours against a rival duck, and battle at 1-minute bullet on the virtual clock. Watch live or skip to the end with the match viewer and "why" panel | Game rating (rated, §7 Q7); XP and level once D1 ships | The rating and the game itself | Design 01 §4.2; ADR-0007; sessions 03, 09, 10 |
| **Practice Pond** | Play your own duck on your own real clock | XP; review material. Never rated | The duck's replies replay exactly from your recorded moves | Design 01 §4.1; ADR-0015; session 11 |
| **Opening School** | Teach the duck a specific opening, move by move. Finishing adds that opening to the duck. Star the ones you want it to favour | A new or strengthened `Opening` and its repertoire entries (§4) | The duck's pre-game shortlist and its book moves, each naming the opening | §4; ADR-0016; design 01 §2.3; session 06 |

In the first build slice only the Arena works. It opens the existing match flow. The other three tiles open placeholder screens.

---

## 3. The Review Room (after any game)

- After an Arena or Practice Pond game, the Review Room opens.
  - The Judge flags the critical moments (ADR-0008).
  - You try a better move, the duck learns the fix, and then you watch it play the fix.
- **Proof uses replay from the fix** (design 01 §4.2): the stored game resumes at the critical ply with today's duck. It does not replay the whole game with the old seed, because a level-up since then can change an earlier move and the game would never reach the same position.
- **Blunder Training** (design 01 §3) is the queue of blunder cards that reviews produce.
  - It is **one screen with two doors**: the Review Room (first) and the Tactics Dojo (added when the Dojo is built).
  - Both names stay: the Review Room is the post-game screen; Blunder Training is the drill.

---

## 4. Openings and personality

Full design: ADR-0016. In short:

- **A duck plays only openings it was trained on.** Finishing Opening School for an opening adds it. Training it again strengthens it.
- **Before every game the duck shortlists up to 3 openings**, from:
  - its preferences: your star, how often it was trained, how well it scores with it;
  - the opponent: how this opening has done against that duck, and whether that duck is prepared for it.
- The shortlist is drawn with the game seed from data snapshotted when the match is created, so a replay picks the same openings. The "why" panel shows "Planned: …".
- **It still reacts.** When the opponent leaves the line, it plays from the engine, shaped by its style and principles.
- **White and Black:**
  - A White opening starts from move 1.
  - A Black opening is a defence to a particular first move ("Sicilian vs 1.e4"). The shortlist takes at most one defence per first move, so it covers more of what White might play.
- **No trained openings:** the duck plays from the engine from move 1. That is the reason to visit Opening School.

---

## 5. Rules of the Pond (principle cards)

**The case for it.**
- Trained lines only fire in positions the duck was shown. Principles are style rules (`domain/rules.py`, kind `principle`) that re-rank the engine's near-equal candidates in *every* position.
- So when the opponent leaves the book, a "castle early, fight for the center" duck still plays like itself rather than like plain Stockfish. Principles are the main source of personality outside the opening shortlist.
- For the player, each card is one idea that transfers between openings (why you develop, why the king castles). It explains the lines they teach, and they can watch the duck apply it in the "why" panel.

**The simplest version:**
- Flipping a card adds the principle to `knowledge.principles`. There is no quiz.
- A duck holds a few active principles at once [placeholder: 3], so choosing them is a style decision, not a collection to complete.
- Rules can only reorder moves that survived the blunder filter, so they cannot make a duck stronger than its level allows (ADR-0005).
- Built with session 07; not in the first slice.

---

## 6. Art and feel

- Arcadey, nerdy, warm, nice art, not super retro.
- **One art slot for the duck:** the `DuckSprite` component (web) draws every duck on every screen, from `avatar.skin` and a pose (`idle`, `emerge`, `celebrate`). Screens never draw duck art themselves. The egg is its own component.
- **Swapping art:** replacing the placeholder with John's artist's duck means changing that component and `assets/manifest.json`, nothing else.
- **Skins** are a small fixed list of minimal, nerdy placeholders (`classic`, `graph-paper`, `blueprint`, `terminal`, `chalkboard`). Real skins come later from artists, especially for Unity.
- **AI art** may be acceptable later for backgrounds and themes, never for the duck.
- **Animations** in the first slice are simple placeholders (the egg wobbles and cracks, the duck pops out). They switch off for players who ask their system for reduced motion.

---

## 7. Decisions (John, 2026-11-21)

| # | Question | Decision |
| --- | --- | --- |
| Q-A | Can the top bar show XP progress? | Yes: add `growth.xpForNextLevel`, derived from the balance table |
| Q1 | Hatching interaction | Tap or click, with a cracking and emerging animation. The Shell Puzzle comes later as the tutorial's first puzzle |
| Q2 | Starting stats | The egg seed gives a small tilt off the even spread; other stat points come from training |
| Q3 | Energy | **None for now.** Out of scope. Nothing may slow the player down, including anything added later |
| Q4 | Duck cap | No hard cap in v1. A soft "pond size" for the UI later is fine |
| Q5 | Platform | Per ADR-0003: web is the dev and Lab client and also playable; Unity desktop is the shipped game later |
| Q6 | New Game vs Continue | No "New Game". Title has **Play** and **Hatch a new egg**; hatching never deletes or replaces a duck; the Arena can pit any two of your ducks |
| Q7 | Do games between your own ducks move ratings? | **Yes**, with the normal formula (the lower-rated duck gains more when it wins). Farming risks are flagged in §8, not blocked |
| Q8 | Rules of the Pond | Kept in the simplest form (§5), not in the first slice |
| Q9 | Opening School | Trained openings and a pre-game shortlist (§4, ADR-0016) instead of Always / Often / Sometimes per move |
| Q10 | Where Blunder Training lives | One screen, two doors. The Review Room first, the Dojo later |
| Q11 | Colors | A small fixed list of placeholder skins, easy to swap |

**Still open:**

1. **Opening names:** our own list, or a public catalogue with names and ECO codes? It needs a license check.
2. **Rival ducks for the Arena:** the roster, names and art (design 01 B6). John mentioned "sparring ducks".
3. **Skin names and look.**
4. **Preference numbers** in ADR-0016 (placeholders until session 06).

---

## 8. Conflicts with what was built or decided

| # | Item | Was | Now |
| --- | --- | --- | --- |
| C1 | Ratings between own ducks | Design 01 Q1 recommended unrated | **Rated** (Q7); design 01 updated |
| C2 | "Replay from that position with the same seed" | Whole-game replay can diverge after a level-up | Replay from the fix (§3) |
| C3 | Starting stats | Session 02 let the player spend the starting budget | The egg tilt sets the start; training places later points; the Lab editor stays for respec |
| C4 | "Each duck keeps its own seed" | Ducks had no seed | `eggSeed` added; it shapes the hatch only |
| C5 | Principles | Design 01 §2.3 unlocked them with a quiz | A flip card, no quiz (§5) |
| C6 | Puzzle rating on the top bar | Only the headline game rating is on the wire | Added with puzzles (M4) |
| C7 | Platform | ADR-0003 | Unchanged |
| C8 | Arena "changes XP and level" | Nothing grants XP yet | Comes with the training door (design 01 D1, session 05) |
| C9 | Energy and care | Design 01 §5 proposed session energy and feeding | Out of scope (Q3). `care` stays in the data model, unused and hidden |
| C10 | Opening School weights | Per-move weights on a flat repertoire | Trained openings and a shortlist (ADR-0016) |

**Rating-farming risks** (Q7; flagged, not blocking):

1. **Hatch and beat.** Every new duck starts at the same provisional rating, so a strong duck could gain by beating fresh hatchlings.
   - Glicko-2 already counts a high-uncertainty opponent for less.
   - Fix when it matters: start new ducks from the calibration curve (level and stats, session 08), or skip rating updates against provisional ducks in your own pond.
2. **Repeat a known win.** Same ducks, same knowledge and same seed replay the same win.
   - Fix: rated matches get server-made seeds, and a given (duck versions, seed) pair is rated once.
3. **Closed pool.** Ratings earned only inside your own pond mean "relative to your pond".
   - Fix: show the pool size beside the number. A rating comparable across players needs League games against anchor ducks (design 01 §4.2).

---

## 9. The first build slice

Title → egg → hatch → name → Pond, with the top bar, duck switcher and four tiles.
- **Arena** opens the existing match flow with the active duck preselected.
- **The other tiles** open placeholder screens.
- **The Lab** (Ducks, Match, Engines) stays reachable from the title and from a gear in the Pond.

New in the API:
- `eggSeed` on hatch;
- `growth.xpForNextLevel`;
- the profile's active duck.

The same-seed-same-game guarantee is unchanged and tested: two ducks hatched from the same egg seed have the same stats and play identical games with the same match seed.
