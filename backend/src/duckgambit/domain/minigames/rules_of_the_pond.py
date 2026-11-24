"""Rules of the Pond: a card names a principle; find the move that follows it."""

from __future__ import annotations

import random
from dataclasses import dataclass

import chess

from duckgambit.domain.minigames.base import (
    Arrow,
    BoardView,
    Choice,
    Info,
    Minigame,
    View,
    deal,
    squares,
)


@dataclass(frozen=True)
class Card:
    rule: str
    line: str  # the moves that reach the position
    good: str
    others: tuple[str, str]
    why: str


CENTRE = "Fight for the centre"
DEVELOP = "Bring out your knights and bishops"
CASTLE = "Castle early"
QUEEN = "Don't bring the queen out early"
TWICE = "Don't move the same piece twice"
HANGING = "Don't leave pieces hanging"
OPEN_FILE = "Rooks love open files"

# Copy is placeholder (John's).
CARDS: list[Card] = [
    Card(
        CENTRE,
        "",
        "e4",
        ("h4", "a3"),
        "A pawn on e4 stands in the centre and frees the queen and a bishop.",
    ),
    Card(
        CENTRE,
        "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6",
        "d4",
        ("h3", "a4"),
        "c3 prepared d4: two pawns in the centre, and the bishop must move.",
    ),
    Card(
        DEVELOP,
        "e4 e5",
        "Nf3",
        ("Qh5", "f3"),
        "The knight comes out and attacks e5. A queen on h5 would only be chased.",
    ),
    Card(
        DEVELOP,
        "e4 e5 Nf3 Nc6",
        "Bc4",
        ("Ng1", "h4"),
        "A new piece comes out, aiming at f7.",
    ),
    Card(
        CASTLE,
        "e4 e5 Nf3 Nc6 Bc4 Bc5 d3 Nf6",
        "O-O",
        ("Kd2", "Rg1"),
        "The king is safe and the rook joins in. Kd2 and Rg1 lose the right to castle.",
    ),
    Card(
        CASTLE,
        "d4 d5 Nf3 Nf6 e3 e6 Bd3 Be7",
        "O-O",
        ("Ke2", "g4"),
        "The pieces are out, so castle. g4 tears open the king's future home.",
    ),
    Card(
        QUEEN,
        "e4 d5 exd5 Qxd5",
        "Nc3",
        ("Qf3", "Qg4"),
        "Punish Black's early queen: the knight comes out and attacks it.",
    ),
    Card(
        QUEEN,
        "e4 e5",
        "Bc4",
        ("Qh5", "Qg4"),
        "Bring out a smaller piece first. The queen would soon be chased by knights.",
    ),
    Card(
        TWICE,
        "e4 e5 Nf3 Nc6 Bc4 Nf6",
        "d3",
        ("Ng1", "Bf1"),
        "d3 guards e4 and opens a path for the other bishop. Going home undoes your work.",
    ),
    Card(
        HANGING,
        "e4 e5 Nf3 Nc6 Bb5 a6",
        "Ba4",
        ("a3", "h3"),
        "A pawn attacks the bishop, so move it to safety.",
    ),
    Card(
        HANGING,
        "e4 e5 Nf3 Nc6 Bc4 Nd4",
        "Nxd4",
        ("a3", "h3"),
        "A knight just walked onto a square you attack: your knight can take it.",
    ),
    Card(
        OPEN_FILE,
        "e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d3 Nf6 Be2 Be7 O-O O-O",
        "Re1",
        ("Kh1", "Na3"),
        "There are no pawns left on the e-file. That is a road for the rook.",
    ),
]


class RulesOfThePond(Minigame):
    info = Info(
        "rules-of-the-pond",
        "Rules of the Pond",
        "Flip a rule card, then pick the move that follows it.",
        "Opening principles: centre, development, castling, queen safety",
        "Each card is one rule. Three moves are shown as arrows: pick the one that follows the "
        "rule.",
    )
    rounds = 6

    def start_round(self, rng: random.Random) -> None:
        # Every rule comes up at most once in a run.
        rules = list(dict.fromkeys(card.rule for card in CARDS))
        rule = deal(self.seed, "rules", rules, self.round)
        self.card = deal(self.seed, rule, [c for c in CARDS if c.rule == rule], 0)
        self.board = chess.Board()
        for word in self.card.line.split():
            self.board.push_san(word)
        moves = [self.card.good, *self.card.others]
        self.options = [deal(self.seed, f"options:{self.round}", moves, i) for i in range(3)]
        self.picked = ""

    def on_choice(self, choice: str) -> None:
        self.picked = choice
        if choice == self.card.good:
            self.win_round(2, self.card.why)
        else:
            self.lose_heart(f"{self.card.good} follows the rule. {self.card.why}", ends_round=True)

    def _arrow(self, word: str) -> tuple[str, str]:
        return squares(self.board.parse_san(word).uci())

    def view(self) -> View:
        if self.phase == "play":
            arrows = [Arrow(*self._arrow(word)) for word in self.options]
        else:
            arrows = [Arrow(*self._arrow(self.card.good), "good")]
            if self.picked != self.card.good:
                arrows.append(Arrow(*self._arrow(self.picked), "bad"))
        return View(
            f"Rule card: “{self.card.rule}”. Which move follows it?",
            BoardView(self.board.fen()),
            arrows=arrows,
            choices=[Choice(word, word) for word in self.options],
        )
