from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult, run


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
        msg = "Docker not found; skipping AppImage smoke test."
        if on_ci and not _is_truthy(os.environ.get("KEYRGB_ALLOW_NO_DOCKER")):
            return RunResult(
                command_str="appimage-smoke",
                stdout="",
                stderr=msg + "\n",
                exit_code=2,
            )
        return RunResult(command_str="appimage-smoke", stdout=msg + "\n", stderr="", exit_code=0)

    if _is_truthy(os.environ.get("KEYRGB_SKIP_APPIMAGE_SMOKE")):
        return RunResult(
            command_str="appimage-smoke",
            stdout="Skipping AppImage smoke test (KEYRGB_SKIP_APPIMAGE_SMOKE).\n",
            stderr="",
            exit_code=0,
        )

    # Use a minimal base image with essentially no desktop/python deps.
    image = os.environ.get("KEYRGB_APPIMAGE_SMOKE_IMAGE", "ubuntu:24.04")

    # The smoke test avoids running the tray (it would hang). Instead, it extracts
    # the AppImage and validates imports using the bundled Python + bundled libs.
    script = "\n".join(
        [
            "set -euo pipefail",
            "cp /dist/keyrgb-x86_64.AppImage ./keyrgb.AppImage",
            "chmod +x ./keyrgb.AppImage",
            "./keyrgb.AppImage --appimage-extract >/dev/null",
            "HERE=\"$PWD/squashfs-root\"",
            "export PYTHONHOME=\"$HERE/usr\"",
            "export PYTHONNOUSERSITE=\"1\"",
            "export PYTHONPATH=\"$HERE/usr/lib/keyrgb:$HERE/usr/lib/keyrgb/site-packages\"",
            "export LD_LIBRARY_PATH=\"$HERE/usr/lib:$HERE/usr/lib64:$HERE/usr/lib/x86_64-linux-gnu:$HERE/usr/lib64/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\"",
            "export TCL_LIBRARY=\"$HERE/usr/lib/tcl8.6\"",
            "export TK_LIBRARY=\"$HERE/usr/lib/tk8.6\"",
            "PY=\"$HERE/usr/bin/python3\"",
            # Ensure _tkinter can load and Tcl can initialize (covers missing libtk/libtcl/init.tcl).
            "\"$PY\" -c \"import tkinter as tk; t=tk.Tcl(); t.eval('info patchlevel'); print('tcl-ok')\"",
            "\"$PY\" -c \"import _tkinter; print('_tkinter-ok')\"",
            # Import a tray-adjacent module that historically pulled in tkinter/theme logic.
            "\"$PY\" -c \"import src.tray.ui.icon; print('tray-icon-import-ok')\"",
            # Diagnostics should run without requiring system deps.
            "\"$PY\" -m src.core.diagnostics > diag.json",
            "\"$PY\" -c \"import json; json.load(open('diag.json')); print('diagnostics-json-ok')\"",
            "echo 'appimage-smoke-ok'",
        ]
    )

    return run(
        [
            docker,
            "run",
            "--rm",
            "-v",
            f"{dist}:/dist:ro",
            "-w",
            "/work",
            image,
            "bash",
            "-lc",
            script,
        ],
        cwd=str(root),
        env_overrides={"KEYRGB_HW_TESTS": "0"},
    )
