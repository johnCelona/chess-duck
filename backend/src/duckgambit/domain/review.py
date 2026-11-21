"""Game review: find the moves that cost the most (spec 5.5, ADR-0008).

STUB FOR M5. Pure classification and selection are here and tested; the Judge pass
(a job that analyses every ply) and "teach the fix" are built in their sessions.

Loss is measured in expected score (win chance plus half the draw chance), not in
centipawns: +9 to +14 is not a blunder, because both are simply winning.
"""

from __future__ import annotations

from dataclasses import dataclass

from duckgambit.domain.engine_types import Candidate

OK, INACCURACY, MISTAKE, BLUNDER = "ok", "inaccuracy", "mistake", "blunder"


@dataclass(frozen=True)
class ReviewThresholds:
    """Expected-score loss, per mille. Placeholders until M5 (John: feel and balance)."""

    inaccuracy_permille: int = 50
    mistake_permille: int = 100
    blunder_permille: int = 200
    critical_moments: int = 3


DEFAULT_THRESHOLDS = ReviewThresholds()


def expected_score_permille(candidate: Candidate) -> int:
    """Win chance plus half the draw chance for the side to move, 0 to 1000."""
    if candidate.mate is not None:
        return 1000 if candidate.mate > 0 else 0
    if candidate.wdl is not None:
        win, draw, _ = candidate.wdl
        return win + draw // 2
    # No WDL reported: a rough logistic-free fallback that saturates at +/- 8 pawns.
    cp = max(-800, min(800, candidate.cp or 0))
    return 500 + cp * 500 // 800


@dataclass(frozen=True)
class JudgedMove:
    """One ply as the Judge saw it. Both lines are from the mover's point of view."""

    ply: int
    played: Candidate
    best: Candidate


@dataclass(frozen=True)
class Annotation:
    ply: int
    played: str
    best: str
    loss_permille: int
    classification: str
    missed_mate: bool


def classify(loss_permille: int, thresholds: ReviewThresholds = DEFAULT_THRESHOLDS) -> str:
    if loss_permille >= thresholds.blunder_permille:
        return BLUNDER
    if loss_permille >= thresholds.mistake_permille:
        return MISTAKE
    if loss_permille >= thresholds.inaccuracy_permille:
        return INACCURACY
    return OK


def annotate(
    moves: list[JudgedMove], thresholds: ReviewThresholds = DEFAULT_THRESHOLDS
) -> list[Annotation]:
    annotations = []
    for judged in moves:
        loss = max(0, expected_score_permille(judged.best) - expected_score_permille(judged.played))
        best_mates = judged.best.mate is not None and judged.best.mate > 0
        played_mates = judged.played.mate is not None and judged.played.mate > 0
        annotations.append(
            Annotation(
                ply=judged.ply,
                played=judged.played.move,
                best=judged.best.move,
                loss_permille=loss,
                classification=classify(loss, thresholds),
                missed_mate=best_mates and not played_mates,
            )
        )
    return annotations


def critical_moments(
    annotations: list[Annotation], thresholds: ReviewThresholds = DEFAULT_THRESHOLDS
) -> list[Annotation]:
    """The few moments worth teaching: the biggest losses, returned in game order."""
    costly = [a for a in annotations if a.classification != OK]
    worst = sorted(costly, key=lambda a: (-a.loss_permille, a.ply))[: thresholds.critical_moments]
    return sorted(worst, key=lambda a: a.ply)
