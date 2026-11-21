# Design 01 · Training minigames, Blunder Training and Bullet Battle

*2026-11-21 · Game-design proposal for John · Status: Proposed. Nothing here is decided until John says so; technical items become ADRs or session briefs through the architect.*

Conventions: **[PH]** marks a placeholder number that belongs in the balance table and is John's to set. **[Unverified]** marks a fact I could not confirm from a primary source. Working titles for modes and emotes are placeholders; names and copy are John's.

Read with: spec sections 1, 4, 5, 6, 7 and ADR-0002, 0004 to 0009.

---

## 0. Summary

1. **Stats are earned by level and placed by training.** A level-up grants stat points (the budget in spec 4.2 is unchanged), but a point only lands in a stat when the player completes that stat's minigame. This is the Duck Life rule ("run to get better at running") on top of the existing budget, and it needs no new stored field.
2. **Four activities cover everything**: Opening Drill (Memory, repertoire, principles), Tactics Drill with themed courses (Aggression, Solidity, Calculation, Creativity, motifs), Blunder Training (XP, puzzle memory, repertoire fixes, guards), and Bullet Battle (Speed, and the source of blunders).
3. **Blunder Training is not a new pipeline.** It is ADR-0008's "teach the fix" with a different entry point (a persistent per-duck queue instead of "top 3 of this game"), one extra fact per annotation (the punishment line), and a small scheduler. Same classify, grade, `apply_lesson` and lesson check.
4. **Blunder tolerance stays derived from level and stage.** Blunder Training never writes it. It feeds it only through XP, the same currency as every other activity, with XP per blunder card capped.
5. **Human-versus-duck bullet treats the human as a recorded input.** The duck stays on its deterministic virtual clock; the human's elapsed time is measured in the service layer and passed to the domain as data. These games are never rated.
6. **Two ducks cannot measure their own growth by only playing each other.** Ratings are relative to a pool. Training games between ducks give XP and review material; the climb from 2000 toward 2500 is *measured* in League games against anchor ducks (ADR-0006 section 5).

What I would cut first, in order: the Creativity course ("find two"), the "spot it first" phase of Blunder Training, per-entry memory strength, guards (motif vigilance), time-odds handicaps beyond one preset. The core that must survive: Blunder Training, bullet sparring, the training-bullet cycle with League checks.

---

## 1. Grounding

### 1.1 What we take from Duck Life

From descriptions of the first three games [1][2]: training is a set of short skill minigames (running, swimming, flying; climbing in later entries) that each raise one skill; training and races pay coins; coins buy seed that restores energy; the duck then races rivals in leagues, and progress through leagues is the goal. Duck Life 2 also sells level-cap raises for coins [2]. I could not confirm details of Duck Life 4 or Duck Life: Battle **[Unverified]**.

| Duck Life | Duck Gambit equivalent |
| --- | --- |
| One minigame per skill | One activity per stat group (section 2) |
| Skill level rises as you play | Stat points placed by the matching minigame; knowledge rows written |
| Energy, fed with seed | `care.energy`, refilled by food earned in play |
| Coins | Food only. No currency that buys strength (pillar 5) |
| Races against rivals in leagues | Bullet Battle; League games against named anchor ducks |
| Level cap raised in a shop | Stat caps raised by growth stage only |

### 1.2 What we take from chess trainers

- **Lichess "Learn from your mistakes"** replays the mistakes of one analysed game and asks for a better move, with the answer available on request [3]. Lichess classifies by drop in winning chances, not raw centipawns: thresholds 0.1 inaccuracy, 0.2 mistake, 0.3 blunder in its source, with separate rules for mates created or lost [4]. This is the same idea as ADR-0008's expected-score loss.
- **Chess.com Game Review** offers Retry on inaccuracies, mistakes, blunders and missed wins, and "show" buttons that demonstrate the fork, the lost piece or the checkmate [5]. Chess.com describes a blunder as a very bad move that loses material or the game [5], which is John's definition.
- **The Woodpecker Method** (Smith and Tikkanen): solve a fixed set of puzzles, then repeat the same set in cycles until recognition is automatic [6]. We take "the same positions come back", not the stopwatch.

What neither trainer does, and we do: show the punishment first, then ask for the fix, and make a third party (the duck) visibly change afterwards.

---

## 2. Training as minigames

### 2.1 The rule that makes it Duck Life: earned by level, placed by training

- XP raises level. Each level grants stat points [PH: 2 per level] into the duck's budget (ADR-0006 section 2). They arrive **unassigned** (`unassigned = statBudget − sum(stats)`, derived, not stored).
- Completing a minigame session with a passing grade places up to one [PH] unassigned point into that minigame's stat. With no unassigned points the session still pays XP and knowledge.
- The duck editor (M1) can still move points by hand. Whether respec is free is John's call (section 9, Q4).
- Stage caps on each stat still apply. Nobody can max everything, as spec 4.2 requires.

Why this is honest: every stat feeds `derive_mind` (ADR-0006), so a placed point changes `nodeMultiplier`, `bookRecall`, rule weights, `temperature` or `speedFactor`. The player sees the cause (I did the opening drill) and the effect (the duck forgets its lines less often in the next lesson check).

### 2.2 The set

| Activity | Stat it places | Knowledge it writes | Session | Milestone |
| --- | --- | --- | --- | --- |
| **Opening Drill** ("Follow Me") | Memory | Repertoire entries; principles through the quiz | 2 to 4 min | M2 |
| **Tactics Drill** ("Puzzle Pond"), four courses | Attack → Aggression; Defence → Solidity; Deep → Calculation; Ideas → Creativity | Motif weights; puzzle memory | 2 to 3 min | M4 |
| **Blunder Training** ("Oops Pile") | None; pays the most XP | Puzzle memory, repertoire fixes, guards | 3 to 5 min | M5 |
| **Bullet Battle** | Speed | None directly; produces blunder cards | 1 to 6 min | M3 play, M5 review |

