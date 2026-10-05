from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from buildpython.steps.appimage import appindicator_bundle, compatibility, indicator_baseline, pygobject_bundle, smoke
from buildpython.utils.subproc import RunResult


def _fixture_deb(path: Path) -> indicator_baseline._BaselineDeb:
    return indicator_baseline._BaselineDeb(filename=path.name, sha256="0" * 64, archive_path=path.name)


def _indicator_deb(path: Path) -> Path:
    if shutil.which("ar") is None:
        pytest.skip("ar is required to build the indicator package fixture")
    payload = path.parent / "payload"
    payload.mkdir()
    libraries = {
        "libayatana-appindicator3.so.1.0.0": b"jammy-lib",
        "libayatana-indicator3.so.7.0.0": b"jammy-lib",
        "libayatana-ido3-0.4.so.0.0.0": b"jammy-lib",
        "libdbusmenu-glib.so.4.0.12": b"jammy-lib",
        "libdbusmenu-gtk3.so.4.0.12": b"jammy-lib",
    }
    links = {
        "libayatana-appindicator3.so.1": "libayatana-appindicator3.so.1.0.0",
        "libayatana-indicator3.so.7": "libayatana-indicator3.so.7.0.0",
        "libayatana-ido3-0.4.so.0": "libayatana-ido3-0.4.so.0.0.0",
        "libdbusmenu-glib.so.4": "libdbusmenu-glib.so.4.0.12",
        "libdbusmenu-gtk3.so.4": "libdbusmenu-gtk3.so.4.0.12",
    }
    data = payload / "data.tar.xz"
    with tarfile.open(data, "w:xz") as tar:
        for name, content in libraries.items():
            info = tarfile.TarInfo(name=f"usr/lib/x86_64-linux-gnu/{name}")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        for name, target in links.items():
            info = tarfile.TarInfo(name=f"usr/lib/x86_64-linux-gnu/{name}")
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    (payload / "debian-binary").write_text("2.0\n", encoding="utf-8")
    with tarfile.open(payload / "control.tar.xz", "w:xz"):
        pass
    packed = subprocess.run(
        ["ar", "rc", str(path), "debian-binary", "control.tar.xz", "data.tar.xz"],
        cwd=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    return path


def _elf(tmp_path: Path, name: str = "usr/lib/libpython3.10.so.1.0") -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x7fELFfixture")
    return path


@pytest.mark.parametrize("symbol", ["GLIBC_2.35", "GLIBC_2.2.5"])
def test_glibc_check_accepts_baseline_and_ignores_version_definitions(tmp_path, monkeypatch, capsys, symbol) -> None:
    path = _elf(tmp_path)
    (path.parent / "alias.so").symlink_to(path.name)
    (path.parent / "text.txt").write_text("GLIBC_2.99", encoding="utf-8")
    calls = []

    def inspect(args, **_kwargs):
        calls.append(args)
        return SimpleNamespace(
            returncode=0,
            stdout=f"Version definition section\nName: GLIBC_2.99\nVersion needs section\nName: {symbol}\n",
        )

    monkeypatch.setattr(compatibility.shutil, "which", lambda _name: "/fixture/readelf")
    monkeypatch.setattr(compatibility.subprocess, "run", inspect)
    compatibility.validate_appdir_glibc(tmp_path)
    assert len(calls) == 1
    assert "1 ELF files" in capsys.readouterr().out


@pytest.mark.parametrize("symbol", ["GLIBC_2.38", "GLIBC_2.36", "GLIBC_ABI_DT_RELR", "GLIBC_PRIVATE"])
def test_glibc_check_rejects_newer_or_unrecognized_requirements_in_wheels(tmp_path, monkeypatch, symbol) -> None:
    _elf(tmp_path, "usr/lib/keyrgb/site-packages/native.so")
    monkeypatch.setattr(compatibility.shutil, "which", lambda _name: "/fixture/readelf")
    monkeypatch.setattr(
        compatibility.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=f"Version needs section\nName: {symbol}\n"),
    )
    with pytest.raises(SystemExit, match=f"native.so requires {symbol}"):
        compatibility.validate_appdir_glibc(tmp_path)


