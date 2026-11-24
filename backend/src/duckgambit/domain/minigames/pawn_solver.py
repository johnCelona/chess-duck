"""Who wins a pawns-only race with perfect play? An exact answer, not a guess.

The side to move always runs up the board: after each move the board is turned around,
so one set of rules serves both colours. Squares are bits, a1 the lowest.
"""

from __future__ import annotations

import chess

FULL = 0xFFFF_FFFF_FFFF_FFFF
NOT_A, NOT_H = FULL & ~chess.BB_FILE_A, FULL & ~chess.BB_FILE_H

Race = tuple[int, int, int]  # mine, theirs, the en passant square (0 when none)


def race_of(board: chess.Board) -> Race:
    """The race as its side to move sees it."""
    mine = int(board.occupied_co[board.turn])
    theirs = int(board.occupied_co[not board.turn])
    passing = int(chess.BB_SQUARES[board.ep_square]) if board.ep_square is not None else 0
    if board.turn == chess.WHITE:
        return mine, theirs, passing
    return _turn(mine), _turn(theirs), _turn(passing)


def solve(race: Race, known: dict[Race, int]) -> int:
    """1 when the side to move wins, 0 for a tie, -1 when it loses. `known` is a cache."""
    if race in known:
        return known[race]
    best = -1
    moved = False
    for after in _moves(race):
        moved = True
        arrived = after is None or not after[0]  # or ate the last pawn
        best = 1 if after is None or arrived else max(best, -solve(after, known))
        if best == 1:
            break
    if not moved:
        best = 0  # nobody can get through
    known[race] = best
    return best


def _turn(bits: int) -> int:
    return int.from_bytes(bits.to_bytes(8, "little"), "big")


def _moves(race: Race) -> list[Race | None]:
    """Each position after a move, turned around; None for a pawn that arrives."""
    mine, theirs, passing = race
    found: list[Race | None] = []
    empty = ~(mine | theirs)
    pawns = mine
    while pawns:
        pawn = pawns & -pawns
        pawns ^= pawn
        rest = mine ^ pawn
        targets = []
        if pawn & NOT_A and (pawn << 7) & (theirs | passing):
            targets.append(pawn << 7)
        if pawn & NOT_H and (pawn << 9) & (theirs | passing):
            targets.append(pawn << 9)
        for to in targets:
            eaten = to if to & theirs else to >> 8
            left = theirs & ~eaten
            found.append(None if to >> 56 else (_turn(left), _turn(rest | to), 0))
        one = pawn << 8
        if one & empty:
            found.append(None if one >> 56 else (_turn(theirs), _turn(rest | one), 0))
            two = one << 8
            if pawn & chess.BB_RANK_2 and two & empty:
                found.append((_turn(theirs), _turn(rest | two), _turn(one)))
    # A win in sight ends the search at once, so look at arrivals and captures first.
    found.sort(key=lambda r: 0 if r is None else 1 + r[0].bit_count())
    return found
