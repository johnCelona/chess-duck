"""Quack-Back: watch an opening, then play it from memory. Each round goes deeper."""

from __future__ import annotations

import random

import chess

from duckgambit.domain.minigames.base import (
    BoardView,
    Choice,
    Info,
    Mark,
    Minigame,
    View,
    deal,
    legal_ucis,
    moved,
    san,
    squares,
)

# Name, whether you play White, and the main line. Plain, beginner-true versions.
LINES: list[tuple[str, bool, str]] = [
    ("Italian Game", True, "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6 O-O O-O"),
    ("Ruy Lopez", True, "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5"),
    ("Scotch Game", True, "e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nf6 Nc3 Bb4 Nxc6 bxc6"),
    ("London System", True, "d4 d5 Bf4 Nf6 e3 c5 c3 Nc6 Nd2 e6 Ngf3 Bd6"),
    ("Queen's Gambit", True, "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6"),
    ("Four Knights Game", True, "e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5 Bb4 O-O O-O d3 d6"),
    ("Caro-Kann Defence", False, "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 h4 h6"),
    ("Sicilian Defence", False, "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be2 e5"),
    ("French Defence", False, "e4 e6 d4 d5 Nc3 Nf6 e5 Nfd7 f4 c5 Nf3 Nc6"),
]


class QuackBack(Minigame):
    info = Info(
        "quack-back",
        "Quack-Back",
        "Watch an opening. Now quack it back from memory.",
        "Learning a first opening, one move deeper each time",
        "The line plays once. Then you play your side from memory and the other side answers. "
        "Every round adds one more of your moves.",
    )

    def start_round(self, rng: random.Random) -> None:
        self.name, self.white, text = deal(self.seed, self.info.id, LINES, 0)
        mine = self.round + 2  # your moves this round
        self.line: list[str] = []
        self.start = board = chess.Board()
        for word in text.split()[: 2 * mine - 1 if self.white else 2 * mine]:
            self.line.append(board.parse_san(word).uci())
            board = moved(board, self.line[-1])
        self.board, self.at = self.start, 0
        self.misses, self.missed = 0, False
        self._show()
        self._reply()

    def _show(self) -> None:
        board = self.start
        for uci in self.line:
            self.add_frames(board, [uci], f"Watch: {san(board, uci)}")
            board = moved(board, uci)

    def _reply(self) -> None:
        """The other side plays its book moves by itself."""
        while self.at < len(self.line) and self.board.turn != self.white:
            self._push()

    def _push(self) -> None:
        self.board = moved(self.board, self.line[self.at])
        self.at += 1

    def on_move(self, uci: str) -> None:
        if uci != self.line[self.at]:
            self.missed, self.misses = True, self.misses + 1
            self.lose_heart(f"Not {san(self.board, uci)}. The right piece is marked.")
            return
        self.missed = False
        before, at = self.board, self.at
        self._push()
        self._reply()
        self.add_frames(before, self.line[at : self.at])
        if self.at == len(self.line):
            praise = "Got there!" if self.misses else "Perfect recall!"
            self.win_round(max(1, 4 - self.misses), f"{praise} That is the {self.name}.")
        else:
            self.say("good", "Quack! Go on.")

    def on_choice(self, choice: str) -> None:
        self._show()
        self.misses += 1
        self.say("info", "That showing cost a point.")

    def view(self) -> View:
        marks = []
        if self.missed:
            marks = [Mark(self.line[self.at][:2], "hint")]
            if self.phase != "play":
                marks.append(Mark(self.line[self.at][2:4], "good"))
        side = "White" if self.white else "Black"
        total = (len(self.line) + 1) // 2
        return View(
            f"{self.name}: play {side}'s moves from memory.",
            BoardView(
                self.board.fen(),
                "white" if self.white else "black",
                self.board.is_check(),
                squares(self.line[self.at - 1]) if self.at else None,
            ),
            moves=legal_ucis(self.board),
            marks=marks,
            choices=[Choice("watch", "Show me again", "Costs a point")],
            notes=[f"Move {min(self.at // 2 + 1, total)} of {total}"],
        )
