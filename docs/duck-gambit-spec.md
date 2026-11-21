# Duck Gambit: Product Spec (v2)

*November 21, 2026 · Supersedes v1 · Lives in `docs/` and is the source of truth for product intent. Architecture decisions go in `docs/adr/`, work packages in `docs/sessions/`, working rules in `CLAUDE.md`.*

Status tags used below: **[Decided]** settled, **[Proposed]** our current best idea and open to change by an ADR, **[Open]** needs a decision from John.

## 0. What changed from v1

- **Python backend with native engines is decided.** The v1 plan of running Stockfish in the browser (WebAssembly) is now an optional future provider, not the default.
- **The product is now a "raise your duck" game first.** Hatching, feeding and care are the casual layer. Chess training is the serious layer underneath.
- **New: bullet matches, leveling, and a review-and-coaching loop** that makes a duck's growth feel earned (section 5.5 and section 6).
- **New: a client-agnostic architecture** so a Unity front end can be added without rewriting the game (section 3).
- **New: an optional Lichess integration**, including saving games to Lichess (section 8).
- **Puzzle Arena** (section 7.4), previously an addendum, is now a core mode.
- A roadmap built from session-sized work packages (section 10).

---

## 1. Vision

### 1.1 Pitch

Hatch a duck. Feed it, teach it chess, and send it into battle against your friends' ducks. As your duck learns, you learn too. Every duck runs on the **same engine**, so contests are decided by whose teaching and tuning is better, not by who owns the faster computer.

Inspired by Duck Life, where you raise and train a duck for races. Here the training is real chess.

### 1.2 Design pillars

1. **Teach by raising.** Chess lessons are the training, not a separate homework screen. The player picks up openings, principles and tactics by teaching them.
2. **Equal engines, different minds.** The engine is shared. Ducks differ in knowledge, style, calculation budget and judgment.
3. **Real, measured progress.** A duck's rating comes from games, not from a number we make up. "Level" is progression; "rating" is measured strength.
4. **Casual in front, chess underneath.** A non-chess player can enjoy the pet and the matches. A chess player can go deep.
5. **Never punish.** Neglect slows training but never erases knowledge. No dark patterns and no pay-to-win.
6. **Watchable.** Every match and puzzle can be spectated and replayed, with a "why did the duck play that?" panel.

### 1.3 Who it is for

- **Trainer:** creates a duck, cares for it, teaches it, enters it in matches.
- **Spectator or commissioner:** watches, and changes arena settings ("stronger engine, 10 seconds, 5 lines").
- **Casual players** who like raising a pet, and **improving players** (a low-rated player teaching a duck their favorite openings is the founding example).

### 1.4 Core loop

1. **Hatch** a duck: pick a name and avatar, get a starting stat budget.
2. **Care** for it: feeding refills the energy that powers lessons.
3. **Train** it: opening lessons, principles, tactic drills, learning from your games.
4. **Play:** sparring, duck-vs-duck matches, tournaments, puzzle battles.
5. **Review** with the duck: find its critical mistakes and "teach the fix."
6. **Level up:** XP unlocks stat budget and growth stages. Ratings update from results.

### 1.5 Example: the bullet showdown

Two ducks rated about 2000 play a 1-minute bullet match with different styles: one loves gambits, one grinds endgames. Afterwards, the review shows three moments where the gambit duck lost the initiative. The player teaches the fixes on the board. The duck replays those positions to prove it learned, gains XP and a lesson, and, after more matches and coaching, its measured rating climbs toward 2500 as its calculation budget unlocks and its blunder tolerance falls. Both players learned something about attacking chess along the way.

---

## 2. Status and scope

### 2.1 Built now (from the repo README on November 21, 2026)

- A Python 3.12 backend with a native engine service and an **Engines page**: install Stockfish 19 from a committed manifest into `engines/installed/`, tune settings, and use **Test engine**.
- A Vite + React 19 + TypeScript web app with `chess.js` (rules) and `chessground` (board UI), tests with vitest and pytest, and linting with oxlint.

### 2.2 Next

- **M0 Foundation:** an architect-led session that audits the repo, records architecture decisions, and builds the seams described in section 3, ending in a walking skeleton (hatch a duck, run a bullet match, watch it live, save the game).

### 2.3 Out of scope for now

