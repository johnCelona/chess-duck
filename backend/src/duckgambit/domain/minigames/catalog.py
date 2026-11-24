"""Every minigame test, in the order the page lists them."""

from __future__ import annotations

from duckgambit.domain.errors import DomainError
from duckgambit.domain.minigames.base import Minigame
from duckgambit.domain.minigames.candidate_showdown import CandidateShowdown
from duckgambit.domain.minigames.crack_the_shell import CrackTheShell
from duckgambit.domain.minigames.fair_trade import FairTrade
from duckgambit.domain.minigames.goose_chase import GooseChase
from duckgambit.domain.minigames.lily_pads import LilyPads
from duckgambit.domain.minigames.oops_pile import OopsPile
from duckgambit.domain.minigames.quack_back import QuackBack
from duckgambit.domain.minigames.rules_of_the_pond import RulesOfThePond
from duckgambit.domain.minigames.tactics_dojo import TacticsDojo
from duckgambit.domain.minigames.three_ways_out import ThreeWaysOut
from duckgambit.domain.minigames.tuck_in import TuckIn

MINIGAMES: tuple[type[Minigame], ...] = (
    LilyPads,
    FairTrade,
    ThreeWaysOut,
    CrackTheShell,
    TuckIn,
    RulesOfThePond,
    QuackBack,
    TacticsDojo,
    GooseChase,
    OopsPile,
    CandidateShowdown,
)


def start(kind: str, seed: int) -> Minigame:
    for game in MINIGAMES:
        if game.info.id == kind:
            return game(seed)
    raise DomainError("minigame.unknown", "No such minigame")