Blunder tolerance has no minigame because it is derived from level and stage. XP is its only input, and Blunder Training pays the best XP per energy [PH]. The client can show the derived value as a "blunder guard" meter next to the XP bar ("at level 8 your duck lets through slips up to X"). That is a display of real derived data, not a second stat.

### 2.3 Opening Drill

**Pitch.** You play your favourite opening on the board and the duck waddles after your moves. Then it quacks the line back from memory. Where it stumbles, you show it again.

**Core loop.**

1. Choose colour and a starting point: the initial position, or the end of a line the duck already knows. A session teaches up to 6 [PH] new duck-side moves.
2. **Teach.** The player plays both sides. Legal moves come from the server (ADR-0002 item 6). Each duck-side move becomes a pending repertoire entry.
3. **Sound check** (optional, balance toggle). Each taught move gets one low-budget Judge search. If its expected-score loss is above the mistake threshold the player is told what it costs and asked "teach it anyway?". Teaching a dubious gambit is allowed (spec 5.3: "including your mistakes if you want").
4. **Quack-back.** From the start of the line the duck replays its side. Each duck move is a real `plan()` call with a fixed seed: it recalls with probability `bookRecall` or forgets. Opponent moves are replayed from the taught line. On a forget the player drags the right move again.
5. **Wrap-up.** `apply_lesson` writes the entries, places a Memory point if one is unassigned, grants XP. The summary states the true recall ("remembered 5 of 6").

**What the duck gains.** Rows in `repertoire_entries` with `source = opening-drill`; +1 `weight` on entries re-shown after a forget; a Memory point; XP.

**Honesty.** Book moves are step 1 of the decision layer. `weight` only matters when a position has more than one taught move, and we say so. The quack-back is ADR-0008's lesson check applied to an opening, so a low Memory stat visibly costs recall. That is the reason to place points in Memory.

**Player learns.** The line, twice (once teaching, once patching), and what the Judge thinks of each move.

**Principles quiz** (a second door in the same building). A principle is added to `knowledge.principles` after a five-question quiz: an opening position and three candidate moves, pick the one that follows the rule. Questions are generated by the principle's own detector in the rule registry (ADR-0005), so the quiz and the duck's behaviour can never disagree, and no authored content is needed. One-time per principle. M2.

### 2.4 Tactics Drill

**Pitch.** Five puzzles on one theme. You answer, then the duck shows what it would have played. When you are right and it is wrong, you have taught it something.

**Core loop** (the "Beat the duck" presentation from spec 7.4, per puzzle).

1. Position from a pack (ADR-0009). In the background the duck runs `rank()` at its own node budget; the result is hidden.
2. The player moves. Grading is an answer-key lookup: instant, and any move that keeps the win counts.
3. The duck's first choice is revealed. Four outcomes:

| Player | Duck | What happens | Written |
| --- | --- | --- | --- |
| Right | Wrong | Player teaches; the duck replays the move | Puzzle-memory entry, motif bump, XP |
| Right | Right | Shared celebration | Motif bump, XP (smaller) |
| Wrong | Right | The duck demonstrates; the player repeats the move | XP (small) |
| Wrong | Wrong | The solution plays out; one retry | Nothing on a failed retry |

4. After five: `LessonCompleted`, a stat point for the course, and the duck's own answers update its puzzle rating (spec 4.4). A puzzle rates a duck only the first time the duck sees it, so taught answers cannot inflate the rating.

Multi-move puzzles: version 1 grades the first move from the answer key and then animates the stored solution as the "why". Playing the full line against the Defender is a later upgrade.

**Courses.** A course is a theme filter plus a stat. Theme names beyond those listed in spec 7.4 must be checked against the Lichess theme list when packs are built **[Unverified]**.

| Course | Themes (examples) | Places |
| --- | --- | --- |
| Attack | `fork`, `pin`, sacrifices, mating attacks | Aggression |
| Defence | `defensiveMove`, `equality` | Solidity |
| Deep | `mateIn2`, `mateIn3`, longer forced lines | Calculation |
| Ideas (cut first) | Any winning position: name two different moves that both keep the win | Creativity |

**Honesty.** A motif bump only matters once motif detectors exist (M4). Do not ship this drill before them. Motif weights are capped by stage [PH], and spec 5.2 already makes over-training a trade-off (a sacrifice-lover sometimes blunders), so this is a style choice and not free strength.

**Player learns.** Tactics by theme, with an immediate comparison against a mind they trained.

### 2.5 Bullet Battle as the Speed trainer

Completing a Bullet Battle game, either variant, places an unassigned point in Speed. Details are in section 4. Speed is a trade, not pure gain: quicker moves keep clock in reserve but search fewer nodes (ADR-0006 section 3).

### 2.6 Free practice

With no energy, every minigame still runs in practice mode: the player plays and learns, and nothing is written to the duck. Watching, replays and reading reviews are always free. Energy limits the duck's growth per session, never the player's access to chess (pillar 5).

---

## 3. Blunder Training in depth

### 3.1 Recommendation: a mode of ADR-0008, not a new pipeline

| | ADR-0008 review screen | Blunder Training |
| --- | --- | --- |
| Entry point | One finished game | A per-duck queue fed by every review |
| Selection | Top K by loss in that game | Eligible cards, due repeats first, then newest |
| Presentation | Critical moments list | Scene, slip, punishment, fix, check |
| Classify, grade, lesson, check | ADR-0008 | The same functions |

Additions the mode needs: (1) a **punishment** fact on each annotation, (2) a **queue** with a scheduler, (3) a **hint ladder** with XP scaling. All knowledge still enters through `apply_lesson`.

### 3.2 Where blunders come from

| Source | Whose move | How it arrives | Milestone |
| --- | --- | --- | --- |
| The duck's games (training bullet, League, tournaments) | Duck | Review job, ADR-0008 | M5 |
| Sparring, duck's moves | Duck | Same job (ADR-0008 rule 6) | M5 |
| Sparring, player's moves | Player | Same job; shown as "your slip" | M5 |
| The player's Lichess games | Player | Import (ADR-0010), then the same review job | M6 |
| Starter set for a new duck | Nobody's | A small pack with a `fix-blunder` goal (section 3.8) | M4 or M5 |

