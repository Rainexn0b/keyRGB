from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from buildpython.steps.appimage import tkinter_bundle
from buildpython.steps.appimage.tkinter_bundle import TkinterManifest


def _manifest(
    base: Path,
    *,
    tcl_version: str = "9.0",
    tk_version: str = "9.0",
) -> TkinterManifest:
    return TkinterManifest(
        extension=base / "lib" / "python3.13" / "lib-dynload" / "_tkinter.so",
        tcl_version=tcl_version,
        tk_version=tk_version,
        base_prefix=base,
    )


def _write_lib(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-native-lib")
    return path


def _write_script_tree(root: Path, *, name: str, marker: str) -> Path:
    tree = root / name
    (tree / "subdir").mkdir(parents=True, exist_ok=True)
    (tree / marker).write_text("script-marker", encoding="utf-8")
    return tree


def test_parse_tkinter_manifest_accepts_tcl8_and_tcl9_payloads(tmp_path) -> None:
    for tcl_version, tk_version in (("8.6", "8.6"), ("9.0", "9.0")):
        payload = json.dumps(
            {
                "extension": str(tmp_path / "_tkinter.so"),
                "tcl_version": tcl_version,
                "tk_version": tk_version,
                "base_prefix": str(tmp_path / "base"),
            }
        )
        manifest = tkinter_bundle._parse_tkinter_manifest(payload)
        assert manifest.tcl_version == tcl_version
        assert manifest.tk_version == tk_version
        assert manifest.base_prefix == tmp_path / "base"


def test_parse_tkinter_manifest_fails_closed() -> None:
    with pytest.raises(SystemExit):
        tkinter_bundle._parse_tkinter_manifest("not-json{{")
    with pytest.raises(SystemExit):
        tkinter_bundle._parse_tkinter_manifest(json.dumps(["not", "a", "dict"]))
    with pytest.raises(SystemExit):
        tkinter_bundle._parse_tkinter_manifest(json.dumps({"tcl_version": "9.0"}))


def test_tkinter_manifest_subprocess_failure_fails_closed(monkeypatch) -> None:
    proc = SimpleNamespace(returncode=1, stdout="", stderr="boom")
    monkeypatch.setattr(tkinter_bundle.subprocess, "run", lambda *_args, **_kwargs: proc)
    with pytest.raises(SystemExit):
        tkinter_bundle._tkinter_manifest()


def test_runtime_script_env_exports_use_stable_version_free_paths() -> None:
    tcl_export, tk_export = tkinter_bundle.runtime_script_env_exports("$HERE")
    assert tcl_export == 'export TCL_LIBRARY="$HERE/usr/lib/tcl"'
    assert tk_export == 'export TK_LIBRARY="$HERE/usr/lib/tk"'
    assert "8.6" not in tcl_export + tk_export
    assert "9.0" not in tcl_export + tk_export


def test_native_lib_dirs_search_base_prefix_first(tmp_path) -> None:
    base = tmp_path / "base"
    (base / "lib").mkdir(parents=True)
    dirs = tkinter_bundle._native_lib_dirs(_manifest(base))
    assert dirs[0] == base / "lib"


def test_find_exact_lib_never_selects_mismatched_version(tmp_path) -> None:
    _write_lib(tmp_path / "libtcl8.6.so")
    assert tkinter_bundle._find_exact_lib([tmp_path], stem="libtcl9.0") is None
    assert tkinter_bundle._find_exact_lib([tmp_path], stem="libtcl8.6") is not None


def test_bundle_tkinter_with_tcl8_separate_libs(tmp_path, monkeypatch) -> None:
    base = tmp_path / "base"
    lib_dir = base / "lib"
    tcl_lib = _write_lib(lib_dir / "libtcl8.6.so")
    tk_lib = _write_lib(lib_dir / "libtk8.6.so")
    _write_script_tree(lib_dir, name="tcl8.6", marker="init.tcl")
    _write_script_tree(lib_dir, name="tk8.6", marker="tk.tcl")

    monkeypatch.setattr(
        tkinter_bundle, "_tkinter_manifest", lambda: _manifest(base, tcl_version="8.6", tk_version="8.6")
    )

    appdir = tmp_path / "AppDir"
    tkinter_bundle.bundle_tkinter(appdir=appdir)

    assert (appdir / "usr" / "lib" / tcl_lib.name).exists()
    assert (appdir / "usr" / "lib" / tk_lib.name).exists()
    assert (appdir / "usr" / "lib" / "tcl" / "init.tcl").exists()
    assert (appdir / "usr" / "lib" / "tk" / "tk.tcl").exists()


def test_bundle_tkinter_with_tcl9_combined_lib(tmp_path, monkeypatch) -> None:
    base = tmp_path / "base"
    lib_dir = base / "lib"
    tcl_lib = _write_lib(lib_dir / "libtcl9.0.so")
    combined = _write_lib(lib_dir / "libtcl9tk9.0.so")
    _write_script_tree(lib_dir, name="tcl9.0", marker="init.tcl")
    _write_script_tree(lib_dir, name="tk9.0", marker="tk.tcl")

    monkeypatch.setattr(tkinter_bundle, "_tkinter_manifest", lambda: _manifest(base))

    appdir = tmp_path / "AppDir"
    tkinter_bundle.bundle_tkinter(appdir=appdir)

    assert (appdir / "usr" / "lib" / tcl_lib.name).exists()
    assert (appdir / "usr" / "lib" / combined.name).exists()
    assert (appdir / "usr" / "lib" / "tcl" / "init.tcl").exists()
    assert (appdir / "usr" / "lib" / "tk" / "tk.tcl").exists()


def test_bundle_tkinter_rejects_mismatched_distro_libs(tmp_path, monkeypatch) -> None:
    base = tmp_path / "base"
    lib_dir = base / "lib"
    _write_lib(lib_dir / "libtcl8.6.so")
    _write_lib(lib_dir / "libtk8.6.so")
    _write_script_tree(lib_dir, name="tcl8.6", marker="init.tcl")
    _write_script_tree(lib_dir, name="tk8.6", marker="tk.tcl")

    # Interpreter needs Tcl 9 but only Tcl 8 libs exist: fail, don't mismatch.
    monkeypatch.setattr(tkinter_bundle, "_tkinter_manifest", lambda: _manifest(base))
    with pytest.raises(SystemExit, match="no exact native library match"):
        tkinter_bundle.bundle_tkinter(appdir=tmp_path / "AppDir")


def test_bundle_tkinter_fails_closed_without_script_trees(tmp_path, monkeypatch) -> None:
    base = tmp_path / "base"
    lib_dir = base / "lib"
    _write_lib(lib_dir / "libtcl9.0.so")
    _write_lib(lib_dir / "libtcl9tk9.0.so")

    monkeypatch.setattr(tkinter_bundle, "_tkinter_manifest", lambda: _manifest(base))
    with pytest.raises(SystemExit, match="script tree"):
        tkinter_bundle.bundle_tkinter(appdir=tmp_path / "AppDir")


def test_ldd_deps_propagates_lib_dirs_via_ld_library_path(tmp_path, monkeypatch) -> None:
    seen: dict = {}

    def fake_run(*_args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(tkinter_bundle.subprocess, "run", fake_run)
    lib_dir = tmp_path / "base" / "lib"

    assert tkinter_bundle._ldd_deps(tmp_path / "_tkinter.so", lib_dirs=[lib_dir]) == {}
    assert str(lib_dir) in seen["env"]["LD_LIBRARY_PATH"]


def test_ldd_deps_without_lib_dirs_inherits_process_env(monkeypatch, tmp_path) -> None:
    seen: dict = {}

    def fake_run(*_args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(tkinter_bundle.subprocess, "run", fake_run)

    assert tkinter_bundle._ldd_deps(tmp_path / "_tkinter.so") == {}
    assert seen["env"] is None
