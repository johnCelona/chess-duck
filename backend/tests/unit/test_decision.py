import chess
import pytest

from duckgambit.domain.balance import MindParams
from duckgambit.domain.decision import SearchBudget, choose, plan, rank, soft_weight
from duckgambit.domain.engine_types import Candidate, SearchResult
from duckgambit.domain.errors import DomainError
from duckgambit.domain.knowledge import RepertoireEntry

BUDGET = SearchBudget(nodes=10_000, multipv=5)


def mind(**overrides) -> MindParams:
    values = {
        "node_multiplier_milli": 1000,
        "book_recall_permille": 1000,
        "blunder_tolerance_cp": 100,
        "temperature_cp": 0,
        "aggression_weight": 0,
        "solidity_weight": 0,
        "speed_factor_permille": 1000,
    }
    return MindParams(**{**values, **overrides})


def result(*lines: tuple[str, int]) -> SearchResult:
    return SearchResult(
        tuple(Candidate(move, cp, None, None, 8, (move,)) for move, cp in lines),
        nodes=10_000,
        depth=8,
    )


def book(move: str, weight: int = 1) -> RepertoireEntry:
    from duckgambit.domain.chessutil import position_key

    return RepertoireEntry("white", position_key(chess.Board()), move, weight)


def test_book_move_is_played_without_a_search_when_memory_is_perfect():
    planned = plan(chess.Board(), mind(), (book("e2e4"),), BUDGET, seed=1)

    assert planned.request is None
    assert planned.decision.move == "e2e4"
    assert planned.decision.source == "book"
    assert planned.decision.reasons[0].code == "book.recalled"


def test_duck_with_no_memory_forgets_its_book_and_asks_the_engine():
    planned = plan(chess.Board(), mind(book_recall_permille=0), (book("e2e4"),), BUDGET, seed=1)

    assert planned.decision is None
    assert planned.request.nodes == 10_000
    assert [note.code for note in planned.notes] == ["book.forgot"]


def test_book_weights_decide_how_often_each_line_is_picked():
    entries = (book("e2e4", 9), book("d2d4", 1))

    picks = [
        plan(chess.Board(), mind(), entries, BUDGET, seed).decision.move for seed in range(400)
    ]

    assert 320 < picks.count("e2e4") < 390


def test_illegal_book_moves_are_ignored():
    planned = plan(chess.Board(), mind(), (book("e2e5"),), BUDGET, seed=1)

    assert planned.decision is None


def test_a_taught_fix_is_recalled_before_the_book():
    planned = plan(chess.Board(), mind(), (book("e2e4"),), BUDGET, seed=1, taught_move="g1f3")

    assert planned.decision.move == "g1f3"
    assert planned.decision.source == "memory"


def test_the_only_legal_move_is_played_without_a_search():
    board = chess.Board("k7/8/8/8/8/8/1q6/K7 w - - 0 1")

    planned = plan(board, mind(), (), BUDGET, seed=1)

    assert planned.decision.source == "forced"
    assert planned.decision.move == "a1b2"


def test_search_request_carries_the_full_move_history():
    board = chess.Board()
    board.push_uci("e2e4")
    board.push_uci("c7c5")

    request = plan(board, mind(), (), BUDGET, seed=1).request

    assert request.initial_fen == chess.STARTING_FEN
    assert request.moves == ("e2e4", "c7c5")
    assert request.multipv == 5


def test_planning_a_finished_game_is_an_error():
    board = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")

    with pytest.raises(DomainError, match="over"):
        plan(board, mind(), (), BUDGET, seed=1)


def test_zero_creativity_always_plays_the_top_scored_move():
    search = result(("e2e4", 40), ("d2d4", 35), ("g1f3", 30))

    moves = {choose(chess.Board(), mind(), search, seed).move for seed in range(50)}

    assert moves == {"e2e4"}


def test_moves_beyond_the_blunder_tolerance_are_never_played():
    search = result(("e2e4", 40), ("d2d4", 35), ("a2a4", -200))

    decisions = [
        choose(chess.Board(), mind(temperature_cp=500), search, seed) for seed in range(300)
    ]

    assert all(decision.move != "a2a4" for decision in decisions)
    dropped = next(c for c in decisions[0].candidates if c.move == "a2a4")
    assert dropped.filtered
    assert dropped.probability_ppm == 0
    assert "filter.dropped" in [reason.code for reason in decisions[0].reasons]


def test_creativity_spreads_choices_across_acceptable_moves():
    search = result(("e2e4", 40), ("d2d4", 35), ("g1f3", 30))

    moves = [
        choose(chess.Board(), mind(temperature_cp=50), search, seed).move for seed in range(300)
    ]

    assert set(moves) == {"e2e4", "d2d4", "g1f3"}
    assert moves.count("e2e4") > moves.count("g1f3")


def test_same_seed_gives_the_same_decision():
    search = result(("e2e4", 40), ("d2d4", 35), ("g1f3", 30))
    creative = mind(temperature_cp=80)

    first = choose(chess.Board(), creative, search, seed=77)
    second = choose(chess.Board(), creative, search, seed=77)

    assert first == second


def test_aggressive_duck_prefers_a_capture_and_says_why():
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    search = result(("b1c3", 30), ("e4d5", 20))

    decision = choose(board, mind(aggression_weight=100), search, seed=1)

    assert decision.move == "e4d5"
    capture = next(c for c in decision.candidates if c.move == "e4d5")
    assert [a.rule_id for a in capture.adjustments] == ["capture"]
    assert capture.final_score == 40
    assert "style.capture" in [reason.code for reason in decision.reasons]


def test_probabilities_cover_exactly_the_surviving_candidates():
    search = result(("e2e4", 40), ("d2d4", 35), ("a2a4", -500))

    decision = choose(chess.Board(), mind(temperature_cp=30), search, seed=3)

    total = sum(c.probability_ppm for c in decision.candidates)
    assert 999_990 <= total <= 1_000_000


def test_shorter_mate_outranks_longer_mate_and_any_centipawn_score():
    quick = Candidate("a2a3", None, 2, None, 8, ())
    slow = Candidate("a2a4", None, 5, None, 8, ())
    winning = Candidate("e2e4", 900, None, None, 8, ())
    losing = Candidate("h2h4", None, -3, None, 8, ())

    assert quick.score() > slow.score() > winning.score() > losing.score()


def test_rank_returns_ordered_ideas_without_sampling():
    search = result(("e2e4", 40), ("d2d4", 45), ("g1f3", 30), ("a2a4", -300))

    ranked = rank(chess.Board(), mind(temperature_cp=90), search, top=3)

    assert [c.move for c in ranked.candidates] == ["d2d4", "e2e4", "g1f3"]


def test_rank_puts_filtered_moves_last():
    search = result(("e2e4", 40), ("a2a4", -300))

    ranked = rank(chess.Board(), mind(), search, top=5)

    assert [c.move for c in ranked.candidates] == ["e2e4", "a2a4"]
    assert ranked.candidates[1].filtered


def test_soft_weight_halves_every_half_life():
    full = soft_weight(0, 50)

    assert soft_weight(50, 50) == full // 2
    assert soft_weight(100, 50) == full // 4
    assert soft_weight(10_000, 50) == 0
    assert soft_weight(25, 50) == pytest.approx(full / 2**0.5, rel=1e-6)
