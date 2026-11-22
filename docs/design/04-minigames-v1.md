# Design 04 · The remaining modes, rough v1

*2026-11-21 · Draft for John's design session · Status: Proposed. Everything here is a starting point to argue with, not a decision. [PH] marks a placeholder number for the balance table. Names and copy are John's.*

The journey map is `03-player-journey.md`; per-activity detail from the first design pass is in `01-training-minigames-and-bullet-battle.md`. This document gives each mode that is not built yet a concrete v1:
- the loop, step by step;
- what it changes in the duck;
- how a player would see that change in a replay;
- the smallest playable version, using what already exists;
- the questions to settle.

---

## 0. Where things stand

| Mode | State | Where |
| --- | --- | --- |
| Title → egg → hatch → Pond | Built | `apps/web/src/pages/{Title,Hatch,Pond}Page.tsx` |
| Arena: custom match | Built | `/arena/custom` |
| Arena: Super Bullet Arena, duck vs challenger | Built, rated, best of N + Armageddon | `/arena/super-bullet`, `domain/series.py`, `domain/challengers.py` |
| Arena: Super Bullet Arena, you play | Built, 30 s each, unrated | `/arena/super-bullet/you/:id`, `services/sparring.py` |
| Practice Pond | Built: untimed by default or any clock, the why panel after the game | `/pond/practice` |
| XP from games, level-ups | Built (match end; sparring game end) | `domain/duck.grant_xp` |
| **Review Room + Blunder Training** | v1 below; the domain parts mostly exist | §3 |
| **Opening School** | v1 below; teaching lines works in the domain today | §1 |
| **Rules of the Pond** | v1 below | §2 |
| **Tactics Dojo** | v1 below; needs puzzle content | §4 |
| Stat points placed by training | v1 below | §5 |
| League and rival ducks | v1 below | §6 |

**Building blocks the remaining modes can reuse:**
- **The playable board:** `Board` with server legal moves, and `useSparringGame`.
- **One duck decision path:** `services/duck_turn.decide_duck_move`.
- **Lessons:** `domain/lessons.apply_lesson`. It already writes repertoire entries (kind `opening`) and puzzle memory (kind `fix`), and `plan()` already plays a remembered fix first.
- **XP:** `grant_xp` and the XP news on the Pond and in the match viewer.
- **The "why" panel**, the move list, and series rules.

---

## 1. Opening School

**Pitch.** Show your duck an opening, move by move. It plays it back from memory. It only ever plays openings you taught it.

### Loop (v1)
1. **Pick:** a colour and an opening.
   - v1: you name it yourself ("My Italian"). Later: a catalogue of named openings.
   - Or continue one the duck already knows.
2. **Teach:** you play both sides on the board, using legal moves from a new `POST /positions/legal-moves {fen}`. Each of the duck's moves becomes a pending entry. Cap: 6 duck moves per lesson [PH].
3. **Quack-back:** the duck replays its side from the start.
   - Each move is a real `plan()` with a lesson seed, so recall depends on the Memory stat.
   - You play the other side's moves; a forgotten move gets a "Show me again".
4. **Done:** `apply_lesson(kind="opening")` writes the entries and grants XP. The summary says "remembered 5 of 6".

### What changes in the duck
- `repertoire_entries` rows: today these are flat; ADR-0016 later adds `Opening` and `opening_id`.
- XP.
- Later: a Memory point (§5).

### Replay test
In the next Arena game, the duck's opening moves show source **book** and "Remembered Bc4 from its lessons" in the why panel. With ADR-0016, the shortlist event says "Planned: My Italian".

### Smallest playable
- **v1a (one session):**
  - the legal-moves endpoint;
  - a teach screen on the playable board;
  - `POST /ducks/{id}/lessons {kind: opening, color, moves}` → `apply_lesson`;
  - the list of what the duck knows (with the counts that already show on the duck).
  - The book step already uses these entries, so ducks immediately play what they were taught.
- **v1b:** the quack-back check.
- **v1c:** `Opening` entities and the pre-game shortlist (ADR-0016).

