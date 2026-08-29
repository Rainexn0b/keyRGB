from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from buildpython.steps.appimage import (
    build as appimage_build,
    common as appimage_common,
    python_runtime,
    tkinter_bundle,
)


def test_pip_install_args_construction(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    args = appimage_build._pip_install_args(("pystray>=0.19.5", "Pillow>=12.2.0"), site_packages)
    assert args[0] == appimage_build.python_exe()
    assert args[1:4] == ["-m", "pip", "install"]
    assert "pystray>=0.19.5" in args
    assert "Pillow>=12.2.0" in args
    assert "--target" in args
    target_index = args.index("--target")
    assert args[target_index + 1] == str(site_packages)
    # All specifiers must precede --target.
    assert target_index == 4 + 2


def test_appimagetool_is_pinned_to_versioned_release_with_digest() -> None:
    assert "continuous" not in appimage_build.APPIMAGETOOL_URL
    assert f"/{appimage_build.APPIMAGETOOL_VERSION}/" in appimage_build.APPIMAGETOOL_URL
    assert len(appimage_build.APPIMAGETOOL_SHA256) == 64
    assert all(ch in "0123456789abcdef" for ch in appimage_build.APPIMAGETOOL_SHA256)


def test_download_verified_reuses_matching_file_and_rejects_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "tool.bin"
    payload = b"pinned-appimagetool-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    target.write_bytes(payload)

    def _should_not_download(*_args, **_kwargs):
        raise AssertionError("download should not run for matching digest")

    monkeypatch.setattr(appimage_common, "download", _should_not_download)
    appimage_common.download_verified("https://example.invalid/tool.bin", target, expected_sha256=digest)
    assert target.read_bytes() == payload

    target.write_bytes(b"tampered")
    downloads: list[tuple[str, Path]] = []

    def _fake_download(url: str, dst: Path) -> None:
        downloads.append((url, dst))
        dst.write_bytes(payload)

    monkeypatch.setattr(appimage_common, "download", _fake_download)
    appimage_common.download_verified("https://example.invalid/tool.bin", target, expected_sha256=digest)
    assert downloads == [("https://example.invalid/tool.bin", target)]
    assert target.read_bytes() == payload

    target.write_bytes(b"stale-local-copy")
    monkeypatch.setattr(appimage_common, "download", lambda url, dst: dst.write_bytes(b"wrong-bytes"))
    with pytest.raises(SystemExit, match="SHA-256 mismatch"):
        appimage_common.download_verified("https://example.invalid/tool.bin", target, expected_sha256=digest)
    assert not target.exists()


def test_relative_path_under_prefix_falls_back_when_path_is_outside_prefix(tmp_path) -> None:
    prefix = tmp_path / "prefix"
    outside = tmp_path / "outside" / "python3.14"

    result = python_runtime._relative_path_under_prefix(path=outside, prefix=prefix, version="3.14")

    assert result == Path("lib") / "python3.14"


def test_relative_path_under_prefix_propagates_unexpected_relative_to_failure(monkeypatch, tmp_path) -> None:
    path = tmp_path / "prefix" / "lib" / "python3.14"
    prefix = tmp_path / "prefix"
    original_relative_to = Path.relative_to

    def fake_relative_to(self: Path, *other):
        if self == path:
            raise AssertionError("unexpected relative failure")
        return original_relative_to(self, *other)

    monkeypatch.setattr(Path, "relative_to", fake_relative_to)

    with pytest.raises(AssertionError, match="unexpected relative failure"):
        python_runtime._relative_path_under_prefix(path=path, prefix=prefix, version="3.14")


def test_ldd_deps_returns_empty_on_oserror(monkeypatch, tmp_path) -> None:
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("ldd missing")

    monkeypatch.setattr(tkinter_bundle.subprocess, "run", fake_run)

    assert tkinter_bundle._ldd_deps(tmp_path / "_tkinter.so") == {}


def test_ldd_deps_propagates_unexpected_subprocess_bug(monkeypatch, tmp_path) -> None:
    def fake_run(*_args, **_kwargs):
        raise AssertionError("unexpected subprocess bug")

    monkeypatch.setattr(tkinter_bundle.subprocess, "run", fake_run)

    with pytest.raises(AssertionError, match="unexpected subprocess bug"):
        tkinter_bundle._ldd_deps(tmp_path / "_tkinter.so")


def test_ldd_deps_parses_resolved_paths(monkeypatch, tmp_path) -> None:
    proc = SimpleNamespace(
        returncode=0,
        stdout=("libXft.so.2 => /usr/lib/libXft.so.2 (0x0000)\n/lib64/ld-linux-x86-64.so.2 (0x0000)\n"),
    )
    monkeypatch.setattr(tkinter_bundle.subprocess, "run", lambda *_args, **_kwargs: proc)

    deps = tkinter_bundle._ldd_deps(tmp_path / "_tkinter.so")

    assert deps == {
        "libXft.so.2": Path("/usr/lib/libXft.so.2"),
        "ld-linux-x86-64.so.2": Path("/lib64/ld-linux-x86-64.so.2"),
    }


def test_appimage_desktop_entry_includes_diagnostic_session_action() -> None:
    desktop = appimage_build._appimage_desktop_entry()

    assert "Exec=keyrgb" in desktop
    assert "Terminal=false" in desktop
    # Normal Exec and autostart convention is unchanged: the action launches via
    # the same `keyrgb` Exec convention.
    assert "Actions=DiagnosticSession;" in desktop
    assert "[Desktop Action DiagnosticSession]" in desktop
    assert "Name=Diagnostic Session" in desktop
    assert "Exec=keyrgb --diagnostic-session" in desktop
    assert "Terminal=true" in desktop
