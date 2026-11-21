import zipfile

import pytest

from duckgambit.adapters.engines.installer import safe_extract


def test_zip_slip_is_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    destination = tmp_path / "out"
    destination.mkdir()
    with zipfile.ZipFile(archive, "w") as opened:
        opened.writestr("../escaped.txt", "unsafe")

    with pytest.raises(ValueError):
        safe_extract(archive, destination, "zip")

    assert not (tmp_path / "escaped.txt").exists()
