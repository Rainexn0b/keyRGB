from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import urllib.request
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
    lib_root = appdir / "usr" / "lib" / "keyrgb"
    site_packages = lib_root / "site-packages"
    src_dst = lib_root / "src"

    shutil.copytree(root / "src", src_dst)

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

    # AppRun: uses system python, but forces imports from bundled code + deps.
    apprun = "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            'HERE="$(dirname "$(readlink -f "$0")")"',
            'export PYTHONNOUSERSITE="1"',
            'export PYTHONPATH="$HERE/usr/lib/keyrgb:$HERE/usr/lib/keyrgb/site-packages"',
            'exec python3 -B -m src.tray "$@"',
            "",
        ]
    )
    _write_text(appdir / "AppRun", apprun)
    _chmod_x(appdir / "AppRun")

    # Build the AppImage.
    if out.exists():
        out.unlink()

    env = {"APPIMAGE_EXTRACT_AND_RUN": "1"}
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
