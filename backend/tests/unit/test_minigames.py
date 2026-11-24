"""Every minigame test is playable, fair and repeatable (ADR-0017)."""

import chess
import pytest

from duckgambit.domain.errors import DomainError
from duckgambit.domain.minigames import content, pawn_races
from duckgambit.domain.minigames.base import Action, moved
from duckgambit.domain.minigames.beginner_eyes import (
    LOOSE,
    MATE,
    exchange_loss,
    loosest,
    mate_in_one,
    think,
)
from duckgambit.domain.minigames.catalog import MINIGAMES, start
from duckgambit.domain.minigames.fair_trade import FairTrade, capture_value
from duckgambit.domain.minigames.goose_chase import GooseChase, free_squares, runaway
from duckgambit.domain.minigames.lily_pads import LilyPads
from duckgambit.domain.minigames.loose_feathers import loose
from duckgambit.domain.minigames.pawn_race import LEVELS, race_moves, race_over, rival_move, search
from duckgambit.domain.minigames.pawn_solver import race_of, solve
from duckgambit.domain.minigames.quack_back import LINES
from duckgambit.domain.minigames.rules_of_the_pond import CARDS
from duckgambit.domain.minigames.stuck_or_mated import verdict
from duckgambit.domain.minigames.three_ways_out import ThreeWaysOut, way_out
from duckgambit.domain.minigames.tuck_in import TuckIn
from duckgambit.domain.seeds import draw_below, rng_for

KINDS = [game.info.id for game in MINIGAMES]


def mash(kind, seed, steps=120, level=""):
    """Press random open inputs; every snapshot must be sane. Returns them all."""
    game, rng, seen = start(kind, seed, level), rng_for(seed, "player"), []
    shot = game.snapshot()
    for _ in range(steps):
        seen.append(shot)
        if shot.phase == "done":
            break
        view = shot.view
        options = [Action("move", m) for m in view.moves]
        options += [Action("square", s) for s in view.squares]
        options += [Action("choice", c.id) for c in view.choices]
        if view.can_hint:
            options.append(Action("hint"))
        if shot.phase == "review":
            options = [Action("next")]
        assert options, f"{kind}: stuck in {shot}"
        chess.Board(view.board.fen)
        shot = game.act(options[draw_below(rng, len(options))], 10)
    return seen


@pytest.mark.parametrize("kind", KINDS)
def test_a_run_never_gets_stuck_and_repeats_exactly(kind):
    for seed in range(5):
        assert mash(kind, seed) == mash(kind, seed)


def lily_pads_hop(game):
    for uci in game.view().moves:
        to, left, here = chess.parse_square(uci[2:4]), game._solve(), (game.at, game.crumbs)
        if game._guarded(to):
            continue
        game.at, game.crumbs = to, game.crumbs - {to}
        after = game._solve()
        game.at, game.crumbs = here
        if after is not None and after < left:
            return uci
    raise AssertionError("no hop gets closer")


def way_not_found(game):
    return next(m.uci() for m in game.board.legal_moves if way_out(game.board, m) not in game.found)


def best_unpicked(game):
    return max((u for u in game.key if u not in game.picks), key=lambda u: game.key[u])


# What a player who knows the answer does next.
PERFECT = {
    "lily-pads": lambda g: Action("move", lily_pads_hop(g)),
    "fair-trade": lambda g: Action("choice", g.answer),
    "three-ways-out": lambda g: Action("move", way_not_found(g)),
    "crack-the-shell": lambda g: Action("move", g.card["mates"][0]),
    "tuck-in": lambda g: Action("choice", g.answer),
    "rules-of-the-pond": lambda g: Action("choice", g.card.good),
    "quack-back": lambda g: Action("move", g.line[g.at]),
    "tactics-dojo": lambda g: Action("move", g.card["best"]),
    "oops-pile": lambda g: Action("move", g.best),
    "loose-feathers": lambda g: Action(
        "square", next(chess.square_name(s) for s in g.targets if s not in g.found)
    ),
    "square-dash": lambda g: Action("square", chess.square_name(g.target)),
    "pond-memory": lambda g: Action("square", chess.square_name(g.todo[0])),
    "stuck-or-mated": lambda g: Action("choice", g.answer),
    "candidate-showdown": lambda g: Action("move", best_unpicked(g)),
}


