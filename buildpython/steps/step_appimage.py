from __future__ import annotations

import shutil
from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, python_exe, run
from .appimage import (
    bundle_libappindicator,
    bundle_pygobject,
    bundle_python_runtime,
    bundle_tkinter,
    chmod_x,
    download,
    env_flag,
    run_checked,
    write_text,
)


APPIMAGETOOL_URL = "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"


def build_appimage() -> Path:
    root = repo_root()
    dist = root / "dist"
    tools = dist / "tools"
    work = dist / "appimage"

    appdir = work / "KeyRGB.AppDir"
    out = dist / "keyrgb-x86_64.AppImage"

    appimagetool = tools / "appimagetool-x86_64.AppImage"

    # Some environments (especially bleeding-edge Python builds) can't build
    # native deps like `evdev` without kernel headers, which blocks full
    # AppImage construction. These flags let us still refresh the staged AppDir
    # (and therefore bundled sources/launchers) for local testing.
    staging_only = env_flag("KEYRGB_APPIMAGE_STAGING_ONLY")
    skip_deps = staging_only or env_flag("KEYRGB_APPIMAGE_SKIP_DEPS")

    if appdir.exists():
        shutil.rmtree(appdir)
    work.mkdir(parents=True, exist_ok=True)

    # Download appimagetool if needed.
    if not appimagetool.exists():
        print(f"Downloading appimagetool -> {appimagetool}")
        download(APPIMAGETOOL_URL, appimagetool)
        chmod_x(appimagetool)

    # Layout
    bundle_python_runtime(appdir=appdir)
    bundle_tkinter(appdir=appdir)
    bundle_libappindicator(appdir=appdir)

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

    tray_logo_src = root / "assets" / "logo-tray.png"
    if tray_logo_src.exists():
        shutil.copy2(tray_logo_src, assets_dst / tray_logo_src.name)

    # Bundle python deps (pip wheels) into the AppDir.
    # We still use the system python interpreter at runtime.
    site_packages.mkdir(parents=True, exist_ok=True)

    if not skip_deps:
        req = root / "requirements.txt"
        if req.exists():
            run_checked(
                [
                    python_exe(),
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(req),
                    "--target",
                    str(site_packages),
                ],
                cwd=root,
            )

        vendor_ite = root / "vendor" / "ite8291r3-ctl"
        if vendor_ite.exists():
            run_checked(
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
        bundle_pygobject(appdir=appdir, site_packages=site_packages)

    # Desktop + icon expected by appimagetool.
    icon_src = root / "assets" / "logo-keyrgb.png"
    if not icon_src.exists():
        raise SystemExit(f"Missing icon: {icon_src}")

    shutil.copy2(icon_src, appdir / "keyrgb.png")

    write_text(
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
    # Set TCL_LIBRARY and TK_LIBRARY so bundled tkinter can find init.tcl and support scripts.
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
            'export TCL_LIBRARY="$HERE/usr/lib/tcl8.6"',
            'export TK_LIBRARY="$HERE/usr/lib/tk8.6"',
            'exec "$HERE/usr/bin/python3" -B -m src.tray "$@"',
            "",
        ]
    )
    write_text(appdir / "AppRun", apprun)
    chmod_x(appdir / "AppRun")

    if staging_only:
        print(f"Prepared AppDir (staging-only): {appdir}")
        return appdir

    # Build the AppImage.
    if out.exists():
        out.unlink()

    env = {"APPIMAGE_EXTRACT_AND_RUN": "1", "ARCH": "x86_64"}
    run_checked(
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
