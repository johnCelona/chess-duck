"""A UCI engine process behind the Engine port (ADR-0007).

Engine I/O runs on a private event loop in its own thread. That keeps subprocess
handling independent of the web server's loop (uvicorn's reloader on Windows uses a
loop that cannot start subprocesses) and of whichever client embeds the backend.

Every search is stateless: `ucinewgame` is sent first, so a result depends only on the
request and the binary (ADR-0006). On a timeout, a cancellation or any protocol error
the process is killed; it is never reused in an unknown state.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import threading
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import chess
import chess.engine

from duckgambit.domain.chessutil import board_from
from duckgambit.domain.engine_types import (
    Candidate,
    EngineInfo,
    EngineOption,
    SearchRequest,
    SearchResult,
)
from duckgambit.domain.errors import DomainError
from duckgambit.services.ports import EngineError

log = logging.getLogger(__name__)

START_TIMEOUT_S = 20.0
QUIT_TIMEOUT_S = 3.0


class EngineLoop:
    """One background event loop shared by all engine processes."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._guard = threading.Lock()

    def _ensure(self) -> asyncio.AbstractEventLoop:
        with self._guard:
            if self._loop is None:
                if sys.platform == "win32":
                    loop: asyncio.AbstractEventLoop = asyncio.ProactorEventLoop()
                else:
                    loop = asyncio.new_event_loop()
                thread = threading.Thread(target=loop.run_forever, name="engine-io", daemon=True)
                thread.start()
                self._loop, self._thread = loop, thread
            return self._loop

    async def run[T](self, coroutine: Coroutine[Any, Any, T]) -> T:
        """Run `coroutine` on the engine loop. Cancelling the caller cancels it there too."""
        future = asyncio.run_coroutine_threadsafe(coroutine, self._ensure())
        return await asyncio.wrap_future(future)

    def stop(self) -> None:
        with self._guard:
            loop, thread = self._loop, self._thread
            self._loop = self._thread = None
        if loop is None or thread is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        if not loop.is_running():
            loop.close()


def default_deadline(request: SearchRequest) -> float:
    """Generous wall-clock allowance: a safety net, never part of a result."""
    if request.nodes is not None:
        return 10.0 + request.nodes / 20_000
    return 120.0


class UciEngine:
    def __init__(
        self,
        command: list[str],
        cwd: Path,
        io: EngineLoop,
        options: dict[str, str | int | bool],
        max_nodes: int,
        deadline: Any = default_deadline,
    ) -> None:
        self._command = command
        self._cwd = cwd
        self._io = io
        self._options = options
        self._max_nodes = max_nodes
        self._deadline = deadline
        self._transport: asyncio.SubprocessTransport | None = None
        self._protocol: chess.engine.UciProtocol | None = None
        self.alive = False

    async def start(self) -> None:
        try:
            await self._io.run(asyncio.wait_for(self._start(), START_TIMEOUT_S))
        except (TimeoutError, OSError, chess.engine.EngineError) as exc:
            await self._kill()
            raise EngineError("engine.start_failed", "The engine did not start") from exc
        self.alive = True

    async def _start(self) -> None:
        self._transport, self._protocol = await chess.engine.popen_uci(
            self._command, cwd=str(self._cwd)
        )
        advertised = self._protocol.options
        wanted = {name: value for name, value in self._options.items() if name in advertised}
        if wanted:
            await self._protocol.configure(wanted)

    async def describe(self) -> EngineInfo:
        protocol = self._require()
        options = tuple(
            EngineOption(
                name=option.name,
                type=option.type,
                default=option.default,
                min=option.min,
                max=option.max,
                choices=tuple(option.var or ()),
            )
            for option in protocol.options.values()
        )
        return EngineInfo(str(protocol.id.get("name", "unknown")), options)

    def _require(self) -> chess.engine.UciProtocol:
        if not self.alive or self._protocol is None:
            raise EngineError("engine.not_running", "The engine is not running")
        return self._protocol

    async def search(self, request: SearchRequest) -> SearchResult:
        protocol = self._require()
        try:
            request.validate(self._max_nodes)
            board = board_from(request.initial_fen, request.moves)
        except DomainError as exc:
            raise EngineError(exc.code, exc.message) from exc
        try:
            return await self._io.run(
                asyncio.wait_for(self._search(protocol, board, request), self._deadline(request))
            )
        except asyncio.CancelledError:
            await asyncio.shield(self._kill())
            raise
        except TimeoutError as exc:
            await self._kill()
            raise EngineError("engine.timeout", "The engine took too long and was stopped") from exc
        except (chess.engine.EngineError, OSError) as exc:
            await self._kill()
            log.warning("Engine failed: %s", type(exc).__name__)
            raise EngineError("engine.failed", "The engine stopped unexpectedly") from exc

    @staticmethod
    async def _search(
        protocol: chess.engine.UciProtocol, board: chess.Board, request: SearchRequest
    ) -> SearchResult:
        limit = chess.engine.Limit(nodes=request.nodes, depth=request.depth)
        by_depth: dict[int, dict[int, chess.engine.InfoDict]] = {}
        nodes = 0
        # A new `game` object makes python-chess send ucinewgame + isready first.
        analysis = await protocol.analysis(
            board, limit, multipv=request.multipv, game=object(), info=chess.engine.INFO_ALL
        )
        with analysis:
            async for info in analysis:
                nodes = max(nodes, int(info.get("nodes", 0)))
                if "pv" not in info or "score" not in info or not info["pv"]:
                    continue
                if info.get("lowerbound") or info.get("upperbound"):
                    continue
                line = int(info.get("multipv", 1))
                by_depth.setdefault(int(info.get("depth", 0)), {})[line] = info

        expected = min(request.multipv, board.legal_moves.count())
        complete = [depth for depth, lines in by_depth.items() if len(lines) >= expected]
        if not complete:
            raise chess.engine.EngineError("engine returned no complete set of lines")
        # Only the deepest depth finished for every line: a search cut off mid-iteration
        # reports deeper lines for some moves only, and mixing depths is not comparable.
        depth = max(complete)
        candidates = []
        for line in sorted(by_depth[depth])[:expected]:
            info = by_depth[depth][line]
            score = info["score"].pov(board.turn)
            wdl = info.get("wdl")
            candidates.append(
                Candidate(
                    move=info["pv"][0].uci(),
                    cp=None if score.is_mate() else score.score(),
                    mate=score.mate(),
                    wdl=tuple(wdl.pov(board.turn)) if wdl is not None else None,
                    depth=depth,
                    pv=tuple(move.uci() for move in info["pv"]),
                )
            )
        return SearchResult(tuple(candidates), nodes=nodes, depth=depth)

    async def _kill(self) -> None:
        self.alive = False
        transport, self._transport, self._protocol = self._transport, None, None
        if transport is None:
            return

        async def kill() -> None:
            with contextlib.suppress(ProcessLookupError, OSError):
                transport.kill()
            with contextlib.suppress(Exception):
                transport.close()

        with contextlib.suppress(Exception):
            await self._io.run(kill())

    async def close(self) -> None:
        """Ask the engine to quit; kill it if it does not."""
        protocol = self._protocol
        if self.alive and protocol is not None:
            with contextlib.suppress(Exception):
                await self._io.run(asyncio.wait_for(protocol.quit(), QUIT_TIMEOUT_S))
        await self._kill()
