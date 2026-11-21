"""`duckgambit` command line: the one entry point for the backend (ADR-0014)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from duckgambit.logging_setup import configure_logging
from duckgambit.settings import Settings


def _serve(args: argparse.Namespace, settings: Settings) -> int:
    import uvicorn

    reload = args.reload or settings.env == "dev"
    uvicorn.run(
        "duckgambit.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=reload,
        reload_dirs=[str(_package_dir())] if reload else None,
        log_config=None,
    )
    return 0


def _package_dir() -> object:
    from pathlib import Path

    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="duckgambit", description="Duck Gambit backend")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="run the API server")
    serve.add_argument("--reload", action="store_true", help="restart on code changes")
    serve.set_defaults(handler=_serve)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    return int(args.handler(args, settings))


if __name__ == "__main__":
    sys.exit(main())
