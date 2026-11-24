"""The shared shape of every minigame test (ADR-0017, design 05).

A minigame is a small state machine: seed in, actions in, a `Snapshot` out. The snapshot
says what to draw (board, marks, buttons, animation frames) and which input is open, so
one client screen plays every minigame and holds no chess rules. The same seed and the
same actions always give the same snapshots; the player's time arrives as data.

All numbers (hearts, points, rounds) are placeholders for John.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import ClassVar, Literal

import chess

from duckgambit.domain.errors import DomainError
from duckgambit.domain.seeds import draw_below, rng_for

Tone = Literal["good", "bad", "info"]
MarkKind = Literal["crumb", "pad", "danger", "good", "bad", "hint", "target"]
Phase = Literal["play", "review", "done"]
ActionType = Literal["move", "square", "choice", "next", "hint", "timeout"]
Squares = tuple[str, str]

VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


@dataclass(frozen=True)
class Level:
    id: str
    label: str
    detail: str


@dataclass(frozen=True)
class Info:
    id: str
    title: str
    blurb: str
    teaches: str
    how_to: str
    levels: tuple[Level, ...] = ()  # difficulties, easiest first; empty when there is only one
    level: str = ""  # the one to start with


@dataclass(frozen=True)
class Action:
    type: ActionType
    value: str = ""


@dataclass(frozen=True)
class Mark:
    square: str
    kind: MarkKind


@dataclass(frozen=True)
class Arrow:
    origin: str
    target: str
    kind: Tone = "info"


@dataclass(frozen=True)
class Frame:
    """One step of an animation the client plays before showing the rest of the view."""

    fen: str
    last_move: Squares | None = None
    caption: str = ""


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class Feedback:
    tone: Tone
    text: str


@dataclass(frozen=True)
class BoardView:
    fen: str
    orientation: Literal["white", "black"] = "white"
    check: bool = False
    last_move: Squares | None = None
    coordinates: bool = True


@dataclass(frozen=True)
class Banner:
    """A screen between two parts of a run. The client shows it over the board until `next`."""

    title: str
    text: str
    button: str
    turns_board: bool = False


@dataclass
class View:
    """What the player sees now, and what they may do."""

    prompt: str
    board: BoardView
    moves: list[str] = field(default_factory=list)
    squares: list[str] = field(default_factory=list)  # squares the player may tap
    marks: list[Mark] = field(default_factory=list)
    arrows: list[Arrow] = field(default_factory=list)
    choices: list[Choice] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    can_hint: bool = False
    banner: Banner | None = None


@dataclass(frozen=True)
class Snapshot:
    version: int  # grows with every action
    phase: Phase
    round: int
    rounds: int
    score: int
    hearts: int | None
    remaining_ms: int | None
    feedback: Feedback | None
    frames: tuple[Frame, ...]
    view: View


class Minigame(ABC):
    """Subclasses fill `start_round`, `view` and the `on_*` handlers they use."""

    info: ClassVar[Info]
    rounds: int = 5
    start_hearts: ClassVar[int | None] = 3
    time_limit_ms: ClassVar[int | None] = None

    def __init__(self, seed: int, level: str = "") -> None:
        self.seed = seed
        self.level = level or self.info.level
        if self.level and self.level not in [item.id for item in self.info.levels]:
            raise DomainError("minigame.level", "No such difficulty")
        self.round = 0
        self.score = 0
        self.hearts = self.start_hearts
        self.used_ms = 0
        self.version = 0
        self.phase: Phase = "play"
        self.feedback: Feedback | None = None
        self.frames: list[Frame] = []
        self._begin()

    # What a game defines.

    @abstractmethod
    def start_round(self, rng: random.Random) -> None: ...

    @abstractmethod
    def view(self) -> View: ...

    def on_move(self, uci: str) -> None:
        raise DomainError("minigame.action", "There is no move to play now")

    def on_square(self, square: str) -> None:
        raise DomainError("minigame.action", "There is no square to tap now")

    def on_choice(self, choice: str) -> None:
        raise DomainError("minigame.action", "There is nothing to choose now")

    def on_hint(self) -> None:
        raise DomainError("minigame.action", "There is no hint here")

    def on_time_up(self) -> None:
        """The clock ran out: the run is over, unless a game has another part to play."""
        self.say("info", "Time!")
        self.phase = "done"

    # What every game shares.

    def act(self, action: Action, spent_ms: int = 0) -> Snapshot:
        """Apply one player action. `spent_ms` is the time since the last one, and counts
        only while the player is playing (not while they read a result)."""
        if self.phase == "done":
            raise DomainError("minigame.finished", "This run is over")
        self.frames = []
        if self.phase == "play" and self.time_limit_ms is not None:
            self.used_ms += max(0, spent_ms)
            if self.used_ms >= self.time_limit_ms:
                self.on_time_up()
                return self._bump()
        if action.type == "timeout":
            return self._bump()  # claimed early: there is still time on the clock
        if action.type == "next":
            if self.phase != "review":
                raise DomainError("minigame.action", "Finish this round first")
            self._advance()
            return self._bump()
        if self.phase != "play":
            raise DomainError("minigame.action", "The round is over: go on to the next one")
        open_now = self.view()
        if action.type == "move":
            self._require(action.value, open_now.moves)
            self.on_move(action.value)
        elif action.type == "square":
            self._require(action.value, open_now.squares)
            self.on_square(action.value)
        elif action.type == "choice":
            self._require(action.value, [choice.id for choice in open_now.choices])
            self.on_choice(action.value)
        else:
            if not open_now.can_hint:
                raise DomainError("minigame.action", "There is no hint here")
            self.on_hint()
        return self._bump()

    def snapshot(self) -> Snapshot:
        remaining = None
        if self.time_limit_ms is not None:
            remaining = max(0, self.time_limit_ms - self.used_ms)
        view = self.view()
        if self.phase != "play":
            view.moves, view.squares, view.choices, view.can_hint = [], [], [], False
        return Snapshot(
            self.version,
            self.phase,
            self.round + 1,
            self.rounds,
            self.score,
            self.hearts,
            remaining,
            self.feedback,
            tuple(self.frames),
            view,
        )

    def say(self, tone: Tone, text: str) -> None:
        self.feedback = Feedback(tone, text)

    def win_round(self, points: int, text: str) -> None:
        self.score += points
        self.say("good", text)
        self.phase = "review"

    def lose_heart(self, text: str, *, ends_round: bool = False) -> None:
        """A miss. Out of hearts, the run ends once this result has been shown."""
        self.say("bad", text)
        if self.hearts is not None:
            self.hearts = max(0, self.hearts - 1)
        if ends_round or self.hearts == 0:
            self.phase = "review"

    def add_frames(self, board: chess.Board, ucis: Iterable[str], caption: str = "") -> None:
        """Animate moves from `board`, which is left untouched."""
        for uci in ucis:
            board = moved(board, uci)
            self.frames.append(Frame(board.fen(), squares(uci), caption))

    def _advance(self) -> None:
        if self.hearts == 0 or self.round + 1 >= self.rounds:
            self.phase = "done"
            return
        self.round += 1
        self._begin()

    def _begin(self) -> None:
        self.phase = "play"
        self.feedback = None
        self.start_round(rng_for(self.seed, self.info.id, self.round))

    def _bump(self) -> Snapshot:
        self.version += 1
        return self.snapshot()

    @staticmethod
    def _require(value: str, allowed: list[str]) -> None:
        if value not in allowed:
            raise DomainError("minigame.action", "That is not possible here")


def squares(uci: str) -> Squares:
    return uci[:2], uci[2:4]


def pick[T](rng: random.Random, items: list[T]) -> T:
    return items[draw_below(rng, len(items))]


def deal[T](seed: int, label: str, items: list[T], index: int) -> T:
    """The `index`-th card of a deck shuffled by the seed: no repeats within a run."""
    order = list(items)
    rng = rng_for(seed, label, "deck")
    for i in range(len(order) - 1, 0, -1):
        j = draw_below(rng, i + 1)
        order[i], order[j] = order[j], order[i]
    return order[index % len(order)]


def legal_ucis(board: chess.Board) -> list[str]:
    return sorted(move.uci() for move in board.legal_moves)


def moved(board: chess.Board, uci: str) -> chess.Board:
    after = board.copy(stack=False)
    after.push(chess.Move.from_uci(uci))
    return after


def san(board: chess.Board, uci: str) -> str:
    return str(board.san(chess.Move.from_uci(uci)))


def name_at(board: chess.Board, square: int) -> str:
    piece = board.piece_type_at(square)
    assert piece is not None
    return str(chess.piece_name(piece))


def board_after(board: chess.Board, uci: str) -> BoardView:
    after = moved(board, uci)
    return BoardView(after.fen(), check=after.is_check(), last_move=squares(uci))
