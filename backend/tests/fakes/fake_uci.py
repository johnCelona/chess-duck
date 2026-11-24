"""A tiny UCI engine for adapter tests. It scores moves like the in-process fake engine.

Behaviour switches (environment):
  FAKE_UCI_MODE = normal | hang | crash | no-handshake | partial-depth | reorder | wrong-name
  FAKE_UCI_LOG  = path of a file that receives every command line

Run as: python fake_uci.py
"""

from __future__ import annotations

import os
import sys
import time

import chess

from duckgambit.adapters.engines.fake import fake_candidates

MODE = os.environ.get("FAKE_UCI_MODE", "normal")
LOG = os.environ.get("FAKE_UCI_LOG")


def say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def record(line: str) -> None:
    if LOG:
        with open(LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def info_line(depth: int, index: int, candidate, nodes: int) -> str:
    score = f"mate {candidate.mate}" if candidate.mate is not None else f"cp {candidate.cp}"
    wdl = " ".join(str(value) for value in candidate.wdl)
    return (
        f"info depth {depth} seldepth {depth} multipv {index} score {score} wdl {wdl} "
        f"nodes {nodes} nps 1000 time 1 pv {candidate.move}"
    )


def main() -> None:
    board = chess.Board()
    multipv = 1
    for raw in sys.stdin:
        line = raw.strip()
        record(line)
        words = line.split()
        if not words:
            continue
        if words[0] == "uci":
            if MODE == "no-handshake":
                time.sleep(3600)
            say("id name " + ("Impostor 1" if MODE == "wrong-name" else "Fake UCI 1"))
            say("id author Duck Gambit tests")
            say("option name Threads type spin default 1 min 1 max 4")
            say("option name Hash type spin default 16 min 1 max 1024")
            say("option name MultiPV type spin default 1 min 1 max 10")
            say("option name UCI_ShowWDL type check default false")
            say("option name Debug Log File type string default <empty>")
            say("option name SyzygyPath type string default <empty>")
            say("uciok")
        elif words[0] == "isready":
            say("readyok")
        elif words[0] == "setoption" and "MultiPV" in words:
            multipv = int(words[-1])
        elif words[0] == "position":
            moves = words[words.index("moves") + 1 :] if "moves" in words else []
            if words[1] == "startpos":
                board = chess.Board()
            else:
                end = words.index("moves") if "moves" in words else len(words)
                board = chess.Board(" ".join(words[2:end]))
            for move in moves:
                board.push_uci(move)
        elif words[0] == "go":
            if MODE == "crash":
                sys.exit(3)
            if MODE == "hang":
                time.sleep(3600)
            nodes = int(words[words.index("nodes") + 1]) if "nodes" in words else 1000
            candidates = fake_candidates(board, multipv)
            for index, candidate in enumerate(candidates, start=1):
                say(info_line(1, index, candidate, nodes + 17))
            if MODE == "partial-depth" and len(candidates) > 1:
                # A deeper iteration that only finished its first line, with a different move.
                say(info_line(2, 1, candidates[-1], nodes + 17))
            if MODE == "reorder" and len(candidates) > 2:
                # What Stockfish does when cut off mid-iteration: the third move overtakes the
                # second at depth 2, and the displaced second move is reprinted on line 3 under
                # the previous depth. Reading by line number would list the second move twice.
                say(info_line(2, 1, candidates[0], nodes + 17))
                say(info_line(2, 2, candidates[2], nodes + 17))
                say(info_line(1, 3, candidates[1], nodes + 17))
            say(f"bestmove {candidates[0].move}" if candidates else "bestmove 0000")
        elif words[0] == "quit":
            return


if __name__ == "__main__":
    main()