def test_every_minigame_has_a_winning_way_checked():
    assert set(PERFECT) | {"goose-chase", "pawn-race", "beginner-duck"} == set(KINDS)


@pytest.mark.parametrize("kind", PERFECT)
def test_perfect_play_wins_every_round_without_losing_a_heart(kind):
    for seed in range(4):
        game = start(kind, seed)
        for _ in range(300):
            if game.phase == "done":
                break
            if game.phase == "review":
                assert game.feedback.tone == "good"
                game.act(Action("next"))
            else:
                game.act(PERFECT[kind](game))
        assert game.phase == "done"
        assert game.round + 1 == game.rounds
        assert game.hearts == game.start_hearts
        assert game.score >= game.rounds


def mate_line(board, depth):
    """A forced win against the runaway's fixed rule within `depth` moves, if there is one."""
    for move in board.legal_moves:
        after = board.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            return [move.uci()]
        if depth == 1 or after.is_stalemate():
            continue
        reply = runaway(after)
        if after.is_capture(reply):
            continue
        after.push(reply)
        rest = mate_line(after, depth - 1)
        if rest:
            return [move.uci(), *rest]
    return None


def test_the_goose_can_be_caught():
    game = GooseChase(4)  # a seed with a three-move mate
    for uci in mate_line(game.board, 3):
        game.act(Action("move", uci))
    assert game.phase == "review"
    assert game.feedback.tone == "good"


def test_goose_chase_marks_exactly_where_the_king_may_step():
    board = chess.Board("8/8/8/4k3/8/8/R7/4K3 b - - 0 1")
    assert set(free_squares(board)) == {m.to_square for m in board.legal_moves}


def test_a_pawn_race_rival_takes_a_win_and_blocks_a_loss():
    board = chess.Board("8/8/8/8/8/8/1p5P/8 b - - 0 1")
    assert rival_move(board).uci() == "b2b1q"
    # Only taking the runner stops it from queening.
    board = chess.Board("8/p1p5/1P6/8/8/8/7P/8 b - - 0 1")
    assert rival_move(board).uci() in {"a7b6", "c7b6"}


def test_a_pawn_race_ends_on_arrival_capture_or_no_moves():
    assert race_over(chess.Board("Q7/p7/8/8/8/8/8/8 b - - 0 1")) == "white"
    assert race_over(chess.Board("8/p7/8/8/8/8/8/8 w - - 0 1")) == "black"
    assert race_over(chess.Board("8/8/8/p7/P7/8/8/8 w - - 0 1")) == "stuck"


def test_a_pawn_race_can_be_won():
    game = start("pawn-race", 1)
    for level in range(game.rounds):
        for _ in range(300):
            if game.phase != "play":
                break
            # A player who looks one move further than the rival.
            game.hearts = 3
            best = max(
                game.view().moves,
                key=lambda u: (-search(moved(game.board, u), 3, -20_000, 20_000), u),
            )
            before = game.board
            game.act(Action("move", best))
            if game.phase == "play" and game.board == chess.Board(LEVELS[level]) != before:
                break  # lost or tied: this player repeats itself
        if game.phase == "review" and game.feedback.tone == "good":
            return
        game.round, game.phase = level + 1, "play"
        if game.round < game.rounds:
            game._begin()
    raise AssertionError("no race won")


def brute(board, known):
    key = board.epd(en_passant="fen")
    if key not in known:
        over = race_over(board)
        if over:
            known[key] = 0 if over == "stuck" else 1 if (over == "white") == board.turn else -1
        else:
            known[key] = max(-brute(moved(board, m.uci()), known) for m in race_moves(board))
    return known[key]


def small(fens):
    return [fen for fen in fens if fen.count("p") <= 3]


def test_the_pawn_solver_agrees_with_brute_force():
    packs = (pawn_races.EASY, pawn_races.HARD_WINNING, pawn_races.HARD_LOSING)
    for fen in [fen for pack in packs for fen in small(pack)[:1]]:
        board = chess.Board(fen)
        assert solve(race_of(board), {}) == brute(board, {})


