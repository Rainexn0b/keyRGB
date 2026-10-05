from __future__ import annotations

from pathlib import Path

import pytest

from buildpython.steps.appimage import build as appimage_build
from buildpython.steps.appimage.hardware_access_bundle import (
    HARDWARE_ACCESS_APPDIR_RELATIVE,
    HARDWARE_ACCESS_FILES,
    bundle_hardware_access,
)
from keyrgb.gui.hardware_access import APPDIR_RELATIVE

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_bundle_relative_path_matches_the_runtime_resolver() -> None:
    assert HARDWARE_ACCESS_APPDIR_RELATIVE == APPDIR_RELATIVE


def test_bundle_copies_required_files_and_not_the_downloader(tmp_path: Path) -> None:
    dest = bundle_hardware_access(appdir=tmp_path / "AppDir", root=_REPO_ROOT)

    assert dest == tmp_path / "AppDir" / APPDIR_RELATIVE
    for _src_rel, dest_rel in HARDWARE_ACCESS_FILES:
        bundled = dest / dest_rel
        assert bundled.is_file(), dest_rel
        assert not bundled.is_symlink()
        assert bundled.read_bytes() == (_REPO_ROOT / _src_rel).read_bytes()
    assert not (dest / "scripts/common.sh").exists()
    assert not (dest / "install.sh").exists()
    bundled_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in dest.rglob("*") if path.is_file()
    )
    assert "appimage_install" not in bundled_text


def test_bundle_rejects_a_missing_payload(tmp_path: Path) -> None:
    root = tmp_path / "incomplete"
    (root / "scripts/lib").mkdir(parents=True)
    with pytest.raises(SystemExit, match="Cannot bundle hardware-access payload"):
        bundle_hardware_access(appdir=tmp_path / "AppDir", root=root)


def test_appimage_build_calls_the_hardware_access_bundler() -> None:
    text = Path(appimage_build.__file__).read_text(encoding="utf-8")
    assert "bundle_hardware_access(appdir=appdir, root=root)" in text
