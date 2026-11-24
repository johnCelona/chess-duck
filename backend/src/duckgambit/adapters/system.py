"""Real clock, id generator and data-directory paths."""

from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidIds:
    def new(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class UnsafePathError(ValueError):
    pass


def safe_child(root: Path, *parts: str) -> Path:
    """Join `parts` under `root` and refuse anything that would land outside it (ADR-0011)."""
    # Windows reads a backslash as a separator and other systems as part of a name: refuse it
    # everywhere, so a path means the same thing on every computer.
    if any("\\" in part for part in parts):
        raise UnsafePathError("Path contains a backslash")
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*parts).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise UnsafePathError(f"Path escapes {resolved_root}")
    return candidate


class DataPaths:
    """Every mutable file lives under one root, never in the source tree (ADR-0014)."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    @property
    def database(self) -> Path:
        return self.root / "duckgambit.db"

    @property
    def engines(self) -> Path:
        return self.root / "engines"

    @property
    def tmp(self) -> Path:
        return self.root / "tmp"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def prepare(self) -> None:
        """Create the layout and empty the staging area left by a previous run."""
        shutil.rmtree(self.tmp, ignore_errors=True)
        for folder in (self.root, self.engines, self.tmp, self.logs):
            folder.mkdir(parents=True, exist_ok=True)

    def engine_dir(self, engine_id: str, version: str | None = None) -> Path:
        return safe_child(self.engines, engine_id, *([version] if version else []))