def test_pawn_race_positions_are_what_they_claim():
    for pack, value in (
        (pawn_races.EASY, 1),
        (pawn_races.HARD_WINNING, 1),
        (pawn_races.HARD_LOSING, -1),
    ):
        assert small(pack)
        assert all(solve(race_of(chess.Board(fen)), {}) == value for fen in small(pack))


def test_hard_pawn_races_mix_winning_and_losing_starts():
    game, kinds = start("pawn-race", 5, "hard"), []
    for index in range(game.rounds):
        game.round = index
        game._begin()
        kinds.append(game.losing)
    assert sorted(kinds) == [False, False, False, True, True]


def test_a_tie_from_a_losing_start_wins_and_any_other_tie_is_replayed():
    for losing, phase in ((True, "review"), (False, "play")):
        game = start("pawn-race", 5, "hard")
        game.losing = losing
        game.board = game.start = chess.Board("8/8/8/p7/8/8/P7/8 w - - 0 1")
        game.act(Action("move", "a2a4"))  # both pawns are blocked
        assert (game.phase, game.hearts) == (phase, 3)


def test_the_rival_replies_at_once_without_locking_the_board():
    for level in ("easy", "medium", "hard"):
        game = start("pawn-race", 2, level)
        shot = game.act(Action("move", game.view().moves[-1]))
        assert shot.frames == ()
        assert shot.view.moves


def test_an_unknown_difficulty_is_refused():
    with pytest.raises(DomainError):
        start("pawn-race", 1, "impossible")
    with pytest.raises(DomainError):
        start("lily-pads", 1, "hard")


def test_every_difficulty_can_be_mashed_through():
    for level in ("easy", "hard"):
        assert mash("pawn-race", 3, level=level) == mash("pawn-race", 3, level=level)


NOTHING = frozenset()
BOTH = frozenset({LOOSE, MATE})


def test_a_hatchling_misses_mate_in_one_and_a_taught_duck_plays_it():
    # Ra8 is mate, but taking the pawn looks nicer to a hatchling.
    board = chess.Board("6k1/5ppp/8/8/R2p4/8/5PPP/6K1 w - - 0 1")
    assert mate_in_one(board).uci() == "a4a8"
    hatchling, taught = think(board, NOTHING, 1), think(board, frozenset({MATE}), 1)
    assert hatchling.move == "a4d4"
    assert any("Ra8#" in text for text in hatchling.missed)
    assert taught.move == "a4a8"
    assert taught.learned


def test_a_hatchling_grabs_a_poisoned_pawn_and_a_taught_duck_does_not():
    board = chess.Board("4k3/8/2p5/3p4/8/8/3Q4/4K3 w - - 0 1")
    hatchling, taught = think(board, NOTHING, 1), think(board, frozenset({LOOSE}), 1)
    assert hatchling.move == "d2d5"
    assert any("queen on d5" in text for text in hatchling.missed)
    assert taught.move != "d2d5"
    assert any("win 9 points" in text for text in taught.learned)


def test_exchanges_count_recaptures():
    board = chess.Board("4k3/8/2p5/3p4/8/8/3R4/4K3 w - - 0 1")
    assert exchange_loss(board, chess.D5) == 0
    board.remove_piece_at(chess.C6)
    assert loosest(board) == (1, chess.D5)


def play_out(first, second, seed, plies=120):
    """1 if `first` (White) mates, -1 if mated, else the material balance's sign."""
    board = chess.Board()
    while board.ply() < plies and not board.is_game_over():
        board.push_uci((first if board.turn else second)(board, seed))
    if board.is_checkmate():
        return -1 if board.turn else 1
    worth = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}
    total = sum(worth[p.piece_type] * (1 if p.color else -1) for p in board.piece_map().values())
    return (total > 0) - (total < 0)


def test_lessons_make_a_duck_stronger_and_a_hatchling_is_not_random():
    def duck(known):
        return lambda board, seed: think(board, known, seed).move

    def rand(board, seed):
        moves = sorted(m.uci() for m in board.legal_moves)
        return moves[draw_below(rng_for(seed, board.ply(), "r"), len(moves))]

    assert sum(play_out(duck(NOTHING), rand, seed) for seed in range(4)) >= 2
    assert sum(play_out(duck(BOTH), duck(NOTHING), seed, 60) for seed in range(3)) >= 2


