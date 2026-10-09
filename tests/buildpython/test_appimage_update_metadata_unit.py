from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from buildpython.steps.appimage import build, update_metadata as updates


def test_release_workflow_provisions_zsync_and_requires_all_assets() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "            zsync \\" in workflow
    assert "test -s dist/keyrgb-x86_64.AppImage\n" in workflow
    assert "test -s dist/keyrgb-x86_64.AppImage.zsync" in workflow
    upload = workflow.split('gh release create "$GITHUB_REF_NAME"', 1)[1]
    for asset in (updates.APPIMAGE_NAME, f"{updates.APPIMAGE_NAME}.zsync", f"{updates.APPIMAGE_NAME}.sha256"):
        assert f"dist/{asset} \\" in upload
    assert "sha256sum keyrgb-x86_64.AppImage > keyrgb-x86_64.AppImage.sha256" in workflow


def _artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    appimage = tmp_path / updates.APPIMAGE_NAME
    appimage.write_bytes(b"fixture-appimage")
    sidecar = Path(f"{appimage}.zsync")
    checksum = hashlib.sha1(appimage.read_bytes(), usedforsecurity=False).hexdigest()
    sidecar.write_bytes(
        (
            f"zsync: 0.6.2\nFilename: {appimage.name}\nBlocksize: 2048\n"
            f"Length: {appimage.stat().st_size}\nHash-Lengths: 2,2,5\n"
            f"URL: {appimage.name}\nSHA-1: {checksum}\n\n"
        ).encode("ascii")
        + b"1234567"
    )
    monkeypatch.setattr(
        updates.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=updates.UPDATE_INFORMATION + "\n"),
    )
    return appimage, sidecar


def test_packaging_uses_explicit_stable_repo_asset_without_guessing(tmp_path: Path) -> None:
    tool, appdir, out = tmp_path / "tool", tmp_path / "AppDir", tmp_path / updates.APPIMAGE_NAME
    args = updates.packaging_args(tool, appdir, out)
    assert args == [
        str(tool),
        "--appimage-extract-and-run",
        "-u",
        "gh-releases-zsync|Rainexn0b|keyRGB|latest|keyrgb-x86_64.AppImage.zsync",
        "--file-url",
        updates.APPIMAGE_NAME,
        str(appdir),
        str(out),
    ]
    assert "--guess" not in args


def test_zsyncmake_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates.shutil, "which", lambda _name: None)
    with pytest.raises(SystemExit, match="install the zsync package"):
        updates.require_zsyncmake()
    monkeypatch.setattr(updates.shutil, "which", lambda _name: "/fixture/zsyncmake")
    updates.require_zsyncmake()


def test_matching_update_artifacts_pass(tmp_path, monkeypatch, capsys) -> None:
    appimage, _sidecar = _artifacts(tmp_path, monkeypatch)
    updates.validate_update_artifacts(appimage)
    assert "latest stable" in capsys.readouterr().out


@pytest.mark.parametrize("returncode,stdout", [(1, ""), (0, ""), (0, "gh-releases-zsync|wrong|repo|latest|x")])
def test_missing_or_wrong_embedded_metadata_fails(tmp_path, monkeypatch, returncode, stdout) -> None:
    appimage, _sidecar = _artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(
        updates.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=returncode, stdout=stdout, stderr="fixture-error"),
    )
    with pytest.raises(SystemExit, match="update information"):
        updates.validate_update_artifacts(appimage)


def test_metadata_probe_does_not_launch_or_extract_application(tmp_path, monkeypatch) -> None:
    appimage, _sidecar = _artifacts(tmp_path, monkeypatch)
    monkeypatch.setenv("APPIMAGE_EXTRACT_AND_RUN", "1")

    def probe(args, **kwargs):
        assert args == [str(appimage), "--appimage-updateinformation"]
        assert "APPIMAGE_EXTRACT_AND_RUN" not in kwargs["env"]
        assert kwargs["capture_output"] and not kwargs["check"]
        return SimpleNamespace(returncode=0, stdout=updates.UPDATE_INFORMATION)

    monkeypatch.setattr(updates.subprocess, "run", probe)
    updates.validate_update_artifacts(appimage)


