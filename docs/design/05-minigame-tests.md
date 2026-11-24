# Design 05 · Minigame tests

*2026-11-23 · Status: playable sketches for John to judge. Nothing here is decided. Every number, name and line of copy is a placeholder.*

A separate page (`#/minigame-tests`) holds rough minigames. They change no duck and save nothing (ADR-0017). John plays them, says what to keep, and official versions are designed afterwards.

## The games

| Minigame | The player does | Teaches | Comes from |
| --- | --- | --- | --- |
| Lily Pads | Hops one piece around to eat crumbs, under par; later, avoids guarded squares | How pieces move; attacked squares | The basics |
| Fair Trade? | 60 seconds of good deal / even swap / bad deal | Piece values; counting recaptures | The basics |
| Three Ways Out | Finds a run, a block and a capture | Getting out of check | The basics |
| Crack the Shell | Mate in one | Checkmate | Shell Puzzle (design 03 §1) |
| Tuck the Duckling In | Says where the king may castle | Castling rules and their exceptions | The basics |
| Rules of the Pond | Picks the move that follows a rule card | Opening principles | Design 04 §2 |
| Quack-Back | Watches an opening, then plays it from memory, longer each round | A first opening | Opening School (design 04 §1) |
| Tactics Dojo | Finds the fork, then the pin | Forks and pins | Design 04 §4 |
| Goose Chase | Mates a lone king with two rooks, a queen, then one rook | Basic mates; avoiding stalemate | Convert the win |
| Oops Pile | Watches a blunder punished, rewinds, fixes it | Blunder checking | Review Room (design 04 §3) |
| Candidate Showdown | Names three moves against three simple ducks | Candidate moves | Design 03 §2.3 |
| Pawn Race | Races pawns to the far side against a simple rival | Pawn moves, blocking, passed pawns | The basics |
| Loose Feathers | Taps every undefended black piece, 90 seconds | Loose pieces | Research |
| Square Dash | Taps the named square on an unlabelled board, 45 seconds from each side | Square names, both sides | Research |
| Pond Memory | Remembers where the pieces stood | Board memory | Research |
| Stuck or Mated? | Sorts checkmate, stalemate, check and neither, 60 seconds | Checkmate against stalemate | The basics |
| The Beginner Duck | Plays a whole game against a duck with blind spots | Nothing: an experiment | Design 06 |

## Tricks worth keeping

- **Offering moves that fail.** Three Ways Out lets you play moves that leave you in check. Noticing why they fail is the lesson.
- **Slip, punishment, rewind.** The animation frames in Oops Pile are the same mechanism as Quack-Back's "watch".
- **Marked escape squares** in Goose Chase make "shrink the box" visible.
- **A clock that stops while you read.** Speed without hurrying the explanation.
- **Answer keys built ahead of time.** Every legal move is scored once, offline, so grading is instant and any sound move counts.
- **Same puzzles again.** Seeds make a run repeatable, so two players can race the same one.

## What the sketches fake

- The Showdown's rivals are fixed rules (takes the most, pushes forward, random but safe), not real ducks.
- Goose Chase's king follows a fixed rule, not an engine.
- Pawn Race's rival is a short look-ahead with a simple pawn count (1, 3 or 5 moves by difficulty); it is not an engine.
- Loose Feathers counts a pinned defender as a defender.
- The Dojo has no duck answering beside you. Positions are engine self-play, so they can look messy.
- Oops Pile's blunders come from the pack, not from your own games.

## Feedback so far (John, 2026-11-24)

- **Stuck or Mated?** Liked.
- **Pawn Race.** Good for thinking about endgames and forcing an unwanted move. Two changes, both made:
  - *Responsive:* the rival's reply no longer locks the board. Same fix in Goose Chase and Quack-Back.
  - *Easy, Medium, Hard.* Easy: positions proven winnable with many good first moves. Medium: the original three races. Hard: dealt positions, two of five proven losing, where a tie counts as a win. Losing starts are checked to be holdable against the hard rival. Positions come from `scripts/build_pawn_races.py`, which solves each one exactly.
  - Decided: the game says when a start is losing and that a tie is the goal.
- **Square Dash.** Really liked; keeping the name for now. Timer moved above the board (for every timed game), a start screen, 45 seconds as White, a switch screen, then 45 as Black. The square to tap also shows in bold beside the title. Every timed game now opens with a Start screen.
- **The Beginner Duck.** Still feels fairly strong. Leave it alone until we work out an idea together.
- **Difficulty.** Only some games have it (Pawn Race for now). Picking such a game opens a menu first.

## Questions for John, per game

1. Is it fun? Keep, change or drop?
2. Too easy or too hard for a new player?
3. Hearts: three and out, or free retries everywhere (design 01's "never punish")?
4. Rush (clock) or calm?
5. What should the duck do or gain in the official version?

## Research notes

Read on 2026-11-23, as search summaries only.

- Small pawns-only and single-piece games are a common way to teach beginners: https://en.chessbase.com/newsroom/post/learning-chess-the-easy-way and https://www.exeterchessclub.org.uk/content/mini-chess-games
- Reduced-material games show how pieces relate: https://chess.com/blog/MomirRadovic/promise-of-chess-mini-games-in-critical-early-period-of-learning
- Scanning drills (loose pieces, captures, threats): https://www.chessworld.net/chess-training-tools.asp
- Memory for positions depends on meaningful patterns (Chase and Simon 1973), so a memory game should use real positions: https://andymatuschak.org/prompts/Chase1973.pdf
- The Lichess puzzle database is CC0, an option if more puzzles are wanted: https://huggingface.co/datasets/Lichess/chess-puzzles
