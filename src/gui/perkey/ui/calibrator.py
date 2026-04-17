from __future__ import annotations

from typing import Callable, Protocol

from src.gui.calibrator.launch import launch_keymap_calibrator

from .status import calibrator_failed, calibrator_started, set_status


class _StatusLabelProtocol(Protocol):
    def config(self, *, text: str) -> None: ...


class _CalibratorEditorProtocol(Protocol):
    status_label: _StatusLabelProtocol


_CALIBRATOR_LAUNCH_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def run_keymap_calibrator_ui(
    editor: _CalibratorEditorProtocol,
    *,
    launch_fn: Callable[[], None] = launch_keymap_calibrator,
) -> None:
    """Launch the keymap calibrator and report status.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._run_calibrator`.
    """

    try:
        launch_fn()
        set_status(editor, calibrator_started())
    except _CALIBRATOR_LAUNCH_ERRORS as exc:
        set_status(editor, calibrator_failed(exc))
