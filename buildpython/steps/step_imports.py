from __future__ import annotations

import importlib.util

from ..utils.import_probe import probe_module_import
from ..utils.paths import repo_root
from ..utils.subproc import RunResult


DEFAULT_IMPORTS = [
    "src.tray.entrypoint",
    # Tk-based GUIs are optional in CI environments where tkinter isn't present.
    "src.gui.perkey",
    "src.gui.calibrator",
]


def _has_tkinter() -> bool:
    # Some CI Python builds (notably certain 3.10 toolcache builds) may not ship
    # with tkinter / _tkinter, even if the rest of the stdlib is present.
    return importlib.util.find_spec("tkinter") is not None and importlib.util.find_spec("_tkinter") is not None


def import_validation_runner() -> RunResult:
    failures: list[str] = []
    root = repo_root()

    has_tk = _has_tkinter()

    for mod in DEFAULT_IMPORTS:
        if not has_tk and mod.startswith("src.gui."):
            continue
        probe = probe_module_import(mod, cwd=root)
        if not probe.ok:
            failures.append(f"Failed to import {mod}: {probe.error_message}\n{probe.stderr}")

    if failures:
        return RunResult(
            command_str="(internal) import validation",
            stdout="\n".join(failures) + "\n",
            stderr="",
            exit_code=1,
        )

    return RunResult(
        command_str="(internal) import validation",
        stdout=(
            "All imports OK:\n"
            + "\n".join(f"  - {m}" for m in DEFAULT_IMPORTS if has_tk or not m.startswith("src.gui."))
            + ("\n\n(Note: Tkinter not available; skipped Tk GUI imports.)\n" if not has_tk else "\n")
        ),
        stderr="",
        exit_code=0,
    )
