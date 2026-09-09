"""Best-effort initial keyboard-focus scheduling for main windows.

UX-05 gives every main window an intentional initial focus target without
forcing focus across applications: focus is scheduled with ``after`` so the
window can map first, never takes a grab, and never steals focus that
already landed on another child. All Tk teardown races fail softly with a
debug log.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)

INITIAL_FOCUS_DELAY_MS = 50


class _FocusRoot(Protocol):
    def after(self, delay_ms: int, callback: Callable[[], object]) -> object: ...

    def focus_get(self) -> object | None: ...


class _FocusTarget(Protocol):
    def focus_set(self) -> object: ...


def schedule_initial_focus(
    root: _FocusRoot,
    target: _FocusTarget,
    *,
    delay_ms: int = INITIAL_FOCUS_DELAY_MS,
) -> None:
    """Schedule keyboard focus on ``target`` after ``delay_ms``.

    This never blocks, never forces cross-application focus, and never
    grabs. If the window already has focus on another child when the
    callback fires, ``target`` is left alone.
    """

    try:
        root.after(delay_ms, lambda: _apply_initial_focus(root, target))
    except (tk.TclError, RuntimeError) as exc:
        logger.debug("Initial focus could not be scheduled: %s", exc)


def _apply_initial_focus(root: _FocusRoot, target: _FocusTarget) -> None:
    try:
        current = root.focus_get()
    except (tk.TclError, RuntimeError) as exc:
        logger.debug("Initial focus check failed (window may be closed): %s", exc)
        return
    # A toplevel may initially report itself as focused before Tk assigns a
    # useful child target. Preserve any child focus, but replace root-only
    # focus with the intentional first control.
    if current is not None and current is not root:
        return
    try:
        target.focus_set()
    except (tk.TclError, RuntimeError) as exc:
        logger.debug("Initial focus target unavailable: %s", exc)


__all__ = ["INITIAL_FOCUS_DELAY_MS", "schedule_initial_focus"]
