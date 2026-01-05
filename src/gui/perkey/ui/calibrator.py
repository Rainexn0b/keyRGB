from __future__ import annotations

from typing import Any, Callable

from src.gui.calibrator.launch import launch_keymap_calibrator

from .status import calibrator_failed, calibrator_started, set_status


def run_keymap_calibrator_ui(editor: Any, *, launch_fn: Callable[[], None] = launch_keymap_calibrator) -> None:
    """Launch the keymap calibrator and report status.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._run_calibrator`.
    """

    try:
        launch_fn()
        set_status(editor, calibrator_started())
    except Exception as exc:
        set_status(editor, calibrator_failed(exc))
