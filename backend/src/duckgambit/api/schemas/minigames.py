"""Wire shapes of the minigame tests (ADR-0017). Experimental: may change freely."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from duckgambit.api.schemas.base import Id, Wire, WireIn
from duckgambit.domain.arena import MAX_SEED
from duckgambit.domain.minigames.base import ActionType, MarkKind, Phase, Snapshot, Squares, Tone
from duckgambit.services.minigames import Run


class MinigameInfoOut(Wire):
    id: str
    title: str
    blurb: str
    teaches: str
    how_to: str


class StartMinigameRequest(WireIn):
    kind: Id
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)


class MinigameActionIn(WireIn):
    type: ActionType
    value: str = Field(default="", max_length=32)


class MinigameSquares(Wire):
    origin: str
    target: str


class MinigameMarkOut(Wire):
    square: str
    kind: MarkKind


class MinigameArrowOut(Wire):
    origin: str
    target: str
    kind: Tone


class MinigameFrameOut(Wire):
    fen: str
    last_move: MinigameSquares | None
    caption: str


class MinigameChoiceOut(Wire):
    id: str
    label: str
    detail: str


class MinigameFeedbackOut(Wire):
    tone: Tone
    text: str


class MinigameBoardOut(Wire):
    fen: str
    orientation: Literal["white", "black"]
    check: bool
    last_move: MinigameSquares | None
    coordinates: bool


class MinigameRunOut(Wire):
    id: str
    kind: str
    seed: int
    version: int = Field(description="Grows with every action")
    phase: Phase = Field(description="play: input is open; review: send `next`; done: run over")
    round: int
    rounds: int
    score: int
    hearts: int | None
    remaining_ms: int | None
    feedback: MinigameFeedbackOut | None
    frames: list[MinigameFrameOut] = Field(description="Play these before showing the board")
    prompt: str
    board: MinigameBoardOut
    moves: list[str] = Field(description="Moves the player may try (UCI)")
    squares: list[str] = Field(description="Squares the player may tap")
    marks: list[MinigameMarkOut]
    arrows: list[MinigameArrowOut]
    choices: list[MinigameChoiceOut]
    notes: list[str]
    can_hint: bool

    @classmethod
    def of(cls, run: Run, shot: Snapshot) -> MinigameRunOut:
        view = shot.view
        return cls(
            id=run.id,
            kind=run.game.info.id,
            seed=run.game.seed,
            version=shot.version,
            phase=shot.phase,
            round=shot.round,
            rounds=shot.rounds,
            score=shot.score,
            hearts=shot.hearts,
            remaining_ms=shot.remaining_ms,
            feedback=MinigameFeedbackOut.model_validate(shot.feedback) if shot.feedback else None,
            frames=[
                MinigameFrameOut(
                    fen=frame.fen, last_move=_squares(frame.last_move), caption=frame.caption
                )
                for frame in shot.frames
            ],
            prompt=view.prompt,
            board=MinigameBoardOut(
                fen=view.board.fen,
                orientation=view.board.orientation,
                check=view.board.check,
                last_move=_squares(view.board.last_move),
                coordinates=view.board.coordinates,
            ),
            moves=view.moves,
            squares=view.squares,
            marks=[MinigameMarkOut.model_validate(mark) for mark in view.marks],
            arrows=[MinigameArrowOut.model_validate(arrow) for arrow in view.arrows],
            choices=[MinigameChoiceOut.model_validate(choice) for choice in view.choices],
            notes=view.notes,
            can_hint=view.can_hint,
        )


def _squares(pair: Squares | None) -> MinigameSquares | None:
    return MinigameSquares(origin=pair[0], target=pair[1]) if pair else None
