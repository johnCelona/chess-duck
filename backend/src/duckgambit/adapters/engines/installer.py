"""Engine installer (spec 9.1, ADR-0011).

Download only from the committed manifest over https, cap the size, verify the pinned
sha256, extract member by member into a staging folder, smoke-test the binary, and only
then swap it into place. A failed install never disturbs a working one.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import shutil
import stat
import subprocess
import tarfile
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path, PurePosixPath

import httpx

from duckgambit.adapters.engines.catalog import (
    INSTALL_RECORD,
    EngineCatalog,
    EngineEntry,
    InstalledEngine,
    PlatformAsset,
)
from duckgambit.adapters.system import DataPaths, UnsafePathError, safe_child

log = logging.getLogger(__name__)

MAX_UNPACKED_BYTES = 1024 * 1024 * 1024
MAX_MEMBERS = 20_000
CHUNK = 1024 * 256

Fetch = Callable[[str, Path, int], Awaitable[str]]
SmokeTest = Callable[[list[str], str], None]


class InstallError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def fetch_https(url: str, destination: Path, max_bytes: int) -> str:
    """Stream `url` to `destination`, refusing non-https hops and oversized bodies.

    Returns the sha256 of what was written.
    """
    digest = hashlib.sha256()
    written = 0
    async with httpx.AsyncClient(follow_redirects=False, timeout=60) as client:
        for _ in range(6):
            if not url.startswith("https://"):
                raise InstallError("engine.download_failed", "Download left https")
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = str(response.next_request.url) if response.next_request else ""
                    continue
                if response.status_code != 200:
                    raise InstallError(
                        "engine.download_failed",
                        f"Download failed with HTTP {response.status_code}",
                    )
                with destination.open("wb") as output:
                    async for chunk in response.aiter_bytes(CHUNK):
                        written += len(chunk)
                        if written > max_bytes:
                            raise InstallError(
                                "engine.download_too_large",
                                "Download is larger than the manifest says it should be",
                            )
                        digest.update(chunk)
                        output.write(chunk)
                return digest.hexdigest()
    raise InstallError("engine.download_failed", "Too many redirects")


def _member_target(destination: Path, name: str) -> Path:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in name:
        raise InstallError("engine.unsafe_archive", f"Archive entry escapes the folder: {name!r}")
    try:
        return safe_child(destination, *path.parts)
    except UnsafePathError as exc:
        raise InstallError("engine.unsafe_archive", str(exc)) from exc


def safe_extract(archive: Path, destination: Path, archive_type: str) -> None:
    """Extract regular files and folders only. Links, devices and escapes are rejected."""
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    if archive_type == "zip":
        with zipfile.ZipFile(archive) as opened:
            members = opened.infolist()
            if len(members) > MAX_MEMBERS:
                raise InstallError("engine.unsafe_archive", "Archive has too many entries")
            for info in members:
                # Unix file type bits, when the archiver recorded them (0 means it did not).
                kind = stat.S_IFMT(info.external_attr >> 16)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise InstallError(
                        "engine.unsafe_archive", f"Not a plain file: {info.filename}"
                    )
                target = _member_target(destination, info.filename)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                total += info.file_size
                if total > MAX_UNPACKED_BYTES:
                    raise InstallError("engine.unsafe_archive", "Archive unpacks too large")
                target.parent.mkdir(parents=True, exist_ok=True)
                with opened.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, CHUNK)
    elif archive_type == "tar.gz":
        with tarfile.open(archive, mode="r:gz") as opened:
            for count, member in enumerate(opened):
                if count > MAX_MEMBERS:
                    raise InstallError("engine.unsafe_archive", "Archive has too many entries")
                if not (member.isfile() or member.isdir()):
                    raise InstallError("engine.unsafe_archive", f"Not a plain file: {member.name}")
                target = _member_target(destination, member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                total += member.size
                if total > MAX_UNPACKED_BYTES:
                    raise InstallError("engine.unsafe_archive", "Archive unpacks too large")
                extracted = opened.extractfile(member)
                if extracted is None:
                    raise InstallError("engine.unsafe_archive", f"Unreadable entry: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with extracted, target.open("wb") as output:
                    shutil.copyfileobj(extracted, output, CHUNK)
    else:
        raise InstallError("engine.unsafe_archive", f"Unsupported archive type: {archive_type}")


def smoke_test(command: list[str], expected_name: str, timeout: float = 30.0) -> None:
    """Start the engine, complete the UCI handshake and check it is what the manifest says."""
    try:
        completed = subprocess.run(  # noqa: S603 - the command comes from the manifest install
            command,
            input="uci\nisready\nquit\n",
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(command[-1]).parent,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError("engine.smoke_test_failed", "The engine did not start") from exc
    lines = completed.stdout.splitlines()
    names = [line[len("id name ") :].strip() for line in lines if line.startswith("id name ")]
    if "uciok" not in lines or "readyok" not in lines:
        raise InstallError("engine.smoke_test_failed", "The engine did not complete the handshake")
    if not names or not names[0].startswith(expected_name):
        raise InstallError("engine.smoke_test_failed", "The engine is not the one in the manifest")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


class EngineInstaller:
    def __init__(
        self,
        catalog: EngineCatalog,
        paths: DataPaths,
        fetch: Fetch = fetch_https,
        smoke: SmokeTest = smoke_test,
    ) -> None:
        self._catalog = catalog
        self._paths = paths
        self._fetch = fetch
        self._smoke = smoke
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, engine_id: str) -> asyncio.Lock:
        return self._locks.setdefault(engine_id, asyncio.Lock())

    def is_busy(self, engine_id: str) -> bool:
        return self._lock(engine_id).locked()

    async def install(self, engine_id: str) -> InstalledEngine:
        entry = self._catalog.entry(engine_id)
        if entry is None:
            raise InstallError("engine.unknown", "Unknown engine")
        asset = self._catalog.asset(engine_id)
        if asset is None:
            raise InstallError(
                "engine.unsupported_platform", "No download is available for this platform"
            )
        async with self._lock(engine_id):
            staging = self._paths.tmp / f"install-{entry.id}-{secrets.token_hex(4)}"
            staging.mkdir(parents=True)
            try:
                archive = staging / "download"
                digest = await self._fetch(asset.url, archive, asset.size_bytes)
                if digest.lower() != asset.sha256:
                    raise InstallError(
                        "engine.checksum_mismatch",
                        "The download does not match the pinned checksum",
                    )
                await asyncio.to_thread(
                    self._unpack_verify_and_swap, entry, asset, archive, staging
                )
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        installed = self._catalog.installed(engine_id)
        if installed is None:
            raise InstallError("engine.install_failed", "The engine could not be installed")
        log.info("Installed %s %s", entry.id, entry.version, extra={"engine": entry.id})
        return installed

    def _unpack_verify_and_swap(
        self, entry: EngineEntry, asset: PlatformAsset, archive: Path, staging: Path
    ) -> None:
        unpacked = staging / "unpacked"
        safe_extract(archive, unpacked, asset.archive)
        source = _member_target(unpacked, asset.binary)
        if not source.is_file():
            raise InstallError(
                "engine.install_failed", "The archive does not contain the manifest binary"
            )

        # Keep only the binary and its license files, not the bundled source tree.
        final = staging / "final"
        final.mkdir()
        binary = final / source.name
        shutil.copy2(source, binary)
        for keep in asset.keep:
            kept = _member_target(unpacked, keep)
            if kept.is_file():
                shutil.copy2(kept, final / kept.name)
        if os.name != "nt":
            binary.chmod(binary.stat().st_mode | 0o755)

        self._smoke([str(binary)], entry.uci_name)
        (final / INSTALL_RECORD).write_text(
            json.dumps(
                {
                    "id": entry.id,
                    "version": entry.version,
                    "binary": binary.name,
                    "binarySha256": sha256_of(binary),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        target = self._catalog.install_dir(entry)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            old = staging / "previous"
            target.rename(old)
        final.rename(target)

    async def remove(self, engine_id: str) -> None:
        entry = self._catalog.entry(engine_id)
        if entry is None:
            raise InstallError("engine.unknown", "Unknown engine")
        async with self._lock(engine_id):
            folder = self._paths.engine_dir(entry.id)
            await asyncio.to_thread(shutil.rmtree, folder, True)
