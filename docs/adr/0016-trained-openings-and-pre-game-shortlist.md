# ADR-0016 · Trained openings and the pre-game shortlist

Status: Proposed · 2026-11-21 · Source: John's answer Q9 in `docs/design/03-player-journey.md` §7 · Amends ADR-0004 (repertoire shape) and ADR-0005 (book step) · Built with session 06

## Context

Today the repertoire is a flat list of `RepertoireEntry(color, position_key, move, weight, source, lesson_id)`. `plan()` recalls any entry that matches the current position. The weight was meant to carry "Always / Often / Sometimes" per move.

John changed the model:
- A duck plays only the openings it has been trained on. Finishing Opening School for an opening adds that opening to the duck.
- Before each game, the duck picks a shortlist of up to three openings, based on its preferences and the opponent. That choice is its personality.
- When the opponent leaves the line, it plays from the engine as normal.
- The shortlist obeys rule 6: it is built only from saved data (both ducks) and the game seed, so a replay picks the same openings.

## Options

1. **Keep a flat repertoire and tag entries with a name.** Cheap, but "how much was this opening trained" and "how does it score" have no home, and a shortlist would have to be rebuilt from entry tags each time.
2. **An `Opening` entity that owns its entries** (chosen). Training counts, the player's star and results attach to one row. The book step filters by the shortlisted opening ids.
3. **A global opening catalogue the duck references.** Useful later for names and ECO codes, but a duck's opening must still be its own (taught lines can differ from theory and include the player's mistakes, spec 5.3). The catalogue can be added as an optional `catalogue_key`.

## Decision

### Data model

- **`Opening`** (new table `openings`, in the duck document and the duck file):
  - `id`
  - `duck_id`
  - `color` (`white` | `black`)
  - `name`
  - `catalogue_key` (nullable)
  - `starred` (the player's pick)
  - `times_trained`: +1 per completed Opening School session for it, capped by the balance table
  - `created_at`
  - `last_trained_at`
- **A Black opening** also has `answers`: the White first move it replies to, in UCI (for example `e2e4` for "Sicilian vs 1.e4"). For White it is null.
- **`RepertoireEntry`** gains `opening_id`. An opening is the tree of its entries.
  - `weight` remains only to choose between branches *inside* one opening (default 1).
  - There are no per-move Always / Often / Sometimes labels.
- **The same position can belong to several openings.** Each opening keeps its own entry, so a transposition does not merge two openings.
- **Results are not stored on the opening.** Each game records `white_opening_id` and `black_opening_id`: the shortlisted opening whose book move the duck actually played, or null. Score with an opening is then a query over games.
- **Migration:**
  - Existing entries move into one "Taught lines" opening per duck and colour.
  - The duck document and duck file schema versions bump, with upcasters.

### Preference

Each trained opening gets an integer preference for this game. Every number is a placeholder in the balance table:

| Term | Points | Why |
| --- | --- | --- |
| Starred by the player | +4 | The player's choice dominates |
| Training | +1 per session, up to +5 | Practice shows |
| Results with it | `round(4 × (points + 1) / (games + 2))`, 0 to 4 | It plays what works; smoothed so one game does not decide |
| Head-to-head with this opponent | +2 if it scored at least 50% with this opening against this opponent (at least 2 games) | Personality reacts to the opponent |
| Opponent is prepared | −2 if the opponent's repertoire covers this opening's first 4 duck-side positions from the other side | Avoids walking into the opponent's home preparation |

The minimum is 1, so a trained opening is never impossible.

### Shortlist

- **Draw:** a weighted draw without replacement of up to 3 openings for the colour the duck plays, using `rng_for(game_seed, 0, "opening-shortlist:<color>")` and `pick_weighted` (`domain/seeds.py`).
- **Black:** the draw takes at most one defence per White first move (`answers`) before it fills the remaining slots. That way three slots cover 1.e4, 1.d4 and another start rather than three answers to 1.e4.
- **Inputs:**
  - Both ducks' openings, training counts, results and head-to-head summaries are snapshotted **when the match is created** and stored with the match.
  - Every game of the match, and any replay, therefore uses the same inputs.
  - Results from game 1 do not change game 2's shortlist within the same match.
- **Event:** a new `OpeningsChosen { gameId, duckId, color, openings: [{ id, name, preference }] }`, emitted after `GameStarted`. The "why" panel can show "Planned: Italian, London".

### In the game

- The book step (ADR-0005 step 1) only considers entries whose `opening_id` is in the duck's shortlist.
  - A transposition into a shortlisted opening counts.
  - Several shortlisted moves in one position are chosen by a seeded weighted pick, as today.
  - The memory-stat recall chance still applies, so a duck with low Memory can forget its own line.
- Taught fixes (puzzle memory) are not openings and are not filtered by the shortlist.
- Once no shortlisted entry matches, the duck plays from the engine with its style and principle rules, as now.
- `MoveChosen` reasons for a book move carry `openingId` and `openingName`.
- This changes moves for the same inputs, so it bumps `DECISION_LAYER_VERSION`. The new numbers bump `Balance.version`.

### A duck with no trained openings

Its book is empty, so it plays from the engine from move 1, shaped by style and principles, with seeded variety. No hidden default repertoire exists. The client may show "No openings trained yet", and that empty state is the reason to visit Opening School.

## Consequences

- Personality becomes visible and explainable: the shortlist event says what the duck planned, and every book move names its opening.
- Opening School has a clear output: one opening, added or strengthened.
- Rating context changes once, when this ships. Old ratings stay in their old context (ADR-0006).
- Duck files gain `openings`. Importing an older file puts its entries into "Taught lines" openings.

## Not building yet

- A catalogue of named openings with ECO codes (`catalogue_key` is reserved).
- Opponent modelling beyond head-to-head results and repertoire overlap.
- Changing the shortlist mid-match.