def test_the_beginner_duck_explains_itself_only_when_asked():
    game = start("beginner-duck", 1, "hatched")
    shot = game.act(Action("move", "e2e4"))
    assert shot.view.notes == []
    assert game.act(Action("hint")).view.notes[0].startswith("Why ")


def test_loose_means_undefended():
    board = chess.Board("4k3/8/2p5/3n4/8/7b/8/4K3 w - - 0 1")
    assert {chess.square_name(s) for s in loose(board)} == {"c6", "h3"}


def test_stuck_or_mated_asks_every_kind():
    seen = set()
    for seed in range(4):
        game = start("stuck-or-mated", seed)
        for index in range(game.rounds):
            game.round = index
            game._begin()
            assert verdict(game.board) == game.answer
            seen.add(game.answer)
    assert seen == {"mate", "stalemate", "check", "free"}


def test_an_exchange_counts_the_recapture():
    board = chess.Board("6k1/8/2p5/3p4/8/8/8/3R2K1 w - - 0 1")
    assert capture_value(board, chess.Move.from_uci("d1d5"))[0] == 1 - 5
    board.remove_piece_at(chess.C6)
    assert capture_value(board, chess.Move.from_uci("d1d5"))[0] == 1


def test_the_clock_ends_the_run_and_stops_while_reading():
    game = FairTrade(1)
    game.act(Action("choice", game.answer), 20_000)
    game.act(Action("next"), 500_000)
    assert game.snapshot().remaining_ms == 40_000
    game.act(Action("timeout"), 1_000)
    assert game.phase == "play"
    assert game.act(Action("timeout"), 40_000).phase == "done"


def test_an_attacked_lily_pad_costs_a_heart_and_sends_the_piece_back():
    for seed in range(20):
        game = LilyPads(seed)
        game.round = 5
        game._begin()
        bad = [m for m in game.view().moves if game._guarded(chess.parse_square(m[2:4]))]
        if bad:
            home = game.at
            game.act(Action("move", bad[0]))
            assert (game.hearts, game.at) == (2, home)
            return
    raise AssertionError("no guarded pad found")


def test_staying_in_check_costs_a_heart():
    game = ThreeWaysOut(3)
    bad = next(m for m in game.view().moves if not game.board.is_legal(chess.Move.from_uci(m)))
    assert game.act(Action("move", bad)).hearts == 2


def test_castling_covers_every_answer():
    answers = set()
    for seed in range(10):
        game = TuckIn(seed)
        for index in range(TuckIn.rounds):
            game.round = index
            game._begin()
            answers.add(game.answer)
    assert answers == {"king", "queen", "both", "none"}


def test_inputs_that_are_not_open_are_refused():
    game = start("crack-the-shell", 1)
    for action in (Action("move", "a1a1"), Action("choice", "x"), Action("next")):
        with pytest.raises(DomainError):
            game.act(action)
    with pytest.raises(DomainError):
        start("nope", 1)


def play_all(fen, ucis):
    board = chess.Board(fen)
    for uci in ucis:
        board.push(board.parse_uci(uci))
    return board


def test_the_content_pack_is_sound():
    for card in content.MATES:
        assert all(play_all(card["fen"], [uci]).is_checkmate() for uci in card["mates"])
    for card in content.FORKS + content.PINS:
        assert card["line"][0] == card["best"]
        play_all(card["fen"], card["line"])
    for card in content.SLIPS:
        play_all(card["fen"], [card["slip"], *card["line"]])
    for card in content.SLIPS + content.SHOWDOWNS:
        assert set(card["key"]) == {m.uci() for m in chess.Board(card["fen"]).legal_moves}
    for pack in (content.MATES, content.FORKS, content.PINS, content.SLIPS, content.SHOWDOWNS):
        fens = [card["fen"] for card in pack]
        assert len(fens) == len(set(fens))


def test_openings_and_rule_cards_are_legal():
    for _, _, line in LINES:
        board = chess.Board()
        for word in line.split():
            board.push_san(word)
        assert board.ply() == 12
    for card in CARDS:
        board = chess.Board()
        for word in card.line.split():
            board.push_san(word)
        for word in (card.good, *card.others):
            board.parse_san(word)
