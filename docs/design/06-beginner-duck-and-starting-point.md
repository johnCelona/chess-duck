# Design 06 · The beginner duck, the starting point, and later scope

*2026-11-24 · §1, §4 and §5 record John's direction. §2 is what the code does today. §3 is Claude's proposal, not decided. Nothing here is built.*

## 1. Direction (John)

- A new duck should **seem like a beginner**. It must **not play random moves**, and it must not be too strong from the start. After a practice game, a new duck felt quite difficult.
- It is fine for it to be hard **once it has learned**.
- The story will name the beginner concepts. The duck has **no grasp of a concept until it completes the training for it**.
- Under consideration: start as **Beginner** or **Experienced** (§4).

## 2. Why a new duck is strong today

Read from the code; its playing strength has not been measured.

- **It searches like an engine.** In Practice Pond a duck gets 200,000 nodes a move (`services/sparring.py`). A new duck's Calculation of 40 lowers that to about 132,000, which is still far beyond a beginner's sight.
- **It only chooses among the engine's five best moves** (`MULTIPV = 5`). In most positions all five are sensible, so a real beginner's move is never on the list.
- **Blunder tolerance cannot help much.** A hatchling may play moves up to 3 pawns worse than the best, but only those five are offered, and Creativity makes the worse ones rare.
- **It sees every short tactic.** It never misses a mate in one or a hanging piece through lack of understanding.

So levels and tolerance can only choose between good moves. Turning down the numbers makes it shallower, not more human.

## 3. Proposal: blind spots that training removes

Each concept the story teaches is something the duck cannot see yet. Its mistakes then have a reason, and the reason goes away.

1. **Offer more moves.** A beginner duck considers every legal move, not five.
2. **Judge with beginner eyes.** It scores moves with a simple, short look-ahead plus the concepts it knows, not the full engine score. The engine's score stays as the answer key.
3. **Concepts switch on.** Finishing a concept's training adds it to the duck's knowledge and its judgement improves for good.
4. **It explains itself.** The why panel says "Did not notice the knight fork (not learned yet)", and later "Saw the fork: learned in Tactics Dojo".
5. **It fades out.** As concepts are learned, the engine's judgement takes over, ending at today's duck.

| Concept | Without it, the duck… | Minigame that could teach it |
| --- | --- | --- |
| Loose pieces | leaves pieces undefended | Loose Feathers |
| Counting trades | makes losing exchanges | Fair Trade? |
| Answering check well | takes the first legal escape | Three Ways Out |
| Mate in one | misses it, for both sides | Crack the Shell |
| Stalemate | throws away won games | Stuck or Mated? |
| Castling, development | drifts in the opening | Tuck the Duckling In, Rules of the Pond |
| Forks and pins | walks into them | Tactics Dojo |
| Pawn endings | pushes the wrong pawn | Pawn Race |
| Basic mates | cannot finish a won game | Goose Chase |
| Blunder checking | does not ask what comes next | Oops Pile |

**Rules it must keep:**
- **Determinism:** seeded and node-limited, and a duck's concepts are saved data. It changes moves, so it bumps `DECISION_LAYER_VERSION`.
- **Not random:** every weak move is the best move the duck can see.
- **Never `Skill Level` or `UCI_Elo`** for this (ADR-0006: they cannot be seeded, and the lowest Elo is 1320).
- **Measured:** use the calibration harness (session 08), then John plays it.

**Costs:** each concept needs its own detector and tests, and existing ducks need a migration (give them every concept, so none gets weaker). This needs an ADR before code.

**Cheapest first experiment:** items 1 and 2 plus two concepts (loose pieces, mate in one), in Practice Pond only. That is enough to judge whether it feels like a beginner.

## 4. Starting point: Beginner or Experienced (under consideration)

| | Beginner | Experienced |
| --- | --- | --- |
| Player | New to chess | Already knows chess well |
| Duck | Knows no concepts | Starts with the basics known |
| Story training | Played in order | Can be skipped |

Open:
1. Is it chosen per player or per egg?
2. Can an Experienced player still play the story?
3. Do skipped lessons give their rewards, or only the knowledge?
4. Does a Beginner get a way to skip ahead later?

## 5. Later scope (not a focus any time soon)

Only if the game becomes a good-looking Unity game, for example on Steam:
- easter eggs;
- easy training of additional ducks;
- things to unlock after the story, as a reason to keep going;
- possibly multiplayer bullet arenas: send your duck into a bracket and see if it wins.

Multiplayer would need accounts, hosting and cheat protection, none of which the local-first design has.
