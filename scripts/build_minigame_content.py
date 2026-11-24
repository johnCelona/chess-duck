"""Build backend/src/duckgambit/domain/minigames/content.py from our own engine games.

    uv run --project backend python scripts/build_minigame_content.py <stockfish binary>

A weak, seeded Stockfish plays itself; positions worth a minigame are kept with an
answer key (every legal move scored). The output is committed, so neither the game nor
CI needs an engine. All positions are normalised to White to move.
"""

import random
import sys
from pathlib import Path

import chess
import chess.engine

OUT = Path("backend/src/duckgambit/domain/minigames/content.py")
WANT = {"MATES": 24, "FORKS": 20, "PINS": 10, "SLIPS": 20, "SHOWDOWNS": 16}
VALUE = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 99}
rng = random.Random(20261123)
found = {name: [] for name in WANT}


def cp(score):
    return max(-2000, min(2000, score.pov(chess.WHITE).score(mate_score=2000)))


def key_for(engine, board, nodes=600_000):
    n = board.legal_moves.count()
    infos = engine.analyse(
        board, chess.engine.Limit(nodes=nodes), multipv=n, game=object()
    )
    return {
        i["pv"][0].uci(): (cp(i["score"]), [m.uci() for m in i["pv"][:6]])
        for i in infos
    }


def flipped(board, *moves):
    if board.turn:
        return (board.copy(stack=False), *moves)
    f = [
        chess.Move(
            chess.square_mirror(m.from_square),
            chess.square_mirror(m.to_square),
            m.promotion,
        )
        for m in moves
    ]
    return (board.mirror(), *f)


def is_fork(board, move):
    after = board.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        return False
    mover = after.piece_type_at(move.to_square)
    hits = 0
    for sq in after.attacks(move.to_square):
        p = after.piece_at(sq)
        if p and p.color == chess.BLACK and p.piece_type != chess.PAWN:
            if VALUE[p.piece_type] > VALUE[mover] or not after.is_attacked_by(
                chess.BLACK, sq
            ):
                hits += 1
    return hits >= 2


def is_pin(board, move):
    after = board.copy(stack=False)
    after.push(move)
    if after.is_check():
        return False
    for sq in chess.SquareSet(after.occupied_co[chess.BLACK]):
        p = after.piece_at(sq)
        if p.piece_type in (chess.PAWN, chess.KING) or board.is_pinned(chess.BLACK, sq):
            continue
        if after.is_pinned(chess.BLACK, sq) and sq in after.attacks(move.to_square):
            return True
    return False


def scan(engine, board, quick):
    """quick: candidates best first from the mover's side, of `board`."""
    (w,) = flipped(board)
    mates = [m for m in w.legal_moves if _mates(w, m)]
    if mates and len(mates) <= 2 and len(found["MATES"]) < WANT["MATES"]:
        found["MATES"].append({"fen": w.fen(), "mates": [m.uci() for m in mates]})
        return
    if len(quick) < 3 or mates:
        return
    best, second = quick[0], quick[1]
    if best[1] >= 150 and best[1] - second[1] >= 150 and best[1] < 1900:
        _, m = flipped(board, best[0])
        name = "FORKS" if is_fork(w, m) else "PINS" if is_pin(w, m) else None
        if name and len(found[name]) < WANT[name]:
            key = key_for(engine, w)
            top = sorted(key, key=lambda u: -key[u][0])
            if top[0] == m.uci() and key[top[0]][0] - key[top[1]][0] >= 130:
                found[name].append(
                    {"fen": w.fen(), "best": top[0], "line": key[top[0]][1]}
                )
                return
    if (
        len(found["SHOWDOWNS"]) < WANT["SHOWDOWNS"]
        and 10 <= board.ply() <= 40
        and abs(best[1]) < 120
        and not board.is_check()
        and board.legal_moves.count() >= 20
        and rng.random() < 0.06
    ):
        key = key_for(engine, w)
        found["SHOWDOWNS"].append(
            {"fen": w.fen(), "key": {u: key[u][0] for u in sorted(key)}}
        )


def _mates(b, m):
    b.push(m)
    r = b.is_checkmate()
    b.pop()
    return r


def slip(engine, board, move):
    """A losing move was just chosen in a level position: keep it with its punishment."""
    if len(found["SLIPS"]) >= WANT["SLIPS"]:
        return
    w, m = flipped(board, move)
    key = key_for(engine, w)
    best = max(v[0] for v in key.values())
    if not (-150 <= best <= 250 and best - key[m.uci()][0] >= 250):
        return
    good = [u for u in key if best - key[u][0] <= 60]
    if not 1 <= len(good) <= 12:
        return
    after = w.copy(stack=False)
    for u in key[m.uci()][1][:4]:
        after.push_uci(u)
    diff = sum(
        VALUE[p.piece_type] * (1 if p.color else -1) for p in after.piece_map().values()
    )
    diff0 = sum(
        VALUE[p.piece_type] * (1 if p.color else -1) for p in w.piece_map().values()
    )
    if not after.is_checkmate() and diff0 - diff < 2:
        return  # the punishment must be visible
    found["SLIPS"].append(
        {
            "fen": w.fen(),
            "slip": m.uci(),
            "line": key[m.uci()][1][1:4],
            "lost": diff0 - diff,
            "key": {u: key[u][0] for u in sorted(key)},
        }
    )


def main():
    engine = chess.engine.SimpleEngine.popen_uci(sys.argv[1])
    engine.configure({"Threads": 1, "Hash": 32})
    games = 0
    while any(len(found[n]) < WANT[n] for n in WANT) and games < 400:
        games += 1
        before = {n: len(found[n]) for n in WANT}
        board = chess.Board()
        while not board.is_game_over() and board.ply() < 90:
            # At most one of each kind per game keeps the pack varied.
            infos = engine.analyse(
                board, chess.engine.Limit(nodes=6000), multipv=6, game=object()
            )
            quick = [
                (i["pv"][0], i["score"].relative.score(mate_score=2000)) for i in infos
            ]
            if board.ply() >= 8:
                caps = {n: WANT[n] for n in WANT}
                for n in WANT:
                    if len(found[n]) > before[n]:
                        WANT[n] = len(found[n])
                scan(engine, board, quick)
                WANT.update(caps)
            if board.ply() >= 8 and rng.random() < 0.10:
                move = rng.choice(list(board.legal_moves))
            else:
                move = rng.choice(quick[:4])[0] if rng.random() < 0.5 else quick[0][0]
            if (
                board.ply() >= 8
                and len(found["SLIPS"]) == before["SLIPS"]
                and abs(quick[0][1]) < 200
                and all(move != m or quick[0][1] - s > 200 for m, s in quick)
            ):
                slip(engine, board, move)
            board.push(move)
            if abs(quick[0][1]) > 1500 and len(found["MATES"]) > before["MATES"]:
                break
        print(games, {n: len(found[n]) for n in WANT}, flush=True)
    engine.quit()
    lines = [
        '"""Generated by scripts/build_minigame_content.py. Do not edit by hand."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
    ]
    for n in WANT:
        lines += [f"{n}: list[dict[str, Any]] = {found[n]!r}", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")


main()
