"""The engine manifest and what is installed (spec 9.1).

The manifest is committed, code-reviewed configuration: the only source of download
URLs and checksums. Installed engines live in the data directory.
"""

from __future__ import annotations

import json
import platform
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from duckgambit.adapters.system import DataPaths

ENGINE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
INSTALL_RECORD = "installed.json"


@dataclass(frozen=True)
class PlatformAsset:
    url: str
    sha256: str
    size_bytes: int
    archive: str  # "zip" | "tar.gz"
    binary: str  # path of the executable inside the archive
    keep: tuple[str, ...]  # license files to keep beside the binary


@dataclass(frozen=True)
class EngineEntry:
    id: str
    name: str
    version: str
    license: str
    homepage: str
    source_url: str
    uci_name: str  # what the engine must report as `id name`; checked by the smoke test
    platforms: dict[str, PlatformAsset]


@dataclass(frozen=True)
class InstalledEngine:
    id: str
    version: str
    binary: Path
    binary_sha256: str

    @property
    def command(self) -> list[str]:
        return [str(self.binary)]


def platform_key() -> str:
    system = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(
        platform.system(), platform.system().lower()
    )
    if system == "macos":
        return "macos-universal"
    machine = platform.machine().lower()
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}.get(
        machine, machine
    )
    return f"{system}-{arch}"


def load_manifest(text: str | None = None) -> list[EngineEntry]:
    if text is None:
        text = resources.files(__package__).joinpath("manifest.json").read_text(encoding="utf-8")
    entries = []
    for raw in json.loads(text)["engines"]:
        if not ENGINE_ID.match(raw["id"]):
            raise ValueError(f"Invalid engine id in manifest: {raw['id']!r}")
        platforms = {}
        for key, asset in raw["platforms"].items():
            if not asset["url"].startswith("https://"):
                raise ValueError(f"Manifest URL for {raw['id']} ({key}) is not https")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", asset["sha256"]):
                raise ValueError(f"Manifest sha256 for {raw['id']} ({key}) is malformed")
            platforms[key] = PlatformAsset(
                url=asset["url"],
                sha256=asset["sha256"].lower(),
                size_bytes=int(asset["sizeBytes"]),
                archive=asset["archive"],
                binary=asset["binary"],
                keep=tuple(asset.get("keep", ())),
            )
        entries.append(
            EngineEntry(
                id=raw["id"],
                name=raw["name"],
                version=raw["version"],
                license=raw["license"],
                homepage=raw["homepage"],
                source_url=raw["sourceUrl"],
                uci_name=raw["uciName"],
                platforms=platforms,
            )
        )
    return entries


class EngineCatalog:
    def __init__(self, paths: DataPaths, entries: list[EngineEntry] | None = None) -> None:
        self._paths = paths
        self._entries = {entry.id: entry for entry in (entries or load_manifest())}

    def entries(self) -> list[EngineEntry]:
        return list(self._entries.values())

    def entry(self, engine_id: str) -> EngineEntry | None:
        """Only ids from the manifest ever reach the filesystem (ADR-0011)."""
        return self._entries.get(engine_id)

    def asset(self, engine_id: str) -> PlatformAsset | None:
        entry = self.entry(engine_id)
        return entry.platforms.get(platform_key()) if entry else None

    def install_dir(self, entry: EngineEntry) -> Path:
        return self._paths.engine_dir(entry.id, entry.version)

    def installed(self, engine_id: str) -> InstalledEngine | None:
        """The manifest version if it is installed. Paths are derived, never stored absolute."""
        entry = self.entry(engine_id)
        if entry is None:
            return None
        folder = self.install_dir(entry)
        record = folder / INSTALL_RECORD
        if not record.is_file():
            return None
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
            binary = folder / Path(data["binary"]).name
            sha256 = str(data["binarySha256"])
        except (ValueError, KeyError, TypeError):
            return None
        if data.get("version") != entry.version or not binary.is_file():
            return None
        return InstalledEngine(entry.id, entry.version, binary, sha256)
