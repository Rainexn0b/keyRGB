from __future__ import annotations

import logging
from collections.abc import Callable
from tkinter import TclError
from typing import Protocol

from keyrgb.gui.calibrator.launch import launch_keymap_calibrator

from .status import calibrator_failed, calibrator_started, set_status

logger = logging.getLogger(__name__)


class _StatusLabelProtocol(Protocol):
    def config(self, *, text: str) -> None: ...


class _RootProtocol(Protocol):
    def after(self, delay_ms: int, callback: Callable[[], None]) -> object: ...

    def winfo_exists(self) -> int: ...


class _ProcessProtocol(Protocol):
    def poll(self) -> int | None: ...


class _CalibratorEditorProtocol(Protocol):
    root: _RootProtocol
    status_label: _StatusLabelProtocol

    def _reload_keymap(self) -> None: ...


_CALIBRATOR_LAUNCH_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_TK_TEARDOWN_ERRORS = (RuntimeError, TclError)
_CALIBRATOR_POLL_MS = 250


def _reload_keymap_when_calibrator_exits(
    editor: _CalibratorEditorProtocol,
    process: _ProcessProtocol,
) -> None:
    try:
        if not bool(editor.root.winfo_exists()):
            return
    except _TK_TEARDOWN_ERRORS as exc:
        logger.debug("Stopping calibrator polling after editor teardown: %s", exc)
        return
    if process.poll() is None:
        editor.root.after(
            _CALIBRATOR_POLL_MS,
            lambda: _reload_keymap_when_calibrator_exits(editor, process),
        )
        return
    editor._reload_keymap()


def run_keymap_calibrator_ui(
    editor: _CalibratorEditorProtocol,
    *,
    launch_fn: Callable[[], _ProcessProtocol] = launch_keymap_calibrator,
) -> None:
    """Launch the keymap calibrator and report status.

    No UX change: preserves the prior behavior and messages from
    `PerKeyEditor._run_calibrator`.
    """

    try:
        process = launch_fn()
        set_status(editor, calibrator_started())
        editor.root.after(
            _CALIBRATOR_POLL_MS,
            lambda: _reload_keymap_when_calibrator_exits(editor, process),
        )
    except _CALIBRATOR_LAUNCH_ERRORS as exc:
        set_status(editor, calibrator_failed(exc))
