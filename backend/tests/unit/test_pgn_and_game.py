import chess

from duckgambit.domain.arena import STARTING_FEN
from duckgambit.domain.chessutil import legal_destinations, move_flags, position_key
from duckgambit.domain.game import outcome_of, points, time_forfeit
from duckgambit.domain.pgn import PgnGame, PgnMove, export_pgn


def game(**overrides) -> PgnGame:
    values = {
        "event": "Duck Gambit match",
        "site": "Duck Gambit",
        "date": "2026.11.21",
        "round": "1",
        "white": "Sir Quackalot",
        "black": "Bill",
        "result": "1-0",
        "termination": "checkmate",
        "time_control": "60+0",
        "initial_fen": STARTING_FEN,
        "seed": 42,
        "rating_context": "ctx_test",
        "engine": "Fake 1",
        "moves": (
            PgnMove("e2e4", "book", None, None, 59_900),
            PgnMove("e7e5", "engine", -20, None, 58_480),
            PgnMove("d1h5", "engine", 35, None, 58_000),
            PgnMove("b8c6", "engine", None, -2, 57_000),
        ),
    }
    return PgnGame(**{**values, **overrides})


def test_pgn_has_headers_evals_from_whites_side_and_clocks():
    pgn = export_pgn(game())

    assert '[White "Sir Quackalot"]' in pgn
    assert '[TimeControl "60+0"]' in pgn
    assert '[Seed "42"]' in pgn
    assert "1. e4 { [%clk 0:00:59] book }" in pgn
    assert "1... e5 { [%eval 0.20] [%clk 0:00:58] }" in pgn
    assert "2... Nc6 { [%eval #2] [%clk 0:00:57] }" in pgn
    assert pgn.rstrip().endswith("1-0")


def test_pgn_round_trips_through_a_standard_parser():
    import io

    import chess.pgn

    parsed = chess.pgn.read_game(io.StringIO(export_pgn(game())))

    assert [move.uci() for move in parsed.mainline_moves()] == ["e2e4", "e7e5", "d1h5", "b8c6"]
    assert parsed.errors == []


def test_custom_start_position_sets_the_fen_header():
    fen = "k7/8/8/8/8/8/1q6/K7 w - - 0 1"

    pgn = export_pgn(game(initial_fen=fen, moves=(PgnMove("a1b2", "forced", None, None, None),)))

    assert f'[FEN "{fen}"]' in pgn
    assert '[SetUp "1"]' in pgn


def test_time_forfeit_is_named_in_the_termination_header():
    assert '[Termination "Time forfeit"]' in export_pgn(game(termination="time_forfeit"))


def test_outcome_detects_checkmate_and_the_ply_cap():
    mated = chess.Board()
    for san in ("f3", "e5", "g4", "Qh4#"):
        mated.push_san(san)

    outcome = outcome_of(mated, max_plies=400)
    assert (outcome.result, outcome.termination, outcome.winner) == ("0-1", "checkmate", "black")

    opening = chess.Board()
    opening.push_san("e4")
    assert outcome_of(opening, max_plies=400) is None
    assert outcome_of(opening, max_plies=1).termination == "ply_cap"


def test_threefold_repetition_is_claimed_automatically():
    board = chess.Board()
    for _ in range(2):
        for uci in ("g1f3", "g8f6", "f3g1", "f6g8"):
            board.push_uci(uci)

    assert outcome_of(board, max_plies=400).termination == "threefold_repetition"


def test_time_forfeit_awards_the_other_side():
    assert time_forfeit(loser_is_white=True).result == "0-1"
    assert points("0-1", "black") == 1.0
    assert points("1/2-1/2", "white") == 0.5
    assert points("1-0", "black") == 0.0


def test_position_key_ignores_move_counters_and_unusable_en_passant():
    first = chess.Board()
    first.push_san("e4")
    second = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 5 9")

    assert position_key(first) == position_key(second)


def test_move_flags_describe_a_move_for_a_client_without_rules():
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")

    flags = move_flags(board, chess.Move.from_uci("e1g1"))

    assert flags.castle == "kingside"
    assert not flags.capture
    assert legal_destinations(chess.Board())["e2"] == ["e3", "e4"]
