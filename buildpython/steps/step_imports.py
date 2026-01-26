from __future__ import annotations

import importlib
import importlib.util
import traceback

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
    return (
        importlib.util.find_spec("tkinter") is not None
        and importlib.util.find_spec("_tkinter") is not None
    )


def import_validation_runner() -> RunResult:
    failures: list[str] = []

    has_tk = _has_tkinter()

    for mod in DEFAULT_IMPORTS:
        if not has_tk and mod.startswith("src.gui."):
            continue
        try:
            importlib.import_module(mod)
        except Exception as exc:
            failures.append(f"Failed to import {mod}: {exc}\n{traceback.format_exc()}")

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
            + "\n".join(
                f"  - {m}"
                for m in DEFAULT_IMPORTS
                if has_tk or not m.startswith("src.gui.")
            )
            + ("\n\n(Note: Tkinter not available; skipped Tk GUI imports.)\n" if not has_tk else "\n")
        ),
        stderr="",
        exit_code=0,
    )
