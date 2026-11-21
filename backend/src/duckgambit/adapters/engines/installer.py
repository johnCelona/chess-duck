import hashlib
import json
import os
import shutil
import tarfile
import zipfile
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
INSTALLED_ROOT = ROOT / "engines" / "installed"
TMP_ROOT = ROOT / "engines" / ".tmp"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def platform_key() -> str:
    import platform

    if platform.system() == "Windows":
        return "win32"
    if platform.system() == "Darwin":
        return "darwin"
    return "linux"


def safe_extract(archive: Path, destination: Path, archive_type: str) -> None:
    destination_resolved = destination.resolve()
    if archive_type == "zip":
        opener = zipfile.ZipFile
        members = lambda z: z.infolist()
        names = lambda item: item.filename
        extract = lambda z: z.extractall(destination)
    elif archive_type == "tar":
        opener = tarfile.open
        members = lambda t: t.getmembers()
        names = lambda item: item.name
        extract = lambda t: t.extractall(destination)
    else:
        raise ValueError("Unsupported archive type")

    with opener(archive, "r") as opened:
        for item in members(opened):
            target = destination_resolved / names(item)
            if destination_resolved not in target.resolve().parents:
                raise ValueError("Archive contains a path traversal entry")
        extract(opened)


async def install_engine(engine_id: str) -> dict:
    manifest = next(
        (item for item in load_manifest()["engines"] if item["id"] == engine_id),
        None,
    )
    if manifest is None:
        raise ValueError("Unknown engine")
    platform_asset = manifest["platforms"].get(platform_key())
    if platform_asset is None:
        raise ValueError("No download is available for this platform")

    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    archive = TMP_ROOT / f"{engine_id}-{manifest['version']}.{platform_asset['archive']}"
    async with httpx.AsyncClient(follow_redirects=True, timeout=300) as client:
        async with client.stream("GET", platform_asset["url"]) as response:
            response.raise_for_status()
            with archive.open("wb") as output:
                async for chunk in response.aiter_bytes():
                    output.write(chunk)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest.lower() != platform_asset["sha256"].lower():
        archive.unlink(missing_ok=True)
        raise ValueError("Checksum mismatch")

    install_dir = INSTALLED_ROOT / engine_id / manifest["version"]
    if install_dir.exists():
        shutil.rmtree(install_dir)
    install_dir.mkdir(parents=True)
    safe_extract(archive, install_dir, platform_asset["archive"])

    binary = install_dir / platform_asset["binary"]
    if not binary.is_file():
        raise ValueError("Downloaded archive did not contain the manifest binary")
    if os.name != "nt":
        binary.chmod(binary.stat().st_mode | 0o111)

    state = {
        "id": engine_id,
        "version": manifest["version"],
        "binary": str(binary),
        "status": "installed",
    }
    (install_dir / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    archive.unlink(missing_ok=True)
    return state


def installed_state(engine_id: str) -> dict | None:
    engine_dir = INSTALLED_ROOT / engine_id
    if not engine_dir.exists():
        return None
    state_files = list(engine_dir.glob("*/state.json"))
    if not state_files:
        return None
    return json.loads(state_files[-1].read_text(encoding="utf-8"))


def remove_engine(engine_id: str) -> None:
    engine_dir = INSTALLED_ROOT / engine_id
    if engine_dir.exists():
        shutil.rmtree(engine_dir)