Polished UI and animation (John owns these), a Unity client (the architecture must allow it, but we do not build it yet), real-money anything, public hosting and accounts, and training a neural network.

---

## 3. System architecture

### 3.1 Principles

The load-bearing rules are in `CLAUDE.md`. In short:

- A **pure domain core** (ducks, knowledge, move selection, scoring, ratings) with no I/O.
- **Thin clients** that only render events and call the API. No chess rules, scoring or rating math in a client.
- The domain emits **semantic events**; clients decide how to present them (a React toast now, a Unity animation later).
- **Contract first:** API and event schemas are the source of truth; clients are generated.
- **Determinism:** anything affecting a result takes a seed and uses node or depth limits, never wall-clock time.
- **External services behind ports**, off by default, faked in tests.

### 3.2 Components [Proposed]

```
 Clients: React web (now) · Unity (later)
        │  HTTP  /api/v1   +   WebSocket or SSE event streams
 ┌──────▼───────────────────────────────────────────┐
 │ API (thin)                                         │
 │ Services: duck · training · match · tournament ·   │
 │           review · puzzles · jobs                  │
 │ Domain (pure): ducks · knowledge · decision layer ·│
 │                scoring · ratings · clocks          │
 │ Adapters: UCI engines · database · file store ·    │
 │           Lichess (optional)                       │
 └──────┬───────────────────────────────────────────┘
        │  UCI over stdin/stdout
   Native Stockfish (downloaded from the manifest)
```

### 3.3 Contract and events [Proposed]

The API is versioned (`/api/v1`) and described by schemas (OpenAPI/JSON Schema), from which a TypeScript client is generated, and later a C# client for Unity. Long-running work (matches, tournaments, reviews) streams events. Starting vocabulary:

- **Duck:** `DuckHatched`, `DuckFed`, `DuckRested`, `StageAdvanced`, `DuckLeveledUp`, `KnowledgeAdded`
- **Training:** `LessonStarted`, `LessonCompleted`, `FixTaught`, `LessonChecked`
- **Match:** `MatchCreated`, `MatchStarted`, `MoveChosen` (with candidates and reasons), `MoveMade`, `MatchFinished`
- **Tournament:** `RoundStarted`, `StandingsUpdated`
- **Review:** `ReviewReady`, `CriticalMomentFound`
- **Puzzles:** `PuzzleStarted`, `CandidatesSubmitted`, `PuzzleScored`
- **Ratings:** `RatingUpdated`
- **Integrations:** `LichessLinked`, `GameImported`, `GameExported`

### 3.4 Deployment modes

| Mode | What runs where | Status |
| --- | --- | --- |
| Local web | React in the browser, Python backend and Stockfish on the same machine | [Decided] first target |
| Desktop game | Unity client plus a bundled backend sidecar the app launches; Stockfish downloaded on first run | [Proposed] |
| Hosted | Backend and engines on a server so friends can join without installing anything | [Open] later |

### 3.5 Unity front end [Proposed]

Unity is a **presentation client**: hatching, feeding and training animations, board and pieces, match playback, UI. It contains no chess rules, scoring or rating logic; it renders events from the same API as the web app.

Candidate strategies, to be settled by an ADR:

- **A. Sidecar (leading candidate for desktop):** the Unity app launches the packaged Python backend locally and talks to it over localhost. Reuses everything; offline play works.
- **B. Hosted service:** Unity talks to a server. The only option for WebGL and mobile (those platforms generally cannot spawn engine subprocesses). Costs hosting.
- **C. Re-implement the core in C#** with a native engine. Highest effort and risks the two implementations drifting apart.

GPL boundary (not legal advice): keep Stockfish a separate downloaded process, and keep Unity-side code free of GPL code unless John decides otherwise.

### 3.6 Persistence and data [Proposed]

- **Local-first**, with SQLite and migrations as the leading choice. Stored shapes are versioned.
- A portable, versioned **duck file** (JSON) that friends can import and export.
- **Game records:** PGN plus per-move metadata (candidates considered, evals, the rule or principle that influenced the choice), and an event log for replays and the thinking panel.
- Entities: Profile, Duck, Knowledge, EngineProfile, Match/Game/Move, Tournament, rating histories, puzzle packs and answer keys, Review/Annotation, integration links, Jobs.

---

## 4. The duck

### 4.1 Anatomy [Proposed]

