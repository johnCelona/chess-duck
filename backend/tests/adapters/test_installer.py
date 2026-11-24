import hashlib
import io
import shutil
import stat
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from duckgambit.adapters.engines.catalog import (
    EngineCatalog,
    EngineEntry,
    PlatformAsset,
    load_manifest,
    platform_key,
)
from duckgambit.adapters.engines.installer import (
    EngineInstaller,
    InstallError,
    safe_extract,
    smoke_test,
)
from duckgambit.adapters.system import DataPaths, UnsafePathError, safe_child

pytestmark = pytest.mark.anyio

FAKE_UCI = Path(__file__).resolve().parents[1] / "fakes" / "fake_uci.py"


def make_zip(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def setup(tmp_path):
    paths = DataPaths(tmp_path / "data")
    paths.prepare()
    archive = make_zip(
        tmp_path / "engine.zip",
        {
            "pkg/engine.bin": b"binary-v1",
            "pkg/Copying.txt": b"GPL",
            "pkg/src/huge.cpp": b"source we do not keep",
        },
    )

    def build(sha256=None, smoke=lambda command, name: None, archive_path=archive):
        asset = PlatformAsset(
            url="https://example.invalid/engine.zip",
            sha256=sha256 or sha(archive_path),
            size_bytes=archive_path.stat().st_size,
            archive="zip",
            binary="pkg/engine.bin",
            keep=("pkg/Copying.txt",),
        )
        entry = EngineEntry(
            "testfish",
            "Testfish",
            "1",
            "GPL-3.0",
            "https://e",
            "https://s",
            "Testfish",
            {platform_key(): asset},
        )
        catalog = EngineCatalog(paths, [entry])

        async def fetch(url, destination, max_bytes):
            assert url == asset.url
            shutil.copy(archive_path, destination)
            return sha(archive_path)

        return catalog, EngineInstaller(catalog, paths, fetch=fetch, smoke=smoke)

    return paths, build, tmp_path


async def test_install_keeps_only_the_binary_and_license_files(setup):
    paths, build, _ = setup
    catalog, installer = build()

    installed = await installer.install("testfish")

    folder = paths.engines / "testfish" / "1"
    assert installed.binary == folder / "engine.bin"
    assert sorted(p.name for p in folder.iterdir()) == [
        "Copying.txt",
        "engine.bin",
        "installed.json",
    ]
    assert installed.binary_sha256 == hashlib.sha256(b"binary-v1").hexdigest()
    assert catalog.installed("testfish") == installed
    assert list(paths.tmp.iterdir()) == []


async def test_checksum_mismatch_installs_nothing(setup):
    paths, build, _ = setup
    catalog, installer = build(sha256="0" * 64)

    with pytest.raises(InstallError) as error:
        await installer.install("testfish")

    assert error.value.code == "engine.checksum_mismatch"
    assert catalog.installed("testfish") is None
    assert list(paths.tmp.iterdir()) == []


async def test_a_failed_smoke_test_leaves_the_previous_install_working(setup):
    _, build, tmp_path = setup
    catalog, installer = build()
    await installer.install("testfish")

    def failing(command, name):
        raise InstallError("engine.smoke_test_failed", "nope")

    newer = make_zip(tmp_path / "v2.zip", {"pkg/engine.bin": b"binary-v2-broken"})
    _, broken_installer = build(smoke=failing, archive_path=newer)
    with pytest.raises(InstallError) as error:
        await broken_installer.install("testfish")

    assert error.value.code == "engine.smoke_test_failed"
    assert catalog.installed("testfish").binary.read_bytes() == b"binary-v1"


async def test_reinstall_replaces_the_old_version_in_place(setup):
    _, build, tmp_path = setup
    _, installer = build()
    await installer.install("testfish")

    newer = make_zip(tmp_path / "v2.zip", {"pkg/engine.bin": b"binary-v2"})
    catalog, second = build(archive_path=newer)
    await second.install("testfish")

    assert catalog.installed("testfish").binary.read_bytes() == b"binary-v2"


async def test_unknown_engines_and_missing_platforms_are_refused(setup):
    paths, build, _ = setup
    _, installer = build()

    with pytest.raises(InstallError) as error:
        await installer.install("not-in-manifest")
    assert error.value.code == "engine.unknown"

    entry = EngineEntry("other", "Other", "1", "MIT", "https://e", "https://s", "Other", {})
    with pytest.raises(InstallError) as error:
        await EngineInstaller(EngineCatalog(paths, [entry]), paths).install("other")
    assert error.value.code == "engine.unsupported_platform"


async def test_remove_deletes_the_install(setup):
    paths, build, _ = setup
    catalog, installer = build()
    await installer.install("testfish")

    await installer.remove("testfish")

    assert catalog.installed("testfish") is None
    assert not (paths.engines / "testfish").exists()


@pytest.mark.parametrize(
    "name", ["../escaped.txt", "/abs.txt", "a/../../escaped.txt", "C:/evil.txt"]
)
def test_zip_entries_that_escape_the_folder_are_rejected(tmp_path, name):
    archive = make_zip(tmp_path / "bad.zip", {"ok.txt": b"fine", name: b"unsafe"})

    with pytest.raises(InstallError) as error:
        safe_extract(archive, tmp_path / "out", "zip")

    assert error.value.code == "engine.unsafe_archive"
    assert not (tmp_path / "escaped.txt").exists()


def test_zip_symlinks_are_rejected(tmp_path):
    archive = tmp_path / "link.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        info = zipfile.ZipInfo("link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        opened.writestr(info, "/etc/passwd")

    with pytest.raises(InstallError):
        safe_extract(archive, tmp_path / "out", "zip")


def test_tar_links_and_escapes_are_rejected(tmp_path):
    def tar_with(member: tarfile.TarInfo, data: bytes = b"") -> Path:
        path = tmp_path / f"{member.name.replace('/', '_').replace('.', '_')}.tar.gz"
        with tarfile.open(path, "w:gz") as opened:
            member.size = len(data)
            opened.addfile(member, io.BytesIO(data))
        return path

    link = tarfile.TarInfo("link")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    escape = tarfile.TarInfo("../escaped.txt")

    for archive in (tar_with(link), tar_with(escape, b"x")):
        with pytest.raises(InstallError):
            safe_extract(archive, tmp_path / "out", "tar.gz")
    assert not (tmp_path / "escaped.txt").exists()


def test_tar_archives_extract_plain_files(tmp_path):
    archive = tmp_path / "ok.tar.gz"
    with tarfile.open(archive, "w:gz") as opened:
        info = tarfile.TarInfo("pkg/engine")
        info.size = 3
        opened.addfile(info, io.BytesIO(b"abc"))

    safe_extract(archive, tmp_path / "out", "tar.gz")

    assert (tmp_path / "out" / "pkg" / "engine").read_bytes() == b"abc"


def test_smoke_test_accepts_a_working_engine_and_rejects_impostors(monkeypatch):
    command = [sys.executable, str(FAKE_UCI)]
    monkeypatch.setenv("FAKE_UCI_MODE", "normal")
    smoke_test(command, "Fake UCI")

    monkeypatch.setenv("FAKE_UCI_MODE", "wrong-name")
    with pytest.raises(InstallError) as error:
        smoke_test(command, "Fake UCI")
    assert error.value.code == "engine.smoke_test_failed"


def test_smoke_test_fails_for_something_that_is_not_an_engine(tmp_path):
    with pytest.raises(InstallError):
        smoke_test([sys.executable, "-c", "print('hello')"], "Fake UCI")
    with pytest.raises(InstallError):
        smoke_test([str(tmp_path / "missing.exe")], "Fake UCI")


def test_committed_manifest_is_well_formed_and_pinned():
    entries = load_manifest()

    stockfish = next(entry for entry in entries if entry.id == "stockfish")
    assert {"windows-x86_64", "linux-x86_64", "macos-universal"} <= set(stockfish.platforms)
    for asset in stockfish.platforms.values():
        assert asset.url.startswith("https://github.com/official-stockfish/Stockfish/releases/")
        assert len(asset.sha256) == 64
        assert asset.size_bytes > 1_000_000


def test_manifest_with_a_plain_http_url_is_refused():
    text = (
        '{"engines": [{"id": "x", "name": "X", "version": "1", "license": "MIT", "homepage": "h",'
        ' "sourceUrl": "s", "uciName": "X", "platforms": {"linux-x86_64": {"url": "http://x/y.zip",'
        ' "sha256": "' + "a" * 64 + '", "sizeBytes": 1, "archive": "zip", "binary": "x"}}}]}'
    )

    with pytest.raises(ValueError, match="https"):
        load_manifest(text)


@pytest.mark.parametrize("parts", [("..",), ("..", ".."), ("a", "..", "..", "b"), ("..\\..",)])
def test_safe_child_refuses_to_leave_the_root(tmp_path, parts):
    with pytest.raises(UnsafePathError):
        safe_child(tmp_path / "root", *parts)


def test_safe_child_allows_paths_inside_the_root(tmp_path):
    assert (
        safe_child(tmp_path, "engines", "stockfish")
        == (tmp_path / "engines" / "stockfish").resolve()
    )
