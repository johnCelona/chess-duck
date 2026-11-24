"""Contracts for Puzzle Arena data and the Lichess port, both built in later milestones."""

import copy
import json
from pathlib import Path

import pytest

from duckgambit.adapters.engines.fake import FakeEnginePool
from duckgambit.adapters.lichess.fake import FAKE_TOKEN, FakeLichess, MemorySecretStore
from duckgambit.domain.errors import DomainError
from duckgambit.domain.puzzles import (
    agreement,
    best_entries,
    load_pack,
    original_ideas,
    score_showdown,
)
from duckgambit.services.answer_keys import JudgeConfig, build_answer_keys
from duckgambit.services.lichess import GameQuery, LichessError

pytestmark = pytest.mark.anyio

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_pack.json"


def sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def keyed_fork() -> dict:
    """The fork puzzle with a hand-written key: Nc7+ wins the queen, Nb6 holds, Nf6+ loses."""
    pack = sample()
    puzzle = pack["puzzles"][1]
    board_moves = load_pack(pack).puzzles[1]
    import chess

    legal = [move.uci() for move in chess.Board(board_moves.fen).legal_moves]
    key = {move: {"wdl": [100, 800, 100], "cp": 0, "mate": None} for move in legal}
    key["d5c7"] = {"wdl": [960, 40, 0], "cp": 520, "mate": None}
    key["d5b6"] = {"wdl": [910, 90, 0], "cp": 400, "mate": None}
    key["d5f6"] = {"wdl": [0, 100, 900], "cp": -300, "mate": None}
    puzzle["answerKey"] = key
    return pack


# ----- puzzle packs and scoring ------------------------------------------------------


def test_the_sample_pack_loads_and_is_not_keyed_yet():
    pack = load_pack(sample())

    assert [p.id for p in pack.puzzles] == ["sample:back-rank", "sample:fork"]
    assert not pack.puzzles[0].keyed


async def test_answer_keys_cover_every_legal_move_and_see_mate_in_one():
    keyed = await build_answer_keys(sample(), FakeEnginePool(), JudgeConfig("fake", nodes=1000))

    pack = load_pack(keyed)
    back_rank = pack.puzzles[0]
    assert back_rank.keyed
    assert [entry.move for entry in best_entries(back_rank)] == ["d1d8"]
    assert back_rank.answer_key["d1d8"].mate == 1
    assert keyed["judge"]["limit"] == {"type": "nodes", "value": 1000}


def test_showdown_points_follow_the_spec():
    fork = load_pack(keyed_fork()).puzzles[1]

    assert score_showdown(["d5c7", "d5b6"], fork).points == 3  # best move first
    assert score_showdown(["d5b6", "d5c7"], fork).points == 2  # best move listed, not first
    assert score_showdown(["d5b6", "g1f1"], fork).points == 1  # no best move, but still winning
    assert score_showdown(["g1f1", "g1h1"], fork).points == -1  # top pick drops 200+ centipawns
    assert score_showdown(["d5f6"], fork).traps == 1
    assert score_showdown([], fork).points == 0


def test_idea_stats_compare_ducks():
    fork = load_pack(keyed_fork()).puzzles[1]

    assert agreement(["d5c7", "d5b6", "g1f1"], ["d5b6", "g1f1", "h2h3"]) == 2
    assert original_ideas(["d5c7", "g1f1"], [["d5b6", "g1f1"]], fork) == ["d5c7"]


def test_scoring_an_unkeyed_puzzle_is_an_error():
    with pytest.raises(DomainError) as error:
        score_showdown(["d1d8"], load_pack(sample()).puzzles[0])

    assert error.value.code == "puzzle.no_answer_key"


@pytest.mark.parametrize(
    "damage",
    [
        lambda pack: pack.update(format="nope"),
        lambda pack: pack.update(schemaVersion=2),
        lambda pack: pack.update(puzzles=[]),
        lambda pack: pack["puzzles"][0].update(fen="not a fen"),
        lambda pack: pack["puzzles"][1]["answerKey"].pop("d5c7"),
        lambda pack: pack["puzzles"][1]["answerKey"]["d5c7"].update(wdl=[1, 2, 3]),
        lambda pack: pack["puzzles"][1]["answerKey"].update(a1a8={"wdl": [0, 1000, 0]}),
    ],
)
def test_malformed_packs_are_rejected(damage):
    pack = copy.deepcopy(keyed_fork())
    damage(pack)

    with pytest.raises(DomainError):
        load_pack(pack)


# ----- Lichess port (fake adapter only) ----------------------------------------------


async def test_linking_identifies_the_player_without_any_scope():
    lichess = FakeLichess(username="DuckTrainer")

    url = lichess.authorization_url("state123", "challenge", "http://127.0.0.1:8000/cb")
    token = await lichess.exchange_code("fake-code", "verifier", "http://127.0.0.1:8000/cb")
    account = await lichess.account(token)

    assert "code_challenge_method=S256" in url
    assert "scope" not in url
    assert (account.id, account.username) == ("ducktrainer", "DuckTrainer")


async def test_public_games_export_without_a_token():
    lichess = FakeLichess(games=("pgn one", "pgn two", "pgn three"))

    games = [pgn async for pgn in lichess.export_games("duck_trainer", GameQuery(max_games=2))]

    assert games == ["pgn one", "pgn two"]


async def test_importing_a_game_returns_its_url_and_identical_games_are_not_duplicated():
    lichess = FakeLichess()

    first = await lichess.import_game("1. e4 e5 *", FAKE_TOKEN)
    again = await lichess.import_game("1. e4 e5 *", FAKE_TOKEN)

    assert first == again
    assert first.url.endswith(first.id)
    assert len(lichess.imported) == 1


async def test_a_revoked_or_wrong_token_is_reported_as_an_expired_link():
    lichess = FakeLichess()
    await lichess.revoke(FAKE_TOKEN)

    for token in (FAKE_TOKEN, "something-else"):
        with pytest.raises(LichessError) as error:
            await lichess.account(token)
        assert error.value.code == "lichess.unauthorised"


def test_the_secret_store_keeps_tokens_out_of_everything_else():
    secrets = MemorySecretStore()

    secrets.set("lichess", FAKE_TOKEN)
    assert secrets.get("lichess") == FAKE_TOKEN
    secrets.delete("lichess")
    assert secrets.get("lichess") is None