def test_glibc_check_requires_readelf_and_elf_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(compatibility.shutil, "which", lambda _name: None)
    with pytest.raises(SystemExit, match="requires readelf"):
        compatibility.validate_appdir_glibc(tmp_path)
    monkeypatch.setattr(compatibility.shutil, "which", lambda _name: "/fixture/readelf")
    with pytest.raises(SystemExit, match="no ELF files"):
        compatibility.validate_appdir_glibc(tmp_path)


def test_glibc_check_fails_when_elf_inspection_fails(tmp_path, monkeypatch) -> None:
    _elf(tmp_path)
    monkeypatch.setattr(compatibility.shutil, "which", lambda _name: "/fixture/readelf")
    monkeypatch.setattr(
        compatibility.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr="bad ELF")
    )
    with pytest.raises(SystemExit, match="bad ELF"):
        compatibility.validate_appdir_glibc(tmp_path)


def test_indicator_bundle_includes_dbusmenu_glib_without_host_package(tmp_path, monkeypatch) -> None:
    host_lib = tmp_path / "host"
    host_lib.mkdir()
    (host_lib / "libdbusmenu-glib.so.4.0.0").write_bytes(b"native-lib")
    (host_lib / "libdbusmenu-glib.so.4").symlink_to("libdbusmenu-glib.so.4.0.0")
    monkeypatch.setattr(appindicator_bundle, "Path", lambda _path: host_lib)

    def fail_baseline(*_args, **_kwargs):
        raise AssertionError("compatible host libraries must not be replaced")

    monkeypatch.setattr(appindicator_bundle, "install_ubuntu_2204_indicator_stack", fail_baseline)
    appdir = tmp_path / "AppDir"
    appindicator_bundle.bundle_libappindicator(appdir=appdir)
    assert (appdir / "usr/lib/libdbusmenu-glib.so.4").read_bytes() == b"native-lib"


def test_newer_host_indicator_libraries_are_replaced(tmp_path, monkeypatch) -> None:
    host_lib = tmp_path / "host"
    host_lib.mkdir()
    (host_lib / "libayatana-appindicator3.so.1.0.0").write_bytes(b"\x7fELFtoo-new")
    monkeypatch.setattr(appindicator_bundle, "Path", lambda _path: host_lib)
    monkeypatch.setattr(appindicator_bundle, "host_indicator_stack_exceeds_baseline", lambda _usr_lib: True)
    replaced = []

    def install(usr_lib: Path) -> None:
        replaced.append(usr_lib)
        for child in list(usr_lib.iterdir()):
            child.unlink()
        (usr_lib / "libayatana-appindicator3.so.1").write_bytes(b"jammy")

    monkeypatch.setattr(appindicator_bundle, "install_ubuntu_2204_indicator_stack", install)
    appdir = tmp_path / "AppDir"
    appindicator_bundle.bundle_libappindicator(appdir=appdir)
    assert replaced == [appdir / "usr/lib"]
    assert (appdir / "usr/lib/libayatana-appindicator3.so.1").read_bytes() == b"jammy"
    assert not (appdir / "usr/lib/libayatana-appindicator3.so.1.0.0").exists()


def test_baseline_install_replaces_only_after_pinned_libraries_pass(tmp_path, monkeypatch) -> None:
    deb = _indicator_deb(tmp_path / "stack.deb")
    cache = tmp_path / "cache"
    usr_lib = tmp_path / "usr/lib"
    usr_lib.mkdir(parents=True)
    stale = usr_lib / "libdbusmenu-glib.so.4.0.99"
    stale.write_bytes(b"too-new")
    monkeypatch.setattr(indicator_baseline, "_BASELINE_DEBS", (_fixture_deb(deb),))
    monkeypatch.setattr(
        indicator_baseline, "download_verified", lambda _url, dst, **_kwargs: dst.write_bytes(deb.read_bytes())
    )
    monkeypatch.setattr(indicator_baseline, "elf_exceeds_glibc_baseline", lambda _path: False)

    indicator_baseline.install_ubuntu_2204_indicator_stack(usr_lib, cache_dir=cache)

    assert not stale.exists()
    assert (usr_lib / "libdbusmenu-glib.so.4").is_symlink()
    assert (usr_lib / "libayatana-appindicator3.so.1.0.0").read_bytes() == b"jammy-lib"
    assert (usr_lib / "libayatana-appindicator3.so.1").readlink() == Path("libayatana-appindicator3.so.1.0.0")


