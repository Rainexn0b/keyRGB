from __future__ import annotations

import importlib
import traceback

from ..utils.subproc import RunResult


DEFAULT_IMPORTS = [
    "src.tray_app",
    "src.gui_perkey",
    "src.gui_keymap_calibrator",
]


def import_validation_runner() -> RunResult:
    failures: list[str] = []

    for mod in DEFAULT_IMPORTS:
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
        stdout="All imports OK:\n" + "\n".join(f"  - {m}" for m in DEFAULT_IMPORTS) + "\n",
        stderr="",
        exit_code=0,
    )
