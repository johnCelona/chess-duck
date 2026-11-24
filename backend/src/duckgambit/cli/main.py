"""`duckgambit` command line: the one entry point for the backend (ADR-0014)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from duckgambit.logging_setup import configure_logging
from duckgambit.settings import Settings

PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _serve(args: argparse.Namespace, settings: Settings) -> int:
    import uvicorn

    # npm run dev restarts the server itself (scripts/dev.mjs); --reload uses uvicorn's
    # reloader, which on Windows only works when attached to a console window.
    reload = bool(args.reload)
    uvicorn.run(
        "duckgambit.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=reload,
        reload_dirs=[str(PACKAGE_DIR)] if reload else None,
        log_config=None,
        # Event streams stay open for as long as a client listens; do not wait for them.
        timeout_graceful_shutdown=3,
    )
    return 0


def contract_documents() -> dict[str, str]:
    """The committed contract files and their current contents (ADR-0002)."""
    from duckgambit.api.app import create_app
    from duckgambit.api.schemas.events import EVENT_ADAPTER

    app = create_app(Settings(env="prod", _env_file=None))
    events = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://duckgambit.example/contracts/events.schema.json",
        "title": "Duck Gambit event envelope",
        "description": "One event as delivered by /api/v1/events and /api/v1/events/stream.",
        **EVENT_ADAPTER.json_schema(by_alias=True, mode="serialization"),
    }

    def render(document: object) -> str:
        return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    return {"openapi.json": render(app.openapi()), "events.schema.json": render(events)}


def _export_contracts(args: argparse.Namespace, settings: Settings) -> int:
    out = Path(args.out)
    stale = []
    for name, text in contract_documents().items():
        target = out / name
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == text:
            continue
        stale.append(name)
        if not args.check:
            out.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
    if args.check and stale:
        print(f"Contracts are out of date: {', '.join(stale)}. Run `npm run gen`.", file=sys.stderr)
        return 1
    print("Contracts are up to date." if not stale else f"Wrote {', '.join(stale)}.")
    return 0


def _seed(args: argparse.Namespace, settings: Settings) -> int:
    """Create two default ducks so a fresh clone has something to play with."""
    from duckgambit.api.container import build_container
    from duckgambit.domain.duck import default_stats

    spreads = {
        "Sir Quackalot": {**default_stats(), "aggression": 60, "solidity": 20},
        "Bill the Solid": {**default_stats(), "solidity": 60, "aggression": 20},
    }

    async def run() -> list[str]:
        container = build_container(settings)
        try:
            existing = {duck.name for duck in await container.ducks.all()}
            created = []
            for name, stats in spreads.items():
                if name not in existing:
                    await container.ducks.hatch(name, stats=stats)
                    created.append(name)
            return created
        finally:
            await container.shutdown()

    created = asyncio.run(run())
    print(f"Hatched: {', '.join(created)}" if created else "Seed ducks already exist.")
    print(f"Data directory: {settings.resolved_data_dir}")
    return 0


def _answer_keys(args: argparse.Namespace, settings: Settings) -> int:
    """Score every legal move of every puzzle in a pack with a fixed Judge (ADR-0009).

    Skeleton for M4: sequential, no resume. It already works against an installed engine.
    """
    from duckgambit.api.container import build_container
    from duckgambit.domain.puzzles import load_pack
    from duckgambit.services.answer_keys import JudgeConfig, build_answer_keys

    source = Path(args.pack)
    pack = json.loads(source.read_text(encoding="utf-8"))
    load_pack(pack)  # validate before spending engine time

    async def run() -> dict[str, object]:
        container = build_container(settings)
        try:
            judge = JudgeConfig(args.engine, nodes=args.nodes, hash_mb=args.hash_mb)
            return await build_answer_keys(pack, container.pool, judge)
        finally:
            await container.shutdown()

    keyed = asyncio.run(run())
    load_pack(keyed)  # the result must be a valid, fully keyed pack
    target = Path(args.out) if args.out else source
    target.write_text(json.dumps(keyed, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote answer keys for {len(pack['puzzles'])} puzzles to {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="duckgambit", description="Duck Gambit backend")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="run the API server")
    serve.add_argument("--reload", action="store_true", help="restart on code changes")
    serve.set_defaults(handler=_serve)

    export = commands.add_parser(
        "export-contracts", help="write contracts/openapi.json and events.schema.json"
    )
    export.add_argument("--out", default="contracts", help="output folder")
    export.add_argument("--check", action="store_true", help="fail if the files are out of date")
    export.set_defaults(handler=_export_contracts)

    seed = commands.add_parser("seed", help="hatch two default ducks (idempotent)")
    seed.set_defaults(handler=_seed)

    keys = commands.add_parser(
        "answer-keys", help="add Judge answer keys to a puzzle pack (skeleton, see ADR-0009)"
    )
    keys.add_argument("pack", help="path to a pack.json")
    keys.add_argument("--out", help="write here instead of updating the pack in place")
    keys.add_argument("--engine", default="stockfish")
    keys.add_argument("--nodes", type=int, default=2_000_000, help="Judge nodes per legal move")
    keys.add_argument("--hash-mb", type=int, default=64)
    keys.set_defaults(handler=_answer_keys)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    return int(args.handler(args, settings))


if __name__ == "__main__":
    sys.exit(main())