```json
{
  "schemaVersion": 1,
  "id": "duck_01",
  "name": "Sir Quackalot",
  "avatar": { "species": "mallard", "skin": "default", "accessories": [] },
  "growth": { "stage": "duckling", "level": 7, "xp": 340 },
  "care": { "hunger": 0.2, "energy": 0.8, "mood": 0.9, "lastFedAt": "2026-11-21T09:00:00Z" },
  "stats": { "calculation": 40, "memory": 70, "aggression": 55, "solidity": 30, "creativity": 20, "speed": 50 },
  "knowledge": {
    "repertoire": {
      "white": [{ "fen": "<normalized FEN>", "move": "e2e4", "weight": 3 }],
      "black": []
    },
    "principles": ["develop_minors", "castle_early", "control_center"],
    "motifs": { "fork": 60, "pin": 30, "backRankMate": 70, "sacrifice": 20 },
    "puzzleMemory": [],
    "lessonLog": []
  },
  "ratings": {
    "game": { "value": 1000, "deviation": 350, "games": 0 },
    "puzzle": { "value": 1000, "deviation": 350 }
  }
}
```

### 4.2 Stats (a budget, not a free-for-all)

A fixed pool of points that grows with level, so nobody can max everything. All effects are tunable config.

- **Calculation:** how much engine effort the duck gets (its node budget). Higher means stronger and deeper tactics.
- **Memory:** how reliably it recalls taught opening lines.
- **Aggression / Solidity:** style weights that tilt move choice.
- **Creativity:** how often it picks a non-top move among acceptable ones (sampling temperature).
- **Speed:** how it spends a clock. High speed plays quickly and keeps time in reserve; useful in bullet.

### 4.3 Growth and care [Proposed]

- **Stages** (names are placeholders): Egg, Hatchling, Duckling, Duck, Champion. Stages unlock stat caps and features.
- **Care state:** hunger, energy, mood. Feeding refills **training energy**, which limits how many lessons fit in a session. Food can offer small, flavorful bonuses.
- **Rule:** care affects *how much* you can train, never what the duck already knows. No lost progress from neglect.

### 4.4 Level vs rating

- **Level** is progression: XP from lessons, reviews and matches. It unlocks stat budget and stages.
- **Rating** is measured strength from games (Glicko-2 is the leading choice, since its rating deviation handles new ducks well). New ducks show a provisional rating until calibrated (section 6.3).
- A separate **puzzle rating** compares ducks within a puzzle pool. It is not a game rating.
- League names by rating band (for example Pond, River, Lake, Ocean) are a placeholder idea.

### 4.5 Avatars and cosmetics

Ducks first, other species (goose, swan, penguin) as skins later. Hats, trails, board themes and pieces are unlocked by play and are cosmetic only, so balance stays in the stats. **Pieces and art** must be GPL-compatible or our own; avoid CC BY-NC assets (see section 11).

---

## 5. Training: teaching a duck

Stockfish cannot learn, so training edits the duck's data, not the engine. Every lesson ends as an update to **Knowledge**.

### 5.1 Lesson types

| Lesson | What the player does | What the duck gains | Milestone |
| --- | --- | --- | --- |
| Opening lessons | Plays a favorite line on the board or imports a PGN | Repertoire entries (position and move, weighted) | M2 |
| Principles | Toggles rules such as "develop minors," "castle by move 10," "fight for the center" | Score bonuses on candidate moves | M2 |
| Motif drills | Solves five puzzles tagged with a motif (fork, pin, back-rank mate) | A motif bonus | M4 |
| Learn from my games | Enters a Lichess username or imports PGN | A repertoire built from the moves the player actually plays | M6 |
| Sparring | Plays the duck and reviews | Review material for 5.5 | M5 |
| Endgame school | Unlocks tablebase lookups for few-piece endings | Perfect play in simple endgames | later |

### 5.2 Principles and motifs

Principles and motifs are simple heuristics applied as small score bonuses on candidate moves (for example, a fork is detected when, after the move, one piece attacks two or more valuable or undefended pieces). They can misfire, and that is a feature: a duck over-trained as a sacrifice-lover will sometimes blunder.

### 5.3 Learn from my games [Proposed, needs Lichess link]

Import the player's recent games. Count the moves they play most in each position and build a repertoire from them. A "mini-me" duck copies your habits, including your mistakes if you want. This is the clearest way to make a duck feel like *yours*.

