import asyncio
import chess
import chess.engine


class UciEngine:
    def __init__(self, binary: str):
        self.binary = binary
        self.engine: chess.engine.SimpleEngine | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self.engine is not None:
                return
            loop = asyncio.get_running_loop()
            self.engine = await asyncio.wait_for(
                loop.run_in_executor(
                    None, chess.engine.SimpleEngine.popen_uci, self.binary
                ),
                timeout=15,
            )
            if "UCI_ShowWDL" in self.engine.options:
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None, self.engine.configure, {"UCI_ShowWDL": "true"}
                    ),
                    timeout=5,
                )

    async def stop(self) -> None:
        async with self._lock:
            if self.engine is None:
                return
            engine, self.engine = self.engine, None
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, engine.quit), timeout=10
            )

    async def options(self) -> dict[str, dict[str, object]]:
        if self.engine is None:
            await self.start()
        return {
            name: {
                "name": name,
                "type": option.type,
                "default": option.default,
                "min": option.min,
                "max": option.max,
                "choices": list(option.var) if option.var else None,
            }
            for name, option in self.engine.options.items()
        }

    async def configure(self, values: dict[str, object]) -> None:
        if self.engine is None:
            await self.start()
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(
            loop.run_in_executor(None, self.engine.configure, values),
            timeout=5,
        )

    async def analyse(
        self,
        fen: str,
        limit: chess.engine.Limit,
        multipv: int,
    ) -> list[dict[str, object]]:
        if self.engine is None:
            await self.start()

        board = chess.Board(fen)
        loop = asyncio.get_running_loop()
        infos = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: self.engine.analyse(board, limit, multipv=multipv),
            ),
            timeout=30,
        )
        candidates: list[dict[str, object]] = []
        for info in infos:
            pv = info.get("pv", [])
            score = info.get("score")
            candidates.append(
                {
                    "move_uci": pv[0].uci() if pv else None,
                    "score_cp": score.pov(board.turn).score() if score and score.is_mate() is False else None,
                    "mate": score.pov(board.turn).mate() if score and score.is_mate() else None,
                    "wdl": list(info["wdl"].pov(board.turn)) if info.get("wdl") else None,
                    "depth": info.get("depth"),
                    "nodes": info.get("nodes"),
                    "pv": [move.uci() for move in pv],
                }
            )
        return candidates
