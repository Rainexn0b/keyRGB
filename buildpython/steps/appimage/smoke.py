from __future__ import annotations

import os
import shutil

from ...utils.paths import repo_root
from ...utils.subproc import RunResult, run
from .tkinter_bundle import runtime_script_env_exports


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "y", "yes", "true", "on"}


def appimage_smoke_runner() -> RunResult:
    """Smoke-test the built AppImage inside a minimal container.

    Goal: catch missing bundled runtime deps (notably tkinter/Tcl/Tk) even when the
    host runner happens to have system packages installed.

    This runs via Docker on CI. Locally, it will skip if Docker isn't available.
    """

    root = repo_root()
    dist = root / "dist"
    appimage = dist / "keyrgb-x86_64.AppImage"

    if not appimage.exists():
        return RunResult(
            command_str="appimage-smoke",
            stdout="",
            stderr=f"AppImage not found: {appimage}\n",
            exit_code=2,
        )

    docker = shutil.which("docker")
    on_ci = _is_truthy(os.environ.get("CI")) or _is_truthy(os.environ.get("GITHUB_ACTIONS"))
    if docker is None:
        msg = "Docker not found; AppImage smoke test was not executed."
        if on_ci and not _is_truthy(os.environ.get("KEYRGB_ALLOW_NO_DOCKER")):
            return RunResult(
                command_str="appimage-smoke",
                stdout="",
                stderr=msg + "\n",
                exit_code=2,
            )
        return RunResult(command_str="appimage-smoke", stdout=msg + "\n", stderr="", exit_code=0, skip_reason=msg)

    if _is_truthy(os.environ.get("KEYRGB_SKIP_APPIMAGE_SMOKE")):
        return RunResult(
            command_str="appimage-smoke",
            stdout="Skipping AppImage smoke test (KEYRGB_SKIP_APPIMAGE_SMOKE).\n",
            stderr="",
            exit_code=0,
            skip_reason="KEYRGB_SKIP_APPIMAGE_SMOKE is enabled",
        )

    images = (
        (os.environ["KEYRGB_APPIMAGE_SMOKE_IMAGE"],)
        if os.environ.get("KEYRGB_APPIMAGE_SMOKE_IMAGE")
        else ("ubuntu:22.04", "ubuntu:24.04")
    )

    results: list[RunResult] = []
    for image in images:
        result = run(
            [docker, "run", "--rm", "-v", f"{dist}:/dist:ro", "-w", "/work", image, "bash", "-lc", _smoke_script()],
            cwd=str(root),
            env_overrides={"KEYRGB_HW_TESTS": "0"},
        )
        results.append(result)
        if result.exit_code != 0:
            break
    return RunResult(
        command_str="; ".join(result.command_str for result in results),
        stdout="".join(f"=== {image} ===\n{result.stdout}" for image, result in zip(images, results, strict=False)),
        stderr="".join(f"=== {image} ===\n{result.stderr}" for image, result in zip(images, results, strict=False)),
        exit_code=results[-1].exit_code,
    )


def _smoke_script() -> str:
    """Exercise minimal imports, then desktop startup without host GI/indicator packages."""
    tcl_export, tk_export = runtime_script_env_exports("$HERE")
    return "\n".join(
        [
            "set -euo pipefail",
            "export DEBIAN_FRONTEND=noninteractive",
            "apt-get update -qq",
            "apt-get install -y --no-install-recommends libfontconfig1 libfreetype6 >/dev/null",
            "cp /dist/keyrgb-x86_64.AppImage ./keyrgb.AppImage",
            "chmod +x ./keyrgb.AppImage",
            "./keyrgb.AppImage --appimage-extract >/dev/null",
            'HERE="$PWD/squashfs-root"',
            'export PYTHONHOME="$HERE/usr"',
            'export PYTHONNOUSERSITE="1"',
            'export PYTHONPATH="$HERE/usr/lib/keyrgb:$HERE/usr/lib/keyrgb/site-packages"',
            'export LD_LIBRARY_PATH="$HERE/usr/lib:$HERE/usr/lib64:$HERE/usr/lib/x86_64-linux-gnu:$HERE/usr/lib64/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"',
            'export GI_TYPELIB_PATH="$HERE/usr/lib/girepository-1.0"',
            tcl_export,
            tk_export,
            'PY="$HERE/usr/bin/python3"',
            "\"$PY\" -c \"import tkinter as tk; t=tk.Tcl(); t.eval('info patchlevel'); print('tcl-ok')\"",
            '"$PY" -c "import _tkinter; print(\'_tkinter-ok\')"',
            '"$PY" -c "import keyrgb.tray.ui.icon; print(\'tray-icon-import-ok\')"',
            '"$PY" -m keyrgb.core.diagnostics > diag.json',
            "\"$PY\" -c \"import json; json.load(open('diag.json')); print('diagnostics-json-ok')\"",
            # GTK/GLib and font rendering are the host desktop stack, deliberately
            # not bundled. Do NOT install python3-gi or any indicator/dbusmenu libs:
            # that would mask a broken bundle (the old smoke never imported GI).
            "apt-get install -y --no-install-recommends libgtk-3-0 libgirepository-1.0-1 xvfb xauth dbus-x11 >/dev/null",
            'export PYSTRAY_BACKEND="appindicator"',
            'export GDK_BACKEND="x11"',
            (
                'xvfb-run -a dbus-run-session -- "$PY" -c "import tkinter as tk; r=tk.Tk(); r.update(); r.destroy(); '
                "import pystray; from PIL import Image; assert pystray.Icon.__module__ == 'pystray._appindicator'; "
                "i=pystray.Icon('smoke', Image.new('RGB', (16,16))); print('desktop-tray-ok')\""
            ),
            'xvfb-run -a dbus-run-session -- "$HERE/AppRun" --diagnostics --no-usb > apprun-diag.json',
            "\"$PY\" -c \"import json; json.load(open('apprun-diag.json')); print('apprun-ok')\"",
            "echo 'appimage-smoke-ok'",
        ]
    )