### 5.4 Sparring

The player plays against their duck at a handicapped strength. Afterwards, the game goes through the review loop below.

### 5.5 Review and coaching loop [Proposed]

1. A fixed **Judge** engine analyzes the finished game.
2. The system finds eval swings and classifies them: blunder, mistake, missed win, missed tactic (with a motif tag where possible).
3. It shows the top few **critical moments**, ordered by impact (three is a good casual default).
4. The player **teaches the fix**: tries the better move on the board (the engine's suggestion is revealed after the attempt), or supplies their own idea.
5. The domain writes a lesson: a repertoire or puzzle-memory entry, a motif bump, XP, and a short "duck explains" line.
6. **Lesson check:** the duck replays the position with a fixed seed to show whether it learned. Success is celebrated; failure becomes another lesson.

This loop is the main source of growth from 2000 toward 2500. It is also where the player learns most.

### 5.6 Endgame school [later]

Syzygy tablebase lookups for positions with few pieces make a duck perfect in simple endings. Unlock it as a growth reward.

---

## 6. How a duck plays

### 6.1 The decision layer [Decided concept, Proposed details]

Every duck runs the same pipeline on the same engine. It must be a **pure, deterministic, unit-testable module** that returns the chosen move plus human-readable reasons.

1. **Book check.** If the position (first four FEN fields) is in the repertoire, pick a weighted-random book move. A low **memory** stat means a chance to "forget" and fall through.
2. **Ask the engine.** Search with the arena's limit and MultiPV set to *k*, getting *k* candidate moves with scores.
3. **Filter.** Drop moves more than *T* centipawns worse than the best. *T* is the **blunder tolerance**, which also lets a duck play weaker than Stockfish's built-in Elo floor.
4. **Style score.** Add bonuses for aggression (captures, checks, attacks near the enemy king), solidity (castling, retreats, trades when ahead), taught principles, and motifs.
5. **Sample.** Pick among the remaining moves with a seeded softmax. **Creativity** sets the temperature (0 means always the top-scored move).
6. **Play it** and repeat. In puzzle mode, return the ranked top 5 instead of sampling one move.

### 6.2 Strength, time and bullet [Proposed]

Time-based limits depend on the machine, so results would change from laptop to laptop. Bullet needs a clock, so we use a **virtual clock**:

- Each side has virtual time (for example 60 seconds plus an increment).
- Before each move, the duck chooses a think budget from its remaining virtual time, an estimate of moves left, and its **speed** stat.
- The budget converts to engine **nodes** using a fixed `virtualNps` constant and the duck's calculation multiplier. Search then runs on nodes, so it is repeatable on any machine.
- Virtual time is deducted, and a flag fall loses the game.

Illustrative shape (every constant is tunable config, chosen by calibration):

```
thinkSeconds = clamp(remaining / expectedMovesLeft + 0.8 * increment, minThink, maxThink) * speedFactor
nodes        = thinkSeconds * virtualNps * calculationMultiplier
remaining   -= thinkSeconds + moveOverhead
```

### 6.3 Calibration and progression (2000 toward 2500) [Proposed]

- **Rating context.** A rating only means something within one *context*: engine id and version, limit type, `virtualNps`, and arena settings. Changing the context (for example a new Stockfish release) needs recalibration or separate rating histories.
- **Calibration harness.** A headless tool plays ducks against **anchor opponents** (Stockfish at fixed UCI_Elo, Skill Level, or node limits) and fits a curve from duck settings to measured rating. A new duck shows a provisional rating until it has played enough anchor games.
- **Growth levers.** XP from lessons, reviews and matches unlocks stat budget (more calculation, better speed), lowers blunder tolerance, and adds knowledge (repertoire, puzzle memory, motifs).
- **Honesty.** The engine does not learn. We will not promise a specific rating curve until the harness has measured it. Stockfish's own strength limiter has a floor (around 1320 in recent versions), so weaker ducks rely on the blunder-tolerance filter, and a human-like engine such as Maia could be added later behind the same interface.

---

## 7. Competition

### 7.1 Arena settings [Proposed]

Settings apply to **all ducks in a match**, so the engine stays equal. Spectators can change them between games, never mid-game.

```json
{
  "engine": { "id": "stockfish-19", "threads": 1, "hashMb": 32 },
  "limit": {
    "type": "virtual-clock",
    "timeControl": { "baseSeconds": 60, "incrementSeconds": 0 },
    "virtualNps": 200000
  },
  "multiPV": 5,
  "format": "round-robin",
  "gamesPerPair": 2,
  "swapColors": true,
  "seed": 12345
}
```

`limit.type` can also be `nodes` (for example `{ "type": "nodes", "value": 200000 }`) for quick, clock-free matches. Presets: **Casual** (50k nodes, 3 lines), **Serious** (500k nodes, 5 lines), **Bullet** (1+0 virtual), **Spectator's choice**.

### 7.2 Formats

Single game, best-of-N, round robin, knockout, Swiss. Results update ratings. A "handicap" option gives one duck more nodes for fun mismatches. Long jobs run in the background with progress, cancel and resume.

### 7.3 Spectator experience

- Live board with an eval bar and duck avatars (idle, thinking, victory, sulk).
- Move list, opening name, and a **thinking panel** showing each duck's candidate lines and why it chose one ("aggression bonus +0.4").
- Speed controls (instant simulation, 1x, step), replay, and PGN export.

### 7.4 Puzzle Arena [Proposed]

A second way to compete: every duck gets the same position and shows what it would play. A stronger, fixed **Judge** grades the answers. Full-strength Stockfish would solve nearly everything, but a trained duck won't, so the contest is *whose training produced better ideas*, and the comparison is educational for the player too.

**How a round works**

1. The arena picks a position and a goal: find the win, convert it within X moves, or survive a slightly worse position.
2. Each duck runs its decision layer but returns its **ranked top 5 candidates** (ranking before sampling keeps it repeatable).
3. The Judge scores the position after each candidate.
4. The spectator view draws each duck's candidates as colored arrows, shows the eval bar for any clicked move, and updates the scoreboard.

**Modes**

| Mode | Start position | Duck's job | Success and score |
| --- | --- | --- | --- |
| Candidate Showdown | Any tactical or unclear position | Submit top 5 moves, ranked | Points from the Judge's score of its #1 pick and best-of-5; badges for unique ideas |
| Mate in N | A forced mate exists | Play moves against the Defender (a fixed engine) | Solved if it mates within N moves; faster scores more |
| Convert the Win | Clearly winning, around +4 | Play up to X moves against the Defender | Success is mate or a win-chance threshold within X moves |
| Survive | Slightly losing, around -1.5 | Defend for X moves against the Defender | Success is keeping the eval above a floor or reaching a draw |
| Head-to-head | Same unclear position | Two ducks play it out, each side once | Normal game result |

**Judging and scoring**

- **Judge:** the same engine at a fixed, much larger node budget than the ducks get. It never changes mid-round.
- **Answer key (recommended):** score *every legal move* of each puzzle with the Judge offline and store the results with the puzzle. In-game scoring is then a lookup.
- **Win chance, not just centipawns:** eval bars saturate in winning positions (+9 and +14 both mean "won"). Score with win/draw/loss output (the `UCI_ShowWDL` option) and mate distance. A move "keeps the win" if its win chance stays above about 90%; ties go to the shortest mate.
- **Candidate Showdown points (suggested):** 3 if the #1 pick matches the Judge's best result or an equally winning move; 2 if the best move is in the top 5 but not first; 1 if no best move is listed but a top-5 move still keeps the position winning or holdable; 0 otherwise; minus 1 if the #1 pick loses 200+ centipawns.
- **Idea stats:** *Agreement* (overlap between two ducks' top 5), *Original Idea* (a Judge top-3 move no other duck listed), *Trap count* (blunders among its five).

**Puzzle sources**

- **Lichess puzzle database:** 6,057,356 rated, tagged puzzles (last updated 2026-07-29), as a CSV with `PuzzleId, FEN, Moves, Rating, RatingDeviation, Popularity, NbPlays, Themes, GameUrl, OpeningTags, DailyDate`. The FEN is the position *before* the opponent's move; apply the first listed move to get the position shown to the solver. Themes such as `mateIn2`, `fork`, `pin`, `advantage` and `crushing` give winning positions; `equality` and `defensiveMove` give "hold on" exercises. Curate a pack of 500 to 1,000 puzzles into one JSON file instead of shipping all six million, and check the data's license terms before redistributing.
- The Judge should accept any move that keeps the evaluation, not only the stored solution (any checkmate counts in mate-in-one puzzles).
- **Hand-built** positions from a pasted FEN, and **replay puzzles** mined from the ducks' own games.

**Settings sketch**

```json
{
  "mode": "candidate-showdown",
  "puzzles": { "source": "lichess-curated", "themes": ["fork", "mateIn3"], "ratingRange": [1200, 1800], "count": 10 },
  "ducks": ["duck_01", "duck_02", "duck_03"],
  "duckSearch": { "limit": { "type": "nodes", "value": 100000 }, "multiPV": 5 },
  "equalEngine": true,
  "judge": { "limit": { "type": "nodes", "value": 2000000 }, "wdl": true },
  "goal": { "type": "convert", "withinMoves": 6, "target": "mate-or-win-chance-95" },
  "runsPerPuzzle": 3
}
```

`equalEngine: true` gives every duck the same node budget so only training differs; `false` lets the calculation stat scale it. Presets: *Warm-up* (mate in 1 to 2, 5 puzzles), *Tactics Night* (mixed, 10), *Boss Fight* (one hard, slightly losing position rated 2000+).

**Spectator view:** colored arrows per duck (thick for #1, thin for #2 to #5), a click-through to the Judge's line, an idea map of ducks by moves, and a **puzzle rating** per duck updated against the ratings of the puzzles it solves or fails. A **Beat the duck** option lets the player solve first, then reveal the ducks' answers.

---

## 8. Lichess integration (optional) [Proposed, to verify]

Lichess is a **port**, off by default, with a fake adapter for tests. Every row below must be verified against the current Lichess API docs and terms before building; do not rely on this table alone.

| Feature | What it gives | Notes |
| --- | --- | --- |
| Link account | Log in with Lichess | OAuth with PKCE and minimal scopes. Tokens never in the repo, logs, or client bundle. |
| Import my games | Repertoire and "mini-me" ducks | Games export. Respect rate limits (one request at a time per token, back off after a 429). |
| Save duck games to Lichess | Review in Lichess analysis, keep a history | **[Open]** Investigate game-import and study endpoints, what actually attaches to an account, and the rules. Fallback: PGN export for manual import. |
| Opening explorer | Human "textbook" moves by rating band | Requires an authentication token on every request. Cache results. |
| Puzzle database | Puzzle packs | Check license terms before redistributing. |
| Cloud eval | Quick eval bar in openings | Cached positions only, no custom strength or time, rate-limited. |
| Tablebase API | Endgame school | Rate-limited (about one request per second). |
| Bot accounts | Ducks play real people | Fresh account with zero games, upgrade is irreversible. A v3 showpiece, not core. |

---

## 9. Engines

### 9.1 Engine service [Decided, built]

Engines run in the Python backend as separate native processes speaking UCI. The browser never talks to an engine directly. The service provides:

- A **manifest** of installable engines (id, version, license, source URL, per-platform downloads with pinned sha256). Installs go to `engines/installed/` and are gitignored.
- An installer with checksum verification, safe archive extraction, and a smoke test (`uci`, `isready`).
- Settings built from the engine's advertised options plus a curated metadata layer, saved as named profiles.
- A **Test engine** action that returns top lines, eval, depth, nodes and time.

### 9.2 Safety rules [Decided]

- Never forward raw UCI text. Only allowlisted options are user-settable, each clamped to the engine's advertised range and to server caps.
- File-path and file-writing options (for example `EvalFile`, `SyzygyPath`, `Debug Log File`) are server-controlled only.
- Cap total Threads and Hash across all running engines. Always time out and clean up subprocesses.
- Show Stockfish's GPL-3.0 notice with a link to its source.

### 9.3 More engines later

Anything that speaks UCI can be added by manifest entry: Leela Chess Zero, Maia for human-like play, others. Browser WebAssembly builds can come back as an optional provider behind the same `Engine` interface.

---

## 10. Roadmap: milestones as coding sessions

Each milestone is split into session-sized work packages in `docs/sessions/NN-slug.md`, each with a goal, acceptance criteria, test plan, and a ready-to-paste prompt.

| Milestone | Outcome | Spec sections | Needs John |
| --- | --- | --- | --- |
| **M0 Foundation** | Audit, ADRs, contracts, domain and persistence skeleton, decision layer, deterministic match runner, walking skeleton | 3, 6 | License, Unity strategy, layout |
| **M1 Hatch and first match** | Real hatching flow, duck editor and stats, live spectating, PGN download, duck file import/export | 4, 7.3 | Art direction, feel |
| **M2 Train a duck** | Opening lessons (board and PGN), principles, knowledge in the decision layer, "why did it play that" panel | 5.1, 5.2 | Lesson UX |
| **M3 Tournaments and ratings** | Arena settings UI, round robin / knockout / Swiss, Glicko-2, calibration harness, bullet clock tuning, leaderboard | 6.2, 6.3, 7 | Balance numbers |
| **M4 Puzzle Arena** | Answer-key script, curated pack, Candidate Showdown, then the other modes, motif drills, puzzle ratings | 7.4 | Puzzle difficulty |
| **M5 Review and level-up** | Judge review, critical moments, teach the fix, lesson check, XP curve, stage progression | 5.5, 4.3 | XP curve, feel |
| **M6 Lichess link** | OAuth, import my games, mini-me ducks, save games (per feasibility), explorer "textbook" | 5.3, 8 | Privacy choices |
| **M7 Unity vertical slice** | Generated C# client, sidecar packaging, hatching and match playback in Unity | 3.5 | Art, animation |
| **M8 Polish and share** | Care loop tuning, cosmetics, daily puzzle, shareable duck links, optional async tournaments through CI, optional hosted mode | 4.3, 4.5 | Everything |

---

## 11. Limitations and recommendations

### 11.1 Limitations

- **Stockfish is not teachable.** "Training" is a decision layer (book, style weights, filters), not learning. Say so honestly in the README and in game text.
- **Weak, human-like play is hard.** Stockfish's own Elo limiter bottoms out around 1320 and its errors look odd. Weak ducks need the blunder-tolerance filter, or Maia later.
- **Fairness depends on settings.** Use node limits or the virtual clock and give every duck the same limits. Real-time limits make results hardware-dependent.
- **Ratings are contextual.** A rating is only comparable within one rating context (section 6.3). Engine upgrades change strength.
- **Style is approximate.** Stockfish has no "aggression" setting, so style comes from re-ranking its candidate moves. Expect subtlety, and tune for fun.
- **The Judge is an opinion, not truth.** It is an engine at a fixed budget. In positions with many winning moves, score on win chance and mate distance and accept any move that keeps the win.
- **Puzzle data is big and has terms.** Ship a curated pack and check the license. Puzzle ratings only compare ducks within the same pool.
- **Lichess limits.** The opening explorer needs a token and is throttled, so cache and never ship a token in client code. Bot accounts are permanent.
- **Licensing.** Stockfish and Chessground are GPL-3.0. Piece sets in the Lichess repository vary: some are GPL-compatible (for example cburnett, GPLv2+) or permissive (for example chessnut, Apache 2.0); many popular sets are CC BY-NC-SA (non-commercial) and some are personal-use only. Read `COPYING.md` in the Lichess repo per set. The effect on a Unity distribution is a decision for John, and this is not legal advice.
- **Hosting.** A Python backend with native engines cannot run on static hosting such as GitHub Pages. Friends need your machine, a bundled desktop build, or a hosted server.
- **Unity.** WebGL and mobile generally cannot spawn engine processes, so they need a hosted service.
- **CPU cost.** Tournaments are compute-heavy. Keep bounded concurrency, job queues and caps.
- **Scope creep.** Live multiplayer, accounts and anti-cheat are real work. Keep them out of M0 to M5.

### 11.2 Recommendations

1. **Run M0 first.** Settle layout, contracts, events and data before features. Build seams, not features.
2. **Keep ducks plain, versioned JSON** and the engine behind one interface, so engines can be swapped without touching the game.
3. **Default to node-limited or virtual-clock matches** with presets (Casual, Serious, Bullet).
4. **Build the calibration harness early** (M3). Without it, "2500" is just a label.
5. **Build puzzle answer keys offline** with a Python script and ship them with the pack, so the game only runs ducks and scores by lookup.
6. **Use Lichess for data, not compute:** the player's games, the explorer, and puzzles, with the user supplying their own token.
7. **Make art and pieces our own or GPL-compatible** from the start.
8. **Add one stretch goal at a time:** review loop, then Lichess link, then Unity, then hosting.

---

## 12. Open decisions for John

1. **Repository license** (GPL-3.0 is the likely fit for Stockfish and Chessground) and its effect on a Unity distribution.
2. **Unity timing and strategy:** desktop-only sidecar first, or hosted from the start?
3. **Hosting:** will friends play on your machine, a bundled build, or a hosted server?
4. **Rating system:** Glicko-2 (proposed) or plain Elo?
5. **Care loop pacing:** real-time timers, or session-based energy?
6. **Art direction:** who draws the ducks and pieces, and in what style?
7. **Duck species and names** for the first release.
8. **Lichess privacy:** what we store about linked accounts and imported games.

---

## Appendix A: Engine concepts

From the Chess.com settings screen, mapped to engine terms:

- **Strength preset (Game Review):** mostly "about this much thinking time per position." The engine ratings shown are on Chess.com's own scale.
- **Maximum time:** a cap per move (`go movetime`).
- **Number of lines:** the UCI option **MultiPV**. Extra lines share the engine's effort, so line 3 is judged less deeply than line 1.
- **Threads:** parallel search threads. More means more positions per second with diminishing returns, up to your CPU cores.
- **Lite vs full:** Lite builds use a smaller neural network (small download, slightly weaker). Native Stockfish has no lite variant as far as we know, so keep the starter engine small through defaults: 1 thread, small hash, node limit.
- **Local vs cloud:** cloud runs on a server's CPUs, possibly on a different engine version.

Other options that matter for the game:

- **Hash (MB):** transposition table memory. 16 to 64 MB is plenty here.
- **Skill Level (0 to 20)** and **UCI_LimitStrength + UCI_Elo:** built-in ways to weaken Stockfish (check `uci` output for your version's Elo range).
- **Limit type:** `go nodes`, `go depth` and `go movetime`. Nodes are reproducible across machines; time is not.
- **UCI_ShowWDL:** reports win/draw/loss chances, useful for scoring winning positions.
- **Syzygy tablebases:** perfect endgame play with few pieces.

UCI in 30 seconds:

```
uci
isready
setoption name MultiPV value 3
position startpos moves e2e4 e7e5
go nodes 200000
```

The engine streams `info ... score cp 28 pv ...` lines and finishes with `bestmove ...`. Scores are in centipawns (100 is roughly one pawn).

## Appendix B: Glossary

- **Duck:** a player's trainable chess agent: stats, knowledge, growth state.
- **Decision layer:** the pipeline that picks a duck's move (section 6.1).
- **Knowledge:** a duck's repertoire (keyed by normalized FEN), principles, motifs, puzzle memory, lesson log.
- **Level / XP:** progression that unlocks stat budget and growth stages.
- **Rating:** measured strength from games, valid within one rating context.
- **Rating context:** engine id and version, limit type, `virtualNps`, and arena settings.
- **Virtual clock:** a simulated game clock that converts think time to engine nodes, so results are repeatable on any machine.
- **Calibration harness:** a headless tool that plays ducks against anchor opponents and fits settings to measured ratings.
- **Judge:** a fixed, stronger engine setting that grades moves identically for every duck.
- **Defender:** a fixed engine opponent in convert-the-win and survive exercises.
- **Answer key:** precomputed Judge scores for every legal move of a puzzle position.
- **Critical moment:** a position in a finished game where a duck's move cost a lot, shown in the review loop.
- **Teach the fix / Lesson check:** the review steps where the player supplies a better move and the duck then proves it learned.
- **Duck file:** a portable, versioned JSON export of a duck.
- **Arena:** the shared match settings for all ducks in a game or tournament.

## Appendix C: Sources

- Stockfish 19 release (September 5, 2026): https://stockfishchess.org/blog/2026/stockfish-19/
- Stockfish.js (WebAssembly builds): https://github.com/nmrugg/stockfish.js
- Lichess API documentation: https://lichess.org/api
- Lichess opening explorer now requires authentication: https://lichess.org/@/thibault/blog/the-opening-explorer-now-requires-authentication/FSWh9Zg3
- Lichess puzzle database (format, themes, size): https://database.lichess.org/
- Lichess asset licenses (per piece set): https://github.com/lichess-org/lila/blob/master/COPYING.md
- Chessground (board UI, GPL-3.0): https://github.com/lichess-org/chessground
- MIT-licensed piece sets, per their author: https://github.com/HollowLeaf1981/ChessPieces
