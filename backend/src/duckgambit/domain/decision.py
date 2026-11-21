"""The decision layer: how a duck turns engine candidates into a move (spec 6.1, ADR-0005).

Two pure steps around the engine search, which the caller performs:

    plan(board, mind, book, budget, seed)   -> a finished decision, or a SearchRequest
    choose(board, mind, search, seed)       -> one sampled move, with reasons
    rank(board, mind, search, top)          -> ordered candidates for puzzles, no sampling

Nothing here touches an engine, a database or a clock. For the same inputs the output
is identical on every machine. Bump DECISION_LAYER_VERSION whenever a change could
alter a move for the same inputs: it is part of the rating context.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from duckgambit.domain.balance import MindParams
from duckgambit.domain.engine_types import Candidate, SearchRequest, SearchResult
from duckgambit.domain.errors import DomainError
from duckgambit.domain.knowledge import RepertoireEntry
from duckgambit.domain.rules import RULES, Adjustment, StyleRule, adjustments_for
from duckgambit.domain.seeds import draw_below, pick_weighted, rng_for

DECISION_LAYER_VERSION = "decision-1"

# round(2**30 * 2 ** (-j / 16)) for j in 0..15: a base-2 softmax without floating point.
_FRAC16 = (
    1073741824, 1028218693, 984625594, 942880699, 902905651, 864625413, 827968132, 792865000,
    759250125, 727060411, 696235434, 666717336, 638450708, 611382493, 585461881, 560640218,
)  # fmt: skip
PPM = 1_000_000


@dataclass(frozen=True)
class Reason:
    """Why something happened. Clients may render `text` or build their own from `code`."""

    code: str
    text: str
    params: dict[str, str | int]


@dataclass(frozen=True)
class ScoredCandidate:
    move: str
    san: str
    rank: int  # the engine's order, 1 is its favourite
    cp: int | None
    mate: int | None
    wdl: tuple[int, int, int] | None
    base_score: int
    adjustments: tuple[Adjustment, ...]
    final_score: int
    filtered: bool  # dropped by the blunder-tolerance filter
    probability_ppm: int  # chance of being played, parts per million
    pv: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    move: str
    san: str
    source: str  # "memory" | "book" | "forced" | "engine"
    candidates: tuple[ScoredCandidate, ...]
    reasons: tuple[Reason, ...]
    nodes: int = 0
    depth: int = 0


@dataclass(frozen=True)
class RankedDecision:
    candidates: tuple[ScoredCandidate, ...]
    nodes: int
    depth: int


@dataclass(frozen=True)
class SearchBudget:
    nodes: int
    multipv: int


@dataclass(frozen=True)
class Plan:
    """Either `decision` is set (no search needed) or `request` is."""

    decision: Decision | None
    request: SearchRequest | None
    notes: tuple[Reason, ...] = ()


def soft_weight(gap_cp: int, half_life_cp: int) -> int:
    """Relative weight of a move `gap_cp` below the best. It halves every `half_life_cp`."""
    if gap_cp <= 0:
        return _FRAC16[0]
    if half_life_cp <= 0:
        return 0
    whole, fraction = divmod(gap_cp * 16 // half_life_cp, 16)
    if whole >= 30:
        return 0
    return _FRAC16[fraction] >> whole


def plan(
    board: chess.Board,
    mind: MindParams,
    book: tuple[RepertoireEntry, ...],
    budget: SearchBudget,
    seed: int,
    taught_move: str | None = None,
) -> Plan:
    """Steps 1 to 3 of the pipeline: memory, book, forced move, or a search request.

    `taught_move` is the fix the duck was taught for exactly this position, if any
    (puzzle memory, ADR-0008). Like book moves, it is subject to the memory stat.
    """
    legal = {move.uci(): move for move in board.legal_moves}
    if not legal:
        raise DomainError("decision.no_legal_moves", "The game is already over")
    ply = board.ply()
    notes: list[Reason] = []

    if taught_move is not None and taught_move in legal:
        san = board.san(legal[taught_move])
        if draw_below(rng_for(seed, ply, "memory-recall"), 1000) < mind.book_recall_permille:
            reason = Reason(
                "memory.recalled",
                f"Remembered being taught {san} here",
                {"move": taught_move, "san": san},
            )
            return Plan(Decision(taught_move, san, "memory", (), (reason,)), None)
        notes.append(
            Reason(
                "memory.forgot",
                "Was taught a move here but could not remember it",
                {"recallPermille": mind.book_recall_permille},
            )
        )

    known = [entry for entry in book if entry.move in legal and entry.weight > 0]
    if known:
        if draw_below(rng_for(seed, ply, "book-recall"), 1000) < mind.book_recall_permille:
            entry = known[pick_weighted(rng_for(seed, ply, "book-pick"), [e.weight for e in known])]
            san = board.san(legal[entry.move])
            reason = Reason(
                "book.recalled",
                f"Remembered {san} from its lessons",
                {"move": entry.move, "san": san, "choices": len(known)},
            )
            return Plan(Decision(entry.move, san, "book", (), (reason,)), None)
        notes.append(
            Reason(
                "book.forgot",
                "Knew a move here but could not remember it",
                {"recallPermille": mind.book_recall_permille},
            )
        )

    if len(legal) == 1:
        ((uci, move),) = legal.items()
        san = board.san(move)
        reason = Reason("forced.only_move", f"{san} is the only legal move", {"san": san})
        return Plan(Decision(uci, san, "forced", (), (*notes, reason)), None)

    request = SearchRequest(
        initial_fen=board.root().fen(),
        moves=tuple(move.uci() for move in board.move_stack),
        nodes=budget.nodes,
        multipv=min(budget.multipv, len(legal)),
    )
    return Plan(None, request, tuple(notes))


def _score(
    board: chess.Board,
    mind: MindParams,
    search: SearchResult,
    rules: tuple[StyleRule, ...],
) -> list[ScoredCandidate]:
    """Steps 4 and 5: filter by blunder tolerance, then add style adjustments."""
    legal = {move.uci(): move for move in board.legal_moves}
    usable = [candidate for candidate in search.candidates if candidate.move in legal]
    if not usable:
        raise DomainError("decision.no_candidates", "The engine returned no legal candidate")
    best_base = max(candidate.score() for candidate in usable)
    scored = []
    for index, candidate in enumerate(usable):
        move = legal[candidate.move]
        base = candidate.score()
        adjustments = adjustments_for(board, move, mind, rules)
        scored.append(
            ScoredCandidate(
                move=candidate.move,
                san=board.san(move),
                rank=index + 1,
                cp=candidate.cp,
                mate=candidate.mate,
                wdl=candidate.wdl,
                base_score=base,
                adjustments=adjustments,
                final_score=base + sum(adjustment.delta_cp for adjustment in adjustments),
                filtered=best_base - base > mind.blunder_tolerance_cp,
                probability_ppm=0,
                pv=candidate.pv,
            )
        )
    return scored


def _order(candidate: ScoredCandidate) -> tuple[int, int, str]:
    return (-candidate.final_score, candidate.rank, candidate.move)


def _with_probabilities(
    scored: list[ScoredCandidate], temperature_cp: int
) -> tuple[list[ScoredCandidate], list[int]]:
    """Step 6 setup: integer weights for the surviving candidates."""
    eligible = sorted((c for c in scored if not c.filtered), key=_order)
    top = eligible[0]
    weights = {
        c.move: (
            soft_weight(top.final_score - c.final_score, temperature_cp)
            if temperature_cp > 0
            else int(c is top)
        )
        for c in eligible
    }
    total = sum(weights.values())
    result = [
        ScoredCandidate(
            **{
                **c.__dict__,
                "probability_ppm": weights.get(c.move, 0) * PPM // total,
            }
        )
        for c in scored
    ]
    return result, [weights.get(c.move, 0) for c in result]


def choose(
    board: chess.Board,
    mind: MindParams,
    search: SearchResult,
    seed: int,
    notes: tuple[Reason, ...] = (),
    rules: tuple[StyleRule, ...] = RULES,
) -> Decision:
    """Steps 4 to 6: filter, style-score and sample one move."""
    scored, weights = _with_probabilities(_score(board, mind, search, rules), mind.temperature_cp)
    picked = scored[pick_weighted(rng_for(seed, board.ply(), "sample"), weights)]
    best = min((c for c in scored if not c.filtered), key=_order)

    reasons = list(notes)
    dropped = sum(1 for c in scored if c.filtered)
    if dropped:
        reasons.append(
            Reason(
                "filter.dropped",
                f"Ruled out {dropped} move{'s' if dropped != 1 else ''} as too risky",
                {"count": dropped, "toleranceCp": mind.blunder_tolerance_cp},
            )
        )
    for adjustment in picked.adjustments:
        reasons.append(
            Reason(
                f"style.{adjustment.rule_id}",
                f"{adjustment.kind.capitalize()} bonus: {adjustment.label} "
                f"({adjustment.delta_cp / 100:+.2f})",
                {
                    "ruleId": adjustment.rule_id,
                    "kind": adjustment.kind,
                    "deltaCp": adjustment.delta_cp,
                },
            )
        )
    if picked.move == best.move:
        reasons.append(
            Reason(
                "engine.top_choice",
                f"{picked.san} scored best after style adjustments",
                {"san": picked.san, "rank": picked.rank},
            )
        )
    else:
        reasons.append(
            Reason(
                "engine.sampled",
                f"Got creative with {picked.san} instead of {best.san}",
                {"san": picked.san, "rank": picked.rank, "probabilityPpm": picked.probability_ppm},
            )
        )
    return Decision(
        move=picked.move,
        san=picked.san,
        source="engine",
        candidates=tuple(scored),
        reasons=tuple(reasons),
        nodes=search.nodes,
        depth=search.depth,
    )


def rank(
    board: chess.Board,
    mind: MindParams,
    search: SearchResult,
    top: int = 5,
    rules: tuple[StyleRule, ...] = RULES,
) -> RankedDecision:
    """Puzzle mode: the duck's ordered ideas. Survivors of the filter come first."""
    scored, _ = _with_probabilities(_score(board, mind, search, rules), mind.temperature_cp)
    ordered = sorted(scored, key=lambda c: (c.filtered, *_order(c)))
    return RankedDecision(tuple(ordered[:top]), search.nodes, search.depth)


def candidate_from_scored(scored: ScoredCandidate) -> Candidate:
    return Candidate(scored.move, scored.cp, scored.mate, scored.wdl, 0, scored.pv)