### Questions
1. Does a lesson teach one line, or can you branch ("if they play d5, do this")?
2. Should a taught move that the Judge thinks is bad get a warning ("this loses a pawn, teach it anyway?")? Design 01 suggests yes, as optional.
3. How much should training an opening again matter: does it raise recall, or only how often the duck picks it?
4. Opening names: our own list, or a catalogue (license check)?

---

## 2. Rules of the Pond (principle cards)

**Pitch.** Flip a card ("Castle early", "Fight for the centre") and your duck adopts that habit in every position after the opening.

### Loop (v1)
1. A deck of 6 to 8 cards [PH], each with:
   - one sentence;
   - an example position;
   - the duck's choice in that example with and without the card ("without: h3; with: O-O").
2. Flip a card to adopt it. A duck holds 3 active [PH]; swapping is free.

### What changes
- `knowledge.principles`: the rule registry (`domain/rules.py`, kind `principle`) adds a small bonus to near-equal candidates. This is a style change, not strength.

### Replay test
The why panel shows "Principle bonus: castles early (+0.15)" on the moves it nudged.

### Smallest playable
- 4 principle rules with unit tests on hand-picked positions;
- `PUT /ducks/{id}/principles`;
- the card screen.
- The example comparison is two `rank()` calls on the same position, with and without the card. Bumps `DECISION_LAYER_VERSION`.

### Questions
1. Which 4 first? Suggestion: develop minor pieces, castle early, fight for the centre, don't bring the queen out early.
2. Are cards unlocked by level, or all available from the start?
3. Is 3 active about right?

---

## 3. Review Room and Blunder Training

**Pitch.** After a game, the Judge finds the moments that mattered. You find the better move, your duck learns it, and you watch it play the fix.

This is the mode closest to existing code. Teach-the-fix lessons and puzzle memory exist in the domain, and the decision layer already plays a remembered fix before anything else.

