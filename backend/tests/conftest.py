"""Shared fixtures. No test here needs a real Stockfish."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from duckgambit.adapters.sqlite.store import SqliteStore

NOW = "2026-11-21T12:00:00Z"


class FixedClock:
    """A clock that advances one second per reading, so timestamps are stable in tests."""

    def __init__(self) -> None:
        self._moment = datetime(2026, 11, 21, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        self._moment += timedelta(seconds=1)
        return self._moment


class CountingIds:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def new(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}_{self._counts[prefix]:04d}"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteStore]:
    sqlite_store = SqliteStore(tmp_path / "test.db")
    sqlite_store.migrate(NOW)
    sqlite_store.profiles.ensure_default(NOW)
    yield sqlite_store
    sqlite_store.close()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def ids() -> CountingIds:
    return CountingIds()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="rewrite golden files instead of comparing against them",
    )