def test_probe_unexpected_errors_propagate(tmp_path, monkeypatch) -> None:
    appimage, _sidecar = _artifacts(tmp_path, monkeypatch)

    def broken(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("probe", 1)

    monkeypatch.setattr(updates.subprocess, "run", broken)
    with pytest.raises(subprocess.TimeoutExpired):
        updates.validate_update_artifacts(appimage)


def test_missing_sidecar_fails(tmp_path, monkeypatch) -> None:
    appimage, sidecar = _artifacts(tmp_path, monkeypatch)
    sidecar.unlink()
    with pytest.raises(SystemExit, match="Missing AppImage update sidecar"):
        updates.validate_update_artifacts(appimage)


@pytest.mark.parametrize(
    "old,new,reason",
    [
        (b"Filename: keyrgb", b"Filename: other", "filename/URL"),
        (b"URL: keyrgb", b"URL: /build/keyrgb", "filename/URL"),
        (b"Length: 16", b"Length: 17", "length mismatch"),
        (b"Length: 16", b"Length: 0", "length mismatch"),
        (b"Length: 16", b"Length: bad", "header"),
        (b"Blocksize: 2048", b"Blocksize: 0", "block size"),
        (b"Blocksize: 2048", b"Blocksize: 3", "block size"),
        (b"Hash-Lengths: 2,2,5", b"Hash-Lengths: 2,9,5", "checksum lengths"),
        (b"Hash-Lengths: 2,2,5", b"Hash-Lengths: 3,2,5", "checksum lengths"),
        (b"SHA-1: ", b"SHA-1: 00", "checksum mismatch"),
        (b"1234567", b"123456", "checksum table"),
        (b"1234567", b"12345678", "checksum table"),
        (b"zsync: 0.6.2\n", b"", "format version"),
        (b"zsync: 0.6.2\n", b"zsync: 0.6.2\nzsync: 0.6.2\n", "duplicate"),
        (b"\n\n", b"\n", "separator"),
        (b"zsync: 0.6.2", b"zsync: \xff", "header"),
    ],
)
def test_malformed_or_stale_sidecar_fails(tmp_path, monkeypatch, old, new, reason) -> None:
    appimage, sidecar = _artifacts(tmp_path, monkeypatch)
    assert old in sidecar.read_bytes()
    sidecar.write_bytes(sidecar.read_bytes().replace(old, new))
    with pytest.raises(SystemExit, match=reason):
        updates.validate_update_artifacts(appimage)


def test_staging_only_does_not_require_update_tool(tmp_path, monkeypatch) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "assets/logo-keyrgb.png").touch()
    monkeypatch.setattr(build, "repo_root", lambda: root)
    monkeypatch.setenv("KEYRGB_APPIMAGE_STAGING_ONLY", "1")
    monkeypatch.setattr(build, "download_verified", lambda *_a, **_kw: None)
    monkeypatch.setattr(build, "chmod_x", lambda *_a, **_kw: None)
    monkeypatch.setattr(build, "bundle_python_runtime", lambda **kw: (kw["appdir"] / "usr").mkdir(parents=True))
    for name in ("bundle_tkinter", "bundle_libappindicator", "bundle_hardware_access"):
        monkeypatch.setattr(build, name, lambda **_kw: None)

    def forbidden(*_a, **_kw):
        raise AssertionError("staging is not a real AppImage build")

    monkeypatch.setattr(build, "require_zsyncmake", forbidden)
    monkeypatch.setattr(build, "validate_update_artifacts", forbidden)
    assert build.build_appimage().name == "KeyRGB.AppDir"


def test_real_packaging_clears_stale_sidecar_and_validates_output_in_dist(tmp_path, monkeypatch) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "assets/logo-keyrgb.png").touch()
    dist = root / "dist"
    dist.mkdir()
    out = dist / updates.APPIMAGE_NAME
    sidecar = Path(f"{out}.zsync")
    out.write_bytes(b"old")
    sidecar.write_bytes(b"stale")
    monkeypatch.setattr(build, "repo_root", lambda: root)
    monkeypatch.delenv("KEYRGB_APPIMAGE_STAGING_ONLY", raising=False)
    monkeypatch.setenv("KEYRGB_APPIMAGE_SKIP_DEPS", "1")
    monkeypatch.setattr(build, "require_zsyncmake", lambda: None)
    monkeypatch.setattr(build, "download_verified", lambda *_a, **_kw: None)
    monkeypatch.setattr(build, "chmod_x", lambda *_a, **_kw: None)
    monkeypatch.setattr(build, "bundle_python_runtime", lambda **kw: (kw["appdir"] / "usr").mkdir(parents=True))
    for name in ("bundle_tkinter", "bundle_libappindicator", "bundle_hardware_access"):
        monkeypatch.setattr(build, name, lambda **_kw: None)
    monkeypatch.setattr(build, "validate_appdir_glibc", lambda _appdir: None)

    def package(args, **kwargs):
        assert kwargs["cwd"] == dist
        assert not out.exists() and not sidecar.exists()
        assert args == updates.packaging_args(
            dist / "tools/appimagetool-x86_64.AppImage", dist / "appimage/KeyRGB.AppDir", out
        )
        out.write_bytes(b"new")
        sidecar.write_bytes(b"new-sidecar")

    def validate(path):
        assert path == out
        assert sidecar.read_bytes() == b"new-sidecar"

    monkeypatch.setattr(build, "run_checked", package)
    monkeypatch.setattr(build, "validate_update_artifacts", validate)
    assert build.build_appimage() == out
