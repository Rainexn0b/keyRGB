from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from buildpython.steps.appimage import python_runtime, tkinter_bundle


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
        stdout=(
            "libXft.so.2 => /usr/lib/libXft.so.2 (0x0000)\n"
            "/lib64/ld-linux-x86-64.so.2 (0x0000)\n"
        ),
    )
    monkeypatch.setattr(tkinter_bundle.subprocess, "run", lambda *_args, **_kwargs: proc)

    deps = tkinter_bundle._ldd_deps(tmp_path / "_tkinter.so")

    assert deps == {
        "libXft.so.2": Path("/usr/lib/libXft.so.2"),
        "ld-linux-x86-64.so.2": Path("/lib64/ld-linux-x86-64.so.2"),
    }