def test_baseline_install_leaves_host_libraries_when_pinned_copy_is_too_new(tmp_path, monkeypatch) -> None:
    deb = _indicator_deb(tmp_path / "stack.deb")
    usr_lib = tmp_path / "usr/lib"
    usr_lib.mkdir(parents=True)
    stale = usr_lib / "libdbusmenu-glib.so.4.0.99"
    stale.write_bytes(b"too-new")
    monkeypatch.setattr(indicator_baseline, "_BASELINE_DEBS", (_fixture_deb(deb),))
    monkeypatch.setattr(
        indicator_baseline, "download_verified", lambda _url, dst, **_kwargs: dst.write_bytes(deb.read_bytes())
    )
    monkeypatch.setattr(indicator_baseline, "elf_exceeds_glibc_baseline", lambda _path: True)

    with pytest.raises(SystemExit, match="exceeds GLIBC_2.35"):
        indicator_baseline.install_ubuntu_2204_indicator_stack(usr_lib, cache_dir=tmp_path / "cache")

    assert stale.read_bytes() == b"too-new"


def test_gi_bundle_keeps_transitive_typelib_namespaces(tmp_path, monkeypatch) -> None:
    site = tmp_path / "host-site"
    (site / "gi").mkdir(parents=True)
    (site / "gi/__init__.py").touch()
    typelibs = tmp_path / "typelibs"
    typelibs.mkdir()
    names = ("Gtk-3.0.typelib", "Atk-1.0.typelib", "xlib-2.0.typelib", "HarfBuzz-0.0.typelib")
    for name in names:
        (typelibs / name).write_bytes(b"metadata")
    monkeypatch.setattr(
        pygobject_bundle.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps({"purelib": str(site)})),
    )
    monkeypatch.setattr(
        pygobject_bundle,
        "Path",
        lambda value: typelibs if value == "/usr/lib/x86_64-linux-gnu/girepository-1.0" else Path(value),
    )
    appdir = tmp_path / "AppDir"
    pygobject_bundle.bundle_pygobject(appdir=appdir, site_packages=appdir / "site-packages")
    for name in names:
        assert (appdir / "usr/lib/girepository-1.0" / name).read_bytes() == b"metadata"


@pytest.mark.parametrize("override", [None, "fixture:custom"])
@pytest.mark.parametrize("failed", [False, True])
def test_smoke_checks_oldest_and_newer_lts_and_preserves_override(tmp_path, monkeypatch, override, failed) -> None:
    artifact = tmp_path / "dist/keyrgb-x86_64.AppImage"
    artifact.parent.mkdir()
    artifact.touch()
    monkeypatch.setattr(smoke, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(smoke.shutil, "which", lambda _name: "/fixture/docker")
    monkeypatch.delenv("KEYRGB_SKIP_APPIMAGE_SMOKE", raising=False)
    monkeypatch.delenv("KEYRGB_APPIMAGE_SMOKE_IMAGE", raising=False)
    if override:
        monkeypatch.setenv("KEYRGB_APPIMAGE_SMOKE_IMAGE", override)
    images = []

    def execute(args, **_kwargs):
        images.append(args[-4])
        return RunResult("docker fixture", "fixture-out", "fixture-err" if failed else "", 1 if failed else 0)

    monkeypatch.setattr(smoke, "run", execute)
    result = smoke.appimage_smoke_runner()
    assert images == ([override] if override else ["ubuntu:22.04"] if failed else ["ubuntu:22.04", "ubuntu:24.04"])
    assert result.exit_code == (1 if failed else 0)
    assert "fixture-out" in result.stdout
    assert not result.skip_reason


def test_smoke_script_checks_desktop_and_actual_launcher_without_masking_bundle() -> None:
    script = smoke._smoke_script()
    checked = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True, check=False)
    assert checked.returncode == 0, checked.stderr
    assert "tk.Tk()" in script
    assert 'PYSTRAY_BACKEND="appindicator"' in script
    assert '"$HERE/AppRun" --diagnostics --no-usb' in script
    assert "GI_TYPELIB_PATH" in script
    packages = " ".join(line for line in script.splitlines() if "apt-get install" in line)
    assert "python3-gi" not in packages
    assert "indicator" not in packages
    assert "dbusmenu" not in packages