A card made from the player's own move works the same way: the player finds the better move and the duck stores it. The duck gains a position and a good move wherever the position came from.

A review of an 80-ply game at 1M Judge nodes takes about a minute and a half (ADR-0008). For bullet, run the review job while the player watches playback, and offer a quicker Judge preset [PH: 200k nodes per ply] recorded with the review.

### 3.3 What counts as a blunder here

A critical moment becomes a Blunder card when all of these hold:

1. **Class.** ADR-0008's `classify` returns `blunder`, by expected-score loss `E(best) − E(played)`. At higher stages `mistake` is also eligible, because a 2200 duck rarely hangs a piece [PH: eligible classes per stage].
2. **The punishment can be shown.** The Judge's best reply line after the bad move either forces mate (John's "blundering checkmate") or wins material of at least 2 points [PH; 1 at later stages] within 6 plies [PH] (John's "losing material").
3. **A fix exists.** Implied by the loss metric: if every move loses, the loss is small and the moment is not a blunder.

Not eligible: `missed win` and `missed mate` (the opposite skill; they can feed Tactics Drill later as replay puzzles), and positional errors with no showable punishment. Those stay in the ordinary review list. At the highest stages, where material blunders dry up, the card may show an eval-bar swing plus the Judge's line instead [PH].

The punishment is a pure function over data the Judge pass already has, because the best move at ply *n+1* is the reply to the move played at ply *n*:

```
describe_punishment(position_after_bad_move, refutation_line, rules)
  -> { kind: "mate" | "material" | "eval", mateIn, materialSwing, lost: {piece, square}, line, motif? }
```

It needs the Judge's principal variation stored per ply, not only the best move (section 7).

### 3.4 The interactive sequence

One card, seven beats. The card is a resource; the client stages the beats. Only graded actions are domain events.

| # | Beat | On the board | Duck (suggested) | Domain |
| --- | --- | --- | --- | --- |
| 1 | Scene | Position before the slip, with "move 23 against Rival" | Idle | Card fetched |
| 2 | Slip | The bad move animates | Carefree | none |
| 3 | Punishment | The opponent's reply line plays, ending on the capture or mate; the lost piece is highlighted | Shock | none |
| 4 | Rewind | Back to the position: "show your duck a better move" | Attentive | none |
| 5 | Fix | The player moves; the server grades | Thinking, then a reaction | `FixAttempted` |
| 6 | Lesson | The accepted move is stored | Lightbulb | `FixTaught`, `KnowledgeAdded`, `XpGained` |
| 7 | Check | The duck plays the position itself with a fixed seed | Proud, or sheepish | `LessonChecked` |

**Grading (beat 5)** follows ADR-0008 rule 4. Verdicts:

- `accepted`: expected score within `fixTolerance` [PH] of the best move. It need not be the Judge's first choice.
- `same-blunder`: the player repeated the bad move. "That is the one we are fixing."
- `insufficient`: playable but still loses too much. The reply says how much, shows that move's own punishment if the grading search returned one, and nothing is written.

A move outside the Judge's stored lines costs one Judge search (about a second at 1M nodes); the duck "thinks" meanwhile. Results are cached by position, move and Judge.

**"Spot it first" (optional, cut first).** Between beats 2 and 3 the player is asked to play the punishing move themselves. It trains the tactic from the other side and pays bonus XP [PH]. Off by default for beginners.

**Choice mode.** For a casual player coaching a strong duck, beat 5 can offer three options: the Judge's best move, the blunder, and a decoy taken from the duck's own candidate list (already in the `MoveChosen` event). Slightly less XP [PH]. This keeps pillar 4 true when the duck is far stronger than its trainer.

**When the duck's blunder was a taught move.** If `MoveChosen.source` was `book`, the card says so and names the lesson (ADR-0008 rule 3 makes this possible): "Your duck played this because you taught it." Options: replace the line (undo the old lesson, write the fix), keep both, or dismiss the card. The player's gambit is never overwritten silently.

### 3.5 Failure and retry under "never punish"

- Attempts are unlimited. A wrong attempt costs nothing: no XP loss, no energy, no mood drop.
- **Hint ladder**, offered after two misses: (1) the piece to move is highlighted; (2) "show me" reveals the move, and the player then plays it. The Judge's move is never shown before an attempt (ADR-0008 rule 4).
- A fix found with "show me" still writes the lesson. XP is reduced [PH: 50%] and the card returns sooner.
- A failed lesson check (the duck forgot, because recall is probabilistic) is presented as "it slipped its mind", not as the player's failure. The card goes back to the short interval.
- The player can skip or dismiss any card. Nothing decays and nothing is taken away.

Only gains vary. There is no state the player can reach that is worse than not having played.

### 3.6 Repetition: yes, counted in sessions; daily streaks: no

**Spaced repetition earns its place**, in Leitner form and counted in *training sessions*, not days:

| Box | Card returns after | A pass moves it to |
| --- | --- | --- |
| 1 (new or failed) | The next session | Box 2 |
| 2 | 2 more sessions [PH] | Box 3 |
| 3 | 5 more sessions [PH] | Mastered (retired) |

A repeat ("re-check") is quick: the duck's lesson check runs first with a new seed (`purpose = recheck:n`), then the player re-solves. Both right: box up. Otherwise back to box 1 with no penalty.

Why sessions and not wall-clock days: nothing piles up while the player is away, tests need no clock, and no timer pulls the player back.

**No daily streaks.** They reward the calendar, not chess, and a broken streak is a punishment. An in-session combo ("three clean fixes in a row") is fine as a pure client flourish with no data behind it.

### 3.7 What is written to the duck

Everything goes through `apply_lesson` (ADR-0008 rule 3) with lesson kind `blunder-fix` or `recheck`.

| Trigger | Data change | Where the decision layer uses it |
| --- | --- | --- |
| Fix accepted, ply inside the opening window | `repertoire_entries` row (`source = blunder-fix`) | Book step |
| Fix accepted, later ply | `puzzle_memory` row | Memory lookup (must be added to `plan`, section 7) |
| Card has a motif tag (M4 onward) | `guards[motif]` bump, first fix only | New guard rule (below) |
| Every accepted fix | XP: full the first time; reduced with "show me" | Level → blunder tolerance, stat budget |
| Re-check passed | Small XP, once per box; entry `strength` +1 (optional) | Recall probability of that entry |
| Never | `blunderToleranceCp`, stats, any rating | |

**A limit to state plainly.** An exact middlegame position almost never recurs in a real game. A puzzle-memory row therefore helps in the lesson check, in a replay from that position (section 4.2), and in openings, where positions do recur and a book move also saves clock. On its own that would make Blunder Training mostly an XP source with a nice story. Two things make the story true:

1. **XP is the main effect, and it is honest.** Level narrows blunder tolerance. "My duck blunders less because we fixed its blunders" is literally correct through XP.
2. **Guards generalise the lesson** (recommended for after M4; cuttable). Today a motif weight rewards moves that *create* a motif. A guard is the mirror: a penalty on a candidate whose engine line shows the opponent replying with a motif the duck has guard training against. A duck that has fixed many fork blunders becomes less likely to pick a move that allows a fork, in positions it has never seen. Guards are a new map beside `motifs`, capped per stage [PH]. They only re-rank candidates that already survived the filter, so they cannot push a duck above the engine's best move, and the calibration harness must measure their rating effect before any number ships.

Without guards the mode still works; we simply must not claim more than XP and exact-position memory.

**Why this is not a free strength grind.**

1. Blunder tolerance is a function of level and stage only. No training writes it.
2. XP per card is bounded: one fix plus at most three re-checks.
3. Cards cost energy, and XP per energy is set roughly level across activities [PH], so no activity is "the grind".
4. New cards come from real reviewed games, which also cost energy.
5. Rating is never written by training. A duck can be level 30 and it still has to win games to show a number.

### 3.8 Starter set

A new duck has no games. Two answers, both cheap:

- It gets real blunders within minutes: a hatchling's first bullet game produces plenty. The first-session flow should lead there (section 5.2).
- A small starter pack of about ten [PH] classic slips (a hanging piece, the Scholar's mate pattern, a back-rank mate, an allowed fork) for the tutorial. It is presented as "pond school", not as the duck's own games.

Pack shape: ADR-0009's format with a new goal type. `fen` is the position *before* the bad move, plus `badMove`, `refutation`, and an answer key over that position's legal moves, so grading is a lookup. Lichess puzzles are stored in this shape (the FEN is before the opponent's move; ADR-0009), but the builder must confirm with the Judge that the first move really is a blunder by our classification, because I have not verified that it always is **[Unverified]**. Ten hand-made positions avoid the question.

---

## 4. Bullet Battle in depth

### 4.1 Variant (a): the player against their own duck, 1+0

**The constraint.** CLAUDE.md rule 6: anything that affects a duck's result is seeded and uses a virtual clock. A human moves in real time.

**The resolution: the human is a recorded input.** The domain never reads a clock. A human move arrives as `(uci, elapsedMs)`, exactly as data. The duck's decision is a function of the move history, its own virtual clock, the seed and its mind, and never of the human's time. Consequences:

- Given the recorded human moves and times, the whole game replays exactly. "Re-run the stored sparring game and compare the duck's moves" is a golden test.
- The game is **never rated** and carries `mode = sparring`. No duck rating can depend on wall-clock time.

**Clocks.**

| | Human | Duck |
| --- | --- | --- |
| Clock | Real, measured by the service through an injectable clock port | Virtual, ADR-0006 formula |
| Charged | Measured `elapsedMs`, with a floor [PH: 100 ms] | Budgeted `thinkMs` |
| Shown | Local countdown, corrected by each server event | The client holds the duck's move for `thinkMs` and ticks its clock down meanwhile |
| Flag | Checked when a move arrives, or when the client calls claim-timeout and the server confirms | `remaining ≤ 0`, deterministic |

The human's clock starts when the duck's move becomes visible:

```
humanElapsed = arrival − max(duckMovePublishedAt, previousHumanArrival + duckThinkMs)
```

The server still computes the duck's move at full speed and never sleeps. On a slow machine, where the search takes longer than the budgeted `thinkMs`, the game feels slower but neither side is charged for it. No server timers are needed. A game whose client disappears is marked `abandoned` at the next start.

**Premoves.** One queued premove, held by the client. When the duck's move is presented, the client submits the premove if it appears in the server's `legalMoves` and drops it otherwise. That is a membership test on server data, not chess logic (rule 2). The server charges the floor time. Promotion defaults to a queen in bullet.

**Flagging.** Either side can lose on time. Timeout against insufficient mating material should be a draw, as in standard rules; ADR-0007's end conditions do not mention it. A **relaxed clock** option for casual players lets the human's clock turn red at zero without ending the game.

**Thinking panel.** `MoveChosen` carries candidates and evals, which would be live engine help. The client hides the panel during sparring and shows it afterwards. Local single-player needs no enforcement. A "coach peek" toggle can deliberately show the eval bar as an assist.

**Handicaps, so a weak player still has fun.** All are recorded with the game and applied by one pure function.

| Handicap | Effect | Note |
| --- | --- | --- |
| **Younger duck** (recommended main dial) | `derive_mind` is evaluated as if the duck were *k* levels lower: wider tolerance, fewer nodes | One number. "Spar against your duck as it was at level 5" |
| Time odds | The human gets 3+0 or 5+0 [PH]; the duck stays at 1+0 virtual | One preset is enough at first |
| Relaxed clock | The human cannot flag | Casual default? (Q6) |
| Material odds | Custom start position | Cut for now |

**Fair-fight staircase.** A suggested handicap from the head-to-head record: after a human win the next game is one step harder, after a loss one step easier [PH]. It is a pure function of stored results, aims at an even score, and is the measure used for the outgrow arc (section 4.3). Honest limit: a weakened Stockfish does not blunder like a person (ADR-0006 section 7); it is fun, not a human simulator.

**What a game pays.** Costs 1 energy [PH]. Pays small fixed XP for any completed game, win or lose, and places a Speed point. No XP for abandoned games or games under 10 [PH] human moves. The head-to-head record (plain win, draw and loss counts per handicap step) is the only "rating" here.

**Feeding Blunder Training.** The finished game enters the review job (ADR-0008 rule 6) for both sides. The duck's eligible slips and the player's eligible slips become cards in the same queue. The player's cards are labelled as theirs; after the outgrow point the copy can flip to "your duck shows you".

### 4.2 Variant (b): duck against duck

**Opponents.** A second duck on the same profile (training partner), a friend's imported duck file, or a League rival (a named anchor duck from the calibration table).

**Spectator loop for one game.** The server computes the 1+0 game in seconds (ADR-0007). The client plays it back paced by each move's `thinkMs` (up to about two minutes at 1x), faster, or instantly. During playback: both clocks, eval bar, thinking panel, duck emotes driven by events. The review job runs in the background so cards are ready when the game ends.

**The cycle.**

```
PLAY     a set: 2 games, colours swapped, one new arena seed
REVIEW   Judge finds each duck's critical moments; a coach's note names the weak spot
TRAIN    Blunder Training on the new cards, plus the drill the note points to
PROVE    replay from the fix: the old game resumes at the blunder with today's duck
REMATCH  new seed
MEASURE  every few sets, a League match against anchors moves the rating
```

- **Coach's note.** A pure summary of the review as reason codes, each mapped to a minigame: lost on time → Bullet; left book early → Opening Drill; slips tagged `fork` → Attack course. It answers "what do I do now?" without the player reading an engine line.
- **Replay from the fix.** Resume the stored game at the critical ply with the current duck: the runner replays the stored moves, then plays on. The duck plays its fix and the game finishes differently. Unrated, no XP, free. This is the clearest proof that the duck learned, and it is where an exact-position memory row actually fires. It is more robust than replaying the whole game with the old seed, because a level-up between games can change an earlier move.
- **Rematches use a new seed.** Unchanged ducks with the same seed reproduce the same game move for move. That is correct, and dull.

**What the player does between games.**

| Action | Time | Effect |
| --- | --- | --- |
| Read the coach's note, open the "why" panel at a critical moment | 30 s | Player understanding |
| Fix up to 3 blunders | 3 to 5 min | Lessons, XP |
| Play the suggested drill | 2 to 4 min | Stat point, knowledge |
| Feed | 10 s | Energy, mood |
| Choose which duck to coach (when both are theirs) | 5 s | The other duck's cards wait in its queue |
| Watch the replay from the fix | 1 min | Proof |
| Rematch, or enter a League match | 1 to 4 min | XP; rating if League |

**From 2000 toward 2500, honestly.**

1. *Where growth comes from.* Both ducks earn XP from each game and each fix. Levels add Calculation (more nodes) and narrow blunder tolerance; stage raises caps; repertoire fixes save clock and remove opening errors (ADR-0006 section 6). Game XP is small and fix XP is large [PH], so a coached duck climbs faster than a duck that is only watched. That is what makes the player's guidance matter.
2. *Where measurement comes from.* Two ducks that only play each other cannot show a rating rise: Glicko-2 mostly moves points between them. So **training games between a player's own ducks do not move ratings** (they pay XP and cards), and **League games against anchor ducks do**. This is Duck Life's shape: train, then race.
3. *What we do not promise.* How many sets it takes, or that 2500 is reachable in a given context, until the harness has measured each lever (spec 6.3). John's example ("around 2000, then 2500 after playing and reviewing") is the target fantasy. The balance table decides whether it takes an evening or a month.

### 4.3 The "your duck outgrows you" arc

| Phase | Staircase position | The player's role | Main training |
| --- | --- | --- | --- |
| **1. Hatchling** | The player wins at even terms | Teacher: the player's own openings and fixes | Opening Drill, sparring |
| **2. Sparring partner** | Even, small handicaps either way | Rival: both sides' slips fill the queue | Sparring, Blunder Training |
| **3. Outgrown** | The duck wins at even terms | Coach: the Judge grades, the player directs | Duck vs duck, League, choice mode |

The crossing is a one-time event per duck, `TrainerOutgrown`, fired when the duck has won 3 of the last 5 [PH] even-terms sparring games. It is a celebration, not a gate: duck-versus-duck play is available from the first session. After it:

- Sparring defaults to the "younger duck" handicap in the player's favour, so the player keeps a fair opponent.
- Review copy flips: the duck (through the Judge) shows the player their slips.
- Choice mode and the hint ladder mean a 1200 player can still coach a 2200 duck. The Judge is the authority on the fix; the player chooses what to work on.

The founding example in spec 1.3, a low-rated player teaching a duck their favourite openings, ends here: the duck plays the player's opening better than the player does, and shows them where they go wrong in it.

---

## 5. The meta loop

### 5.1 Care model (recommended answer to spec 12, decision 5)

**Session-based energy, with activity-driven hunger and no real-time decay.**

- **Energy** (0 to 10 [PH]) is spent by activities that write to the duck. It refills by feeding.
- **Food** is earned by playing: finishing a set, a League win, a passed lesson check [PH]. A pantry also refills to full after about 8 hours away [PH], so every session starts with a meal available. It never grows beyond full, so there is no stockpile to fear losing and no reason to log in on a schedule.
- **Hunger** is "room to eat": it rises as energy is spent and stops the player overfilling. It does not rise into a penalty while the player is away.
- **Mood** rises with feeding, variety (a different activity than last time), wins and passed checks, and drifts back to neutral. It multiplies XP between ×1.0 and ×1.2 [PH]. It never goes below ×1.0 and never touches move choice.
- Care never affects a game. A hungry duck plays exactly as well as a fed one (spec 4.3).
- No purchases, no timers with paid skips, no loss from neglect.

Wall-clock time appears only in the pantry refill. It enters the domain as a `now` argument (ADR-0001) and affects how much training fits in a session, never a result.

### 5.2 Energy costs (all placeholders)

| Activity | Energy | Typical time | XP | Other gains |
| --- | --- | --- | --- | --- |
| Feed | +4 | 10 s | none | Mood |
| Opening Drill | 2 | 2 to 4 min | Medium | Repertoire, Memory point |
| Tactics Drill | 2 | 2 to 3 min | Medium | Motif, course stat point |
| Blunder Training, 3 new cards | 2 | 3 to 5 min | Large | Fixes, guards |
| Re-checks due | 0 | 1 min | Small | Entry strength |
| Bullet sparring | 1 | 1 to 6 min | Small | Speed point, cards |
| Training bullet set, duck vs duck | 2 | 1 to 4 min | Small, both ducks | Cards for both |
| League match (rated) | 3 | 1 to 4 min | Small | Rating, food |
| Replay from the fix | 0 | 1 min | none | Proof |
| Free practice, watching, replays | 0 | any | none | Player learning |

### 5.3 One session

**Five minutes:** feed (10 s) → due re-checks (1 min) → one bullet game (2 min) → fix its worst blunder (1 to 2 min) → the level bar moves.

**Fifteen minutes:** feed → Opening Drill → training set against the partner duck, watched at 2x → coach's note → Blunder Training on three cards → replay from the fix → League match → rating update → feed with the winnings.

**First session of a new duck:** hatch → teach four opening moves → the first bullet game, which will be full of slips → Blunder Training on real cards, with starter cards filling in if there are fewer than three → first level-up → place the first point.

### 5.4 Across days

| When | What changes |
| --- | --- |
| Day 1 | Hatch, first lines, first fixes, the first few levels come fast [PH] |
| Week 1 | Sparring is the main mode; the staircase settles; stage 2 |
| Weeks 2 to 4 | The duck outgrows the trainer; a second duck or an imported rival becomes the partner |
| Later | League bands; the 2000 to 2500 stretch is the long game of sets, fixes and League checks |

A level-up fires `DuckLeveledUp` with the points granted and the blunder tolerance before and after, so the client can show both. A stage change fires `StageAdvanced` and raises caps.

---

## 6. Events and emotes

The domain emits facts. It does not know that a duck can gasp. Presentation beats with no domain meaning (the slip animating, the rewind) are client staging of data already in the card and are **not** events.

### 6.1 Events each activity needs

Reused from ADR-0002: `LessonStarted`, `LessonCompleted`, `FixTaught`, `LessonChecked`, `KnowledgeAdded`, `DuckLeveledUp`, `StageAdvanced`, `DuckFed`, `DuckRested`, `ReviewReady`, `CriticalMomentFound`, `PuzzleStarted`, `CandidatesSubmitted`, `PuzzleScored`, `RatingUpdated`, and all Match events.

Proposed new events:

| Event | Payload sketch | Emitted by |
| --- | --- | --- |
| `FixAttempted` | `{ itemId, move, verdict: accepted \| same-blunder \| insufficient, lossVsBest, attempt, hintLevel }` | Blunder Training, review |
| `HintRevealed` | `{ itemId, level: piece \| move }` | Blunder Training |
| `DrillItemScheduled` | `{ itemId, box, dueInSessions, mastered }` | Scheduler |
| `StatTrained` | `{ duckId, stat, from, to, unassignedLeft }` | Any minigame |
| `XpGained` | `{ duckId, amount, source, multiplier, xpAfter, xpForNextLevel }` | Any XP source |
| `CareChanged` | `{ duckId, hunger, energy, mood, cause }` | Any activity with an energy cost |
| `TrainerOutgrown` | `{ duckId, lastGames: [...] }` | Sparring |

Additive fields on existing events:

| Event | Added fields |
| --- | --- |
| `LessonStarted`, `LessonCompleted` | `kind: opening-drill \| principle-quiz \| tactics-drill \| blunder-fix \| recheck`, `practice: bool`, a results summary |
| `LessonChecked` | `kind: fix \| recall \| recheck`, `positionKey`, `expectedMove`, `playedMove`, `source` |
| `CriticalMomentFound` | `punishment { kind, mateIn, materialSwing, lost, line }`, `eligibleForDrill`, `playedSource`, `lessonId?` |
| `ReviewReady` | `coachNote: [{ code, params, suggests }]` |
| `MoveMade` | `by: human \| duck`, `elapsedMs` |
| `GameFinished` | `termination` adds `resignation`, `abandoned`; `mode`, `rated` |
| `DuckLeveledUp` | `pointsGranted`, `blunderToleranceBefore`, `blunderToleranceAfter` |

### 6.2 Suggested event-to-emote mapping

Emote names only. This table is John's; it should live in the client as data.

| Event (condition) | Emote |
| --- | --- |
| `LessonStarted` | `ready` |
| Card opened (client beat) | `curious` |
| Slip shown (client beat) | `carefree` |
| Punishment shown (client beat; `punishment.kind = material`) | `shock` |
| Punishment shown (`punishment.kind = mate`) | `faint` |
| `FixAttempted` (`insufficient`) | `head-tilt` |
| `FixAttempted` (`same-blunder`) | `wince` |
| `HintRevealed` | `peek` |
| `FixTaught` | `lightbulb` |
| `LessonChecked` (passed) | `proud` |
| `LessonChecked` (failed) | `sheepish` |
| `DrillItemScheduled` (`mastered`) | `medal` |
| `PuzzleScored` (player right, duck wrong) | `amazed` |
| `PuzzleScored` (duck right, player wrong) | `smug` |
| `PuzzleScored` (both right) | `high-five` |
| `StatTrained` | `flex` |
| `XpGained` | `sparkle` |
| `DuckLeveledUp` | `level-up-dance` |
| `StageAdvanced` | `transform` |
| `KnowledgeAdded` (repertoire) | `note-taking` |
| `MoveChosen` (source `book`) | `confident` |
| `MoveMade` (duck clock low) | `panic` |
| `GameFinished` (win / loss / draw) | `victory` / `sulk` / `shrug` |
| `GameFinished` (lost on time) | `out-of-breath` |
| `TrainerOutgrown` | `graduation` |
| `DuckFed` | `munch` |
| `CareChanged` (energy 0) | `sleepy` |
| `RatingUpdated` (up / down) | `cheer` / `determined` |

---

## 7. Technical deltas for the architect

### 7.1 Affects the foundation being built now (contract, events, data model)

| # | Delta | Why | Touches |
| --- | --- | --- | --- |
| A1 | **Participants have a kind**: `human \| duck`. `MoveMade` carries `by` and `elapsedMs`; `moves` rows store them | Sparring | ADR-0002, 0004, 0007 |
| A2 | **Games carry `mode`** (`league`, `training`, `sparring`, `replay`) **and `rated`**; rating updates happen only when `rated` | Training games and sparring must not move ratings | ADR-0004, 0006, 0007 |
| A3 | **`termination` enum** includes `resignation` and `abandoned`; decide timeout against insufficient material | Human games | ADR-0007 |
| A4 | **A game can start from a stored game and ply** (`startFrom: { gameId, ply }`, clocks included), unrated | Replay from the fix | ADR-0007 |
| A5 | **Decision source `memory`**: `plan` consults `puzzle_memory` as well as the repertoire. ADR-0005 names only the repertoire, while ADR-0008 writes puzzle-memory rows that nothing reads | Otherwise fixes outside the opening are cosmetic | ADR-0005, `MoveChosen.source` |
| A6 | **One door for all training changes**: generalise the lesson to carry a knowledge delta, an optional stat placement, XP and an energy cost, with `kind` as an enum | Stat placement and XP must be as auditable as knowledge | ADR-0008 rule 3 |
| A7 | **Reserve the new event names and additive fields** in section 6.1 | Additive under ADR-0002 item 9, cheaper to reserve now | ADR-0002 |
| A8 | **`SearchResult` keeps the principal variation per candidate**, and annotations store the best line and refutation line per ply | Punishment display; guards | ADR-0005, 0007, 0008 |
| A9 | **Seed purposes** `lesson-check` and `recheck:n` in the per-decision seed scheme | Repeated checks must differ but be reproducible | ADR-0005 |
| A10 | **Duck document**: add `knowledge.guards` (map like `motifs`); treat `unassigned` as derived; care gains `food`. Duck file schema follows | Guards, placement, care | ADR-0004 |

### 7.2 Needed later, with their sessions

| # | Delta | Milestone |
| --- | --- | --- |
| B1 | Tables: `drill_items` (duck, source, annotation or puzzle reference, state, box, due counter, attempts), `drill_attempts`; a per-duck session counter | M5 |
| B2 | Optional `strength` column on `puzzle_memory` and `repertoire_entries`, feeding per-entry recall; behind `DECISION_LAYER_VERSION` | M5 |
| B3 | Pure functions: `describe_punishment`, `is_drill_eligible`, `schedule_next`, `coach_note`, `apply_handicap`, `suggest_handicap` | M3, M5 |
| B4 | Rule signature sees the candidate's line, for the guard rule | After M4 |
| B5 | Pack goal type `fix-blunder` (pre-blunder `fen`, `badMove`, `refutation`, key over that position); builder check that the first move is a blunder | M4 or M5 |
| B6 | Named anchor "rival" ducks: the calibration anchor table gains name and avatar fields | M3 |
| B7 | Quick-review Judge preset, recorded with the review | M5 |
| B8 | Head-to-head sparring record per handicap step (can be a query over `games`) | M3 |

**API resources (sketch).**

```
POST /api/v1/sparring                       { duckId, colour, timeControl, handicap, relaxedClock } -> game + legalMoves
POST /api/v1/games/{id}/moves               { uci }     -> accepted; the duck's reply arrives on the stream
POST /api/v1/games/{id}/resign
POST /api/v1/games/{id}/claim-timeout
GET  /api/v1/ducks/{id}/sparring-record     -> counts per handicap step, suggested handicap
POST /api/v1/matches                        adds mode, rated, startFrom
GET  /api/v1/ducks/{id}/drills?due=true     -> cards (position, bad move, punishment, source; never the best move)
POST /api/v1/drills/{itemId}/attempts       { uci }     -> verdict, loss, punishment of that move
POST /api/v1/drills/{itemId}/hints          { level }
POST /api/v1/drills/{itemId}/check          -> runs the lesson check
POST /api/v1/ducks/{id}/training-sessions   { kind, params, practice } -> session; steps as sub-resources
POST /api/v1/ducks/{id}/feed
```

**Balance-table entries (all placeholders).** Stat points per level; points placed per session; XP per activity and outcome; hint XP factor; choice-mode XP factor; mood multiplier range; energy maximum and cost per activity; food per reward; pantry refill hours; drill eligibility per stage (classes, minimum material swing, horizon plies); `fixTolerance`; Leitner intervals; opening-window length; guard caps per stage and the guard penalty curve; motif caps per stage; handicap step size; staircase rule; outgrow rule; minimum plies for sparring XP; human move floor; quick-review Judge nodes.

### 7.3 Where this contradicts or stretches the ADRs

| ADR | Text | Issue | Proposed resolution |
| --- | --- | --- | --- |
| 0007 | "No wall-clock time exists on the server side of a game" | Sparring needs the human's elapsed time | A short ADR: wall-clock is allowed only in the service layer, only for the human's clock, only in unrated interactive games; the domain receives `elapsedMs` as data. Rule 6 is unchanged for anything a duck decides or any rated result |
| 0007 | The runner loops to completion as a job | Sparring waits for a human | A second service (interactive game session) that reuses the same domain functions; not a job |
| 0005 | Book step looks up the repertoire only | Puzzle memory is never read | A5 |
| 0005 | A rule looks at (board, move) | The guard rule needs the candidate's line | B4, with a version bump |
| 0006 | Stats come from the budget | Stats are now placed by training | Budget rule unchanged; record the placement rule |
| 0006 | "Results update ratings" (spec 7.2) | Training games between own ducks are unrated | A2; the rating moves in League games against anchors |
| 0008 | Top K = 3 per game, then done | A persistent queue across games | Same pipeline, new entry point (section 3.1) |
| 0008 | Annotations hold best move and scores | Lines are needed too | A8 |
| 0009 | `fen` is the solver's position | Blunder packs need the pre-blunder position | B5 |
| 0004 | Imported rating value is kept | A hand-edited duck file could carry an inflated rating and be farmed | Give imports a provisional rating from the fitted curve instead, or exclude them from rated play until calibrated |

---

## 8. Proposed work packages

Session-sized. Milestones are from spec section 10. Sparring play is proposed for M3 (earlier than the spec's M5) because it needs nothing from review; its review hook stays in M5.

| # | Title | Goal | Depends on | Milestone |
| --- | --- | --- | --- | --- |
| D1 | Training door | Generalised lesson with stat placement, XP and energy; `XpGained`, `StatTrained`, `CareChanged` | M0 skeleton | M2 |
| D2 | Care loop v1 | Energy costs, feeding, food rewards, practice mode | D1 | M2 |
| D3 | Opening Drill | Teach on the board, sound check, quack-back recall, wrap-up | D1, M2 opening lessons | M2 |
| D4 | Principles quiz | Detector-generated quiz that unlocks a principle | M2 principle rules | M2 |
| D5 | Bullet sparring | Interactive game session, human clock port, premove, resign, claim-timeout; replay golden test | M1 live board, wall-clock ADR | M3 |
| D6 | Handicap and staircase | Younger-duck handicap, time-odds preset, record, suggestion, `TrainerOutgrown` | D5 | M3 |
| D7 | League and game modes | `mode` and `rated` on games, named anchor rivals, rated League match | M3 harness and anchors | M3 |
| D8 | Tactics Drill | Beat-the-duck loop over a pack, courses, first-seen puzzle rating | M4 packs and motif detectors, D1 | M4 |
| D9 | Punishment and eligibility | `describe_punishment`, `is_drill_eligible`, lines stored on annotations | M5 Judge review | M5 |
| D10 | Blunder Training session | Queue, card resource, attempts, hint ladder, choice mode, lesson, check | D9, M5 teach-the-fix | M5 |
| D11 | Re-checks | Leitner scheduler in sessions, re-check flow, optional entry strength | D10 | M5 |
| D12 | Starter blunder pack | `fix-blunder` goal type, ten hand-made positions with keys | ADR-0009 pack schema | M4 or M5 |
| D13 | Training-bullet cycle | Sets, review during playback, coach's note, replay from the fix | D7, D10 | M5 |
| D14 | Guards | Guard map, guard rule, harness measurement of its effect | M4 detectors, M3 harness, D10 | M5 or later |
| D15 | My Lichess blunders | Imported games through the review job into the queue | M6 import, D10 | M6 |
| D16 | Emote table | Client-side data file mapping events to emote names | Any event stream | M1 web, M7 Unity |
| D17 | Care tuning | Mood, pantry and reward tuning from play data | D2 | M8 |

---

## 9. Open questions for John

In priority order. Each has my recommended default.

| # | Question | Recommended default |
| --- | --- | --- |
| Q1 | Do training games between a player's own two ducks move ratings? Your example has two ducks reaching 2500 by playing each other. | **No.** They pay XP and blunder cards. Ratings move in League games against anchor ducks, because a closed pair cannot measure its own growth |
| Q2 | Are stat points placed by minigames, or allocated freely in the editor? | **Placed by minigames**; the editor remains for respec |
| Q3 | Care pacing (spec 12, decision 5): real-time timers or session energy? | **Session energy**, food earned by play, pantry full after about 8 hours away, no decay, no streaks |
| Q4 | Is respec free? | Free until the first stage change, then free once per stage |
| Q5 | Do guards ship (blunder fixes generalise to "allows a fork" positions), or is Blunder Training XP plus exact-position memory only? | Ship guards after M4, only once the harness has measured them |
| Q6 | Sparring defaults for a new player: time control, relaxed clock, starting handicap? | Human 3+0 against the duck's 1+0, relaxed clock off, staircase starting at even |
| Q7 | Does the player ever lose anything by failing? | **Never.** Wrong attempts are free; hints reduce the gain; nothing decays |
| Q8 | Blunder card size and tone: how many per session, and is "spot it first" on by default? | 3 cards; "spot it first" off until the second stage |
| Q9 | When the duck's blunder was a move the player taught, what is the default? | Ask every time: replace, keep both, or dismiss |
| Q10 | XP weighting: how much faster should a coached duck grow than a watched one? | Fix XP about five times game XP [PH], so coaching dominates |
| Q11 | What marks "outgrown", and what copy and ceremony go with it? | Duck wins 3 of the last 5 even games; a one-time celebration; nothing is locked before it |
| Q12 | Names and emotes: mode titles, the emote list in 6.2, League rival names and art | Working titles stand until you replace them |

---

## 10. Sources

Web sources were read on 2026-11-21. Items 1, 2, 5 and 6 come from search summaries of the pages, not a full read; treat specifics as approximate.

1. Duck Life, CrazyGames listing (training minigames, seed, coins): https://www.crazygames.com/game/ducklife
2. Duck Life 2, CrazyGames listing (countries, feed, level-cap upgrade, Wix Games): https://www.crazygames.com/game/ducklife-2
3. Lichess blog, "Learn from your mistakes": https://lichess.org/blog/WFvLpiQAACMA8e9D/learn-from-your-mistakes (the page refused an automated fetch; described from search results and forum threads)
4. Lichess source, judgement thresholds (read directly): https://github.com/lichess-org/lila/blob/master/modules/tree/src/main/Advice.scala
5. Chess.com, Game Review: https://support.chess.com/en/articles/8584089-how-does-game-review-work and https://www.chess.com/terms/game-review
6. Chessable on the Woodpecker Method: https://www.chess.com/blog/Chessable/the-woodpecker-method-explained-turbocharge-your-tactical-and-strategic-vision
7. Project documents: `docs/duck-gambit-spec.md`, `CLAUDE.md`, `docs/adr/0002`, `0004` to `0010`
