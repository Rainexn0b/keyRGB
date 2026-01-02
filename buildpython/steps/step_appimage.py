from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import urllib.request
import json
from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run


APPIMAGETOOL_URL = (
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/"
    "appimagetool-x86_64.AppImage"
)


def _download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(url) as resp, dst.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _chmod_x(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_checked(args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        env={**os.environ, **(env or {})},
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _python_runtime_manifest() -> dict[str, str]:
    # Query the build-time interpreter. We'll bundle this runtime into the AppImage
    # to avoid relying on the user's system python version.
    code = """
import json
import sys
import sysconfig

paths = sysconfig.get_paths()

out = {
    "executable": sys.executable,
    "prefix": sys.prefix,
    "version": f"{sys.version_info.major}.{sys.version_info.minor}",
    "stdlib": paths.get("stdlib") or "",
    "platstdlib": paths.get("platstdlib") or "",
    "libdir": sysconfig.get_config_var("LIBDIR") or "",
    "ldlibrary": sysconfig.get_config_var("LDLIBRARY") or "",
    "instsoname": sysconfig.get_config_var("INSTSONAME") or "",
}

print(json.dumps(out))
"""
    proc = subprocess.run(
        [python_exe(), "-c", code],
        cwd=str(repo_root()),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    try:
        data = json.loads(proc.stdout)
    except Exception:
        raise SystemExit(f"Failed to parse python runtime manifest: {proc.stdout}\n{proc.stderr}")

    if not isinstance(data, dict):
        raise SystemExit("Invalid python runtime manifest")
    return {str(k): str(v) for k, v in data.items()}


def _bundle_python_runtime(*, appdir: Path) -> None:
    manifest = _python_runtime_manifest()
    prefix = Path(manifest.get("prefix", ""))
    version = manifest.get("version", "")
    stdlib = Path(manifest.get("stdlib", ""))
    platstdlib = Path(manifest.get("platstdlib", ""))
    libdir = Path(manifest.get("libdir", ""))
    ldlibrary = manifest.get("ldlibrary", "")
    instsoname = manifest.get("instsoname", "")

    if not version or not stdlib.exists() or not prefix.exists():
        raise SystemExit(f"Cannot bundle python runtime (stdlib missing): {stdlib}")

    usr_bin = appdir / "usr" / "bin"
    usr_lib = appdir / "usr" / "lib"
    usr_bin.mkdir(parents=True, exist_ok=True)
    usr_lib.mkdir(parents=True, exist_ok=True)

    def rel_under_prefix(path: Path) -> Path:
        try:
            return path.relative_to(prefix)
        except Exception:
            # Fallback: keep our previous lib layout.
            return Path("lib") / f"python{version}"

    # Interpreter
    py_src = Path(python_exe())
    py_dst = usr_bin / "python3"
    shutil.copy2(py_src, py_dst)
    _chmod_x(py_dst)

    # Standard library (pure + platform stdlib). Some distros use lib64.
    # Place stdlib in the same relative location under prefix so the bundled
    # interpreter can find it via PYTHONHOME.
    std_rel = rel_under_prefix(stdlib)
    dst_stdlib = appdir / "usr" / std_rel
    if dst_stdlib.exists():
        shutil.rmtree(dst_stdlib)
    dst_stdlib.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(stdlib, dst_stdlib, symlinks=False)

    if platstdlib != stdlib and platstdlib.exists():
        plat_rel = rel_under_prefix(platstdlib)
        dst_plat = appdir / "usr" / plat_rel
        if not dst_plat.exists():
            dst_plat.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(platstdlib, dst_plat, symlinks=False)

    # libpython (if the interpreter is dynamically linked against it)
    # Prefer INSTSONAME (libpython3.x.so.1.0) over LDLIBRARY (libpython3.x.so)
    # because the latter may be a missing symlink on some distros.
    lib_candidates = [instsoname, ldlibrary] if instsoname else [ldlibrary]
    lib_src: Path | None = None
    for candidate in lib_candidates:
        if candidate and libdir.exists():
            maybe = libdir / candidate
            if maybe.exists():
                lib_src = maybe
                break

    if lib_src is not None:
        lib_rel = rel_under_prefix(lib_src)
        lib_dst = appdir / "usr" / lib_rel
        lib_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lib_src, lib_dst)

        # Also place a copy in usr/lib so the dynamic loader can find it
        # via our simpler LD_LIBRARY_PATH.
        flat_dst = appdir / "usr" / "lib" / lib_src.name
        if flat_dst != lib_dst:
            flat_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(lib_src, flat_dst)


def _bundle_pygobject(*, appdir: Path, site_packages: Path) -> None:
    """Best-effort bundle of PyGObject (gi) for tray/AppIndicator support.

    We do not attempt to fully vendor GTK; instead we bundle the Python bindings
    plus typelibs so pystray can use AppIndicator on desktop environments.
    """

    code = r"""
import json
import sysconfig
paths = sysconfig.get_paths()
print(json.dumps({
    "purelib": paths.get("purelib") or "",
    "platlib": paths.get("platlib") or "",
}))
"""
    proc = subprocess.run(
        [python_exe(), "-c", code],
        cwd=str(repo_root()),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return

    try:
        data = json.loads(proc.stdout)
    except Exception:
        return

    candidates: list[Path] = []
    for k in ("purelib", "platlib"):
        v = str(data.get(k, "") or "")
        if v:
            candidates.append(Path(v))

    # Also consider system Python dist-packages. On Ubuntu runners we install
    # python3-gi via apt which lives here (and matches the system CPython ABI).
    candidates.extend(
        [
            Path("/usr/lib/python3/dist-packages"),
            Path("/usr/lib/python3.12/dist-packages"),
        ]
    )

    gi_src: Path | None = None
    for base in candidates:
        maybe = base / "gi"
        if maybe.exists() and maybe.is_dir():
            gi_src = maybe
            break

    if gi_src is None:
        # No PyGObject in the build env.
        return

    gi_dst = site_packages / "gi"
    if gi_dst.exists():
        shutil.rmtree(gi_dst)
    shutil.copytree(gi_src, gi_dst, symlinks=False)

    # Bundle typelibs (girepository). Prefer the multiarch path when present.
    # This is necessary for Gtk/AppIndicator introspection at runtime.
    typelib_src_candidates = [
        Path("/usr/lib/x86_64-linux-gnu/girepository-1.0"),
        Path("/usr/lib64/girepository-1.0"),
        Path("/usr/lib/girepository-1.0"),
    ]
    typelib_src = next((p for p in typelib_src_candidates if p.exists()), None)
    if typelib_src is not None:
        typelib_dst = appdir / "usr" / "lib" / "girepository-1.0"
        typelib_dst.mkdir(parents=True, exist_ok=True)
        # Copy a focused subset to keep size reasonable.
        for name in typelib_src.glob("*.typelib"):
            if name.name.startswith(
                (
                    "Gtk-",
                    "Gdk-",
                    "GdkPixbuf-",
                    "Gio-",
                    "GLib-",
                    "GObject-",
                    "Pango-",
                    "PangoCairo-",
                    "cairo-",
                    "AppIndicator3-",
                    "AyatanaAppIndicator3-",
                )
            ):
                shutil.copy2(name, typelib_dst / name.name)


def build_appimage() -> Path:
    root = repo_root()
    dist = root / "dist"
    tools = dist / "tools"
    work = dist / "appimage"

    appdir = work / "KeyRGB.AppDir"
    out = dist / "keyrgb-x86_64.AppImage"

    appimagetool = tools / "appimagetool-x86_64.AppImage"

    if appdir.exists():
        shutil.rmtree(appdir)
    work.mkdir(parents=True, exist_ok=True)

    # Download appimagetool if needed.
    if not appimagetool.exists():
        print(f"Downloading appimagetool -> {appimagetool}")
        _download(APPIMAGETOOL_URL, appimagetool)
        _chmod_x(appimagetool)

    # Layout
    _bundle_python_runtime(appdir=appdir)

    lib_root = appdir / "usr" / "lib" / "keyrgb"
    site_packages = lib_root / "site-packages"
    src_dst = lib_root / "src"

    shutil.copytree(root / "src", src_dst)

    # Bundle GUI assets that are loaded from repo-relative paths.
    # The GUI resolves `assets/...` relative to `usr/lib/keyrgb` inside the AppImage.
    assets_dst = lib_root / "assets"
    assets_dst.mkdir(parents=True, exist_ok=True)

    deck_src = root / "assets" / "y15-pro-deck.png"
    if deck_src.exists():
        shutil.copy2(deck_src, assets_dst / deck_src.name)

    # Bundle python deps (pip wheels) into the AppDir.
    # We still use the system python interpreter at runtime.
    site_packages.mkdir(parents=True, exist_ok=True)

    req = root / "requirements.txt"
    if req.exists():
        _run_checked(
            [python_exe(), "-m", "pip", "install", "-r", str(req), "--target", str(site_packages)],
            cwd=root,
        )

    vendor_ite = root / "vendor" / "ite8291r3-ctl"
    if vendor_ite.exists():
        _run_checked(
            [
                python_exe(),
                "-m",
                "pip",
                "install",
                "--no-deps",
                str(vendor_ite),
                "--target",
                str(site_packages),
            ],
            cwd=root,
        )

    # Bundle PyGObject (gi) when available in the build env so pystray can use
    # AppIndicator without relying on the user's system Python packages.
    _bundle_pygobject(appdir=appdir, site_packages=site_packages)

    # Desktop + icon expected by appimagetool.
    icon_src = root / "assets" / "logo-keyrgb.png"
    if not icon_src.exists():
        raise SystemExit(f"Missing icon: {icon_src}")

    shutil.copy2(icon_src, appdir / "keyrgb.png")

    _write_text(
        appdir / "keyrgb.desktop",
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Name=KeyRGB",
                "Comment=RGB Keyboard Controller",
                "Exec=keyrgb",
                "Icon=keyrgb",
                "Terminal=false",
                "Categories=Utility;System;",
                "StartupNotify=false",
                "",
            ]
        ),
    )

    # AppRun: uses the bundled python to avoid system-python ABI mismatches.
    # Prefer AppIndicator/Gtk when possible; we bundle PyGObject (gi) when
    # available at build time and provide typelibs via GI_TYPELIB_PATH.
    apprun = "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            'HERE="$(dirname "$(readlink -f "$0")")"',
            'export PYTHONHOME="$HERE/usr"',
            'export PYTHONNOUSERSITE="1"',
            'export PYTHONPATH="$HERE/usr/lib/keyrgb:$HERE/usr/lib/keyrgb/site-packages"',
            'export LD_LIBRARY_PATH="$HERE/usr/lib:$HERE/usr/lib64:$HERE/usr/lib/x86_64-linux-gnu:$HERE/usr/lib64/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"',
            'export GI_TYPELIB_PATH="$HERE/usr/lib/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"',
            'exec "$HERE/usr/bin/python3" -B -m src.tray "$@"',
            "",
        ]
    )
    _write_text(appdir / "AppRun", apprun)
    _chmod_x(appdir / "AppRun")

    # Build the AppImage.
    if out.exists():
        out.unlink()

    env = {"APPIMAGE_EXTRACT_AND_RUN": "1", "ARCH": "x86_64"}
    _run_checked(
        [str(appimagetool), "--appimage-extract-and-run", str(appdir), str(out)],
        cwd=root,
        env=env,
    )

    if not out.exists():
        raise SystemExit(f"AppImage build did not produce: {out}")

    print(f"Built AppImage: {out}")
    return out


def main() -> int:
    build_appimage()
    return 0


def appimage_build_runner() -> RunResult:
    root = repo_root()
    return run(
        [python_exe(), "-m", "buildpython.steps.step_appimage"],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )


if __name__ == "__main__":
    raise SystemExit(main())