### Loop (v1)
1. **Review:** a finished Arena or Practice game shows a **Review** button. A background job runs the Judge (a fixed, stronger setting of the same engine) over the duck's moves and stores a score per move. v1 uses a quick Judge preset [PH 200k nodes per move].
2. **Critical moments:** the 3 biggest drops in winning chances [PH], each shown as a card.
3. **One card:**
   - the position before the slip;
   - the slip animates;
   - the punishment line plays (the Judge's best reply);
   - rewind: "show your duck a better move".
   - You move, and the Judge grades it: accepted if it is within `fixTolerance` [PH] of the best; otherwise "still loses …", with no penalty.
4. **Lesson:** an accepted move goes in through `apply_lesson(kind="fix")`, which writes a puzzle-memory row and grants XP.
5. **Prove it:** "Replay from here". The duck plays the position with today's mind via `decide_duck_move`. With Memory recall it plays the fix ("Remembered being taught Nf3 here"), and the game can continue from there.

**Blunder Training** is the same card screen fed by a queue of every reviewed game's cards: new cards first, then due repeats (counted in sessions, not days; design 01 §3.6). There are two doors: the Review Room (v1) and the Tactics Dojo (later).

### What changes
- `puzzle_memory` rows;
- XP;
- the review is stored per game (annotations).

### Replay test
"Replay from here" shows the new move with source **memory**, so the fix is visible in the why panel.

### Smallest playable
- **v1a:**
  - the review job and annotations table (ADR-0008);
  - critical moments;
  - the card screen;
  - grading;
  - the fix lesson;
  - replay from the fix for that one position.
- **v1b:** the persistent card queue, repeats, the hint ladder.
- **v1c:** blunder cards from your own Practice Pond moves ("your slip").

### Questions
1. How many cards per game, and what counts as a blunder for a hatchling compared with a champion?
2. Show the punishment line before asking for the fix (design 01's order)?
3. Hints: highlight the piece first, then "show me" (reduced XP)?
4. Does a correct fix also give a stat point (§5), or only XP?

---

## 4. Tactics Dojo

**Pitch.** Five puzzles on one theme. You solve; then your duck shows what it would have played. When you are right and it is wrong, you have taught it something.

### Loop (v1)
1. Pick a course: Forks, Pins, Back-rank mates, Mate in 2 [PH themes].
2. **Per puzzle:**
   - the position appears;
   - the duck answers in secret (`rank()` at its own node budget);
   - you move, graded by answer-key lookup.
   - Reveal the duck's choice. The four outcomes (you right or wrong × duck right or wrong) and what each writes are in design 01 §2.4.
3. **After five:**
   - XP;
   - motif weight bumps;
   - the duck's puzzle rating, counted only on puzzles it is seeing for the first time.

### What changes
- `knowledge.motifs` (weights);
- `puzzle_memory` when you teach a puzzle the duck got wrong;
- puzzle rating;
- XP.

### Replay test
The same puzzle later shows the duck playing the taught move (source **memory**). Motif bonuses appear in the why panel once motif detectors exist.

### Smallest playable
- **Content first:** a hand-made pack of 30 puzzles [PH]. It is our own content, so there is no license question. Answer keys are computed once by the Judge at build time (ADR-0009 format).
- The puzzle screen reuses the playable board.
- Motif detectors (fork, pin, back rank) come in v1b. Until then the courses are a theme filter and the gain is XP plus puzzle memory, and the copy must not promise more.
- **Candidate Showdown** (several ducks, one position, their top 5 side by side) is a separate screen after v1. It needs only `rank()` per duck and an eval bar.

### Questions
1. Do you solve first, or does the duck go first?
2. Is it one puzzle at a time or a timed rush mode? (A rush mode fits the arcade feel.)
3. Where do puzzles come from after the starter pack: the Lichess puzzle database (license to check), or generated from the duck's own games?

---

## 5. Stat points placed by training (the training door, part 2)

**Today:** levels raise the stat budget, but nothing places the new points. The bar shows "Stat points 240 / 246".

**v1:** finishing an activity places one unassigned point [PH] in its stat:

| Activity | Stat |
| --- | --- |
| Opening School | Memory |
| Tactics Dojo courses | Attack → Aggression; Defence → Solidity; Deep → Calculation |
| Super Bullet Arena game | Speed |
| Review fixes | None; they pay the most XP |

A `StatTrained` event lets the top bar animate the change. The Lab editor stays for respec.

**Replay test:** the duck's mind changes, visible in node budgets (Calculation), recall (Memory) and time use (Speed) in the why panel.

**Question:** one point per finished activity, or only for a passing grade?

---

## 6. League and rival ducks

**Today:**
- four placeholder challengers;
- every Arena game against them is rated;
- the farming flags are in design 03 §8.

**v1:**
- **The League ladder:** beat the challenger above you in a best of 3 to move up a rung.
- **Rewards:** a badge per rung and a "beaten the Grandmallard" trophy.
- **Ratings:** League ratings against anchors become the "real" number (session 10). Own-duck ratings stay the pond rating.

**Questions:**
1. The roster: names, personalities and art. Each challenger could have a signature opening once Opening School exists.
2. Should a rung be locked until the one below is beaten?

---

## 7. Suggested build order

| Step | What | Size | Why this order |
| --- | --- | --- | --- |
| 1 | Review Room v1a | 2 sessions | Closest to done; it is the core promise (the duck learns from your fixes) |
| 2 | Opening School v1a + v1b | 2 sessions | The legal-moves endpoint and teach screen also serve the Review Room |
| 3 | Stat points placed by training (§5) | 1 session | Makes every mode move the top bar |
| 4 | Rules of the Pond | 1 session | Small; personality after the book |
| 5 | Tactics Dojo v1 with the starter pack | 2 sessions | Needs content |
| 6 | Blunder Training queue, ADR-0016 shortlist, League ladder | later | Builds on all of the above |

---

## 8. Questions for tomorrow (all in one place)

1. **Review Room:** cards per game, punishment first or not, hints, does a fix give a stat point?
2. **Opening School:** one line or branches, warn on bad moves, what training again does, opening names.
3. **Rules of the Pond:** the first 4 principles, unlock by level or not, how many active at once.
4. **Tactics Dojo:** who answers first, one-at-a-time or rush, the puzzle source after the starter pack.
5. **Stats:** one point per activity or only on a pass.
6. **League:** ladder rules, challenger roster and personalities.
7. **Feel:** what each mode's "moment" is (the egg crack, the level-up, the duck playing your fix). These are where animation and art matter most.
