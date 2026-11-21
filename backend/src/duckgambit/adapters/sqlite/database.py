"""SQLite connection handling and forward-only migrations (ADR-0004)."""

from __future__ import annotations

import logging
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from importlib import resources
from pathlib import Path

from duckgambit.adapters.sqlite.data_steps import DATA_STEPS

log = logging.getLogger(__name__)

_current: ContextVar[sqlite3.Connection | None] = ContextVar("duckgambit_sqlite_tx", default=None)


class SchemaTooNewError(RuntimeError):
    pass


def available_migrations() -> list[tuple[int, str, str]]:
    """(version, name, sql) for every packaged migration, in order."""
    found = []
    for entry in resources.files(__package__).joinpath("migrations").iterdir():
        if entry.name.endswith(".sql"):
            number, _, name = entry.name[:-4].partition("_")
            found.append((int(number), name, entry.read_text(encoding="utf-8")))
    return sorted(found)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._keeper: sqlite3.Connection | None = None

    def hold_open(self) -> None:
        """Keep one connection open for the life of the process.

        Transactions open short-lived connections. Without this, each one would be the
        last connection to close, and SQLite would checkpoint and delete the WAL file
        every time, which costs several milliseconds per transaction.
        """
        if self._keeper is None:
            self._keeper = sqlite3.connect(self.path, check_same_thread=False)

    def close(self) -> None:
        if self._keeper is not None:
            self._keeper.close()
            self._keeper = None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        # With WAL, NORMAL cannot corrupt the file; a power cut may lose the last commits,
        # which a deterministic match simply replays on resume.
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """A write transaction. Nested use joins the outer transaction."""
        outer = _current.get()
        if outer is not None:
            yield outer
            return
        connection = self._connect()
        token = _current.set(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            _current.reset(token)
            connection.close()

    def migrate(self, applied_at: str, target: int | None = None) -> list[int]:
        """Apply pending migrations. Backs the file up first. Returns the versions applied.

        `target` stops at that version instead of the latest; tests use it to build a
        database as an older build would have left it. A migration's data step, if it has
        one (`data_steps.DATA_STEPS`), runs after its SQL in the same transaction.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        migrations = available_migrations()
        latest = migrations[-1][0]
        if target is not None:
            migrations = [m for m in migrations if m[0] <= target]
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()
        if current > latest:
            raise SchemaTooNewError(
                f"Database schema {current} is newer than this build supports ({latest})"
            )
        pending = [m for m in migrations if m[0] > current]
        if not pending:
            return []
        if current > 0:
            backup = self.path.with_name(f"{self.path.name}.bak-v{current}")
            shutil.copy2(self.path, backup)
            log.info("Backed up database to %s before migrating", backup.name)

        connection = self._connect()
        try:
            for version, name, sql in pending:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _statements(sql):
                        connection.execute(statement)
                    step = DATA_STEPS.get(version)
                    if step is not None:
                        step(connection)
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS schema_migrations ("
                        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
                    )
                    connection.execute(
                        "INSERT INTO schema_migrations (version, name, applied_at)"
                        " VALUES (?, ?, ?)",
                        (version, name, applied_at),
                    )
                    connection.execute(f"PRAGMA user_version = {int(version)}")
                    connection.execute("COMMIT")
                except BaseException:
                    connection.execute("ROLLBACK")
                    raise
                log.info("Applied migration %04d_%s", version, name)
        finally:
            connection.close()
        return [version for version, _, _ in pending]

    def schema_version(self) -> int:
        connection = self._connect()
        try:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()


def _statements(sql: str) -> list[str]:
    """Split a migration into statements. Migrations must not put ';' inside strings."""
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    cleaned = "\n".join(line.split("--")[0] for line in lines)
    return [part.strip() for part in cleaned.split(";") if part.strip()]
