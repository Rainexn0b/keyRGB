"""Shared dynamic wraplength syncing for settings panel description labels.

Panels place description labels with a fixed initial ``wraplength``; without
syncing, that fixed value clips text whenever the settings window (and thus the
column) is narrower than the initial wrap. ``bind_wraplength_sync`` re-wraps
the given labels to the actual column width on ``<Configure>``.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable
from typing import Protocol

WRAP_SYNC_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)


class _WrapLabel(Protocol):
    # Only wraplength syncing is required; both tk.Label and ttk.Label accept
    # an int-valued wraplength keyword and return a value we ignore.
    def configure(self, *, wraplength: int) -> object: ...


def bind_wraplength_sync(
    parent: tk.Misc,
    labels: Iterable[_WrapLabel],
    *,
    min_wrap: int = 260,
    margin: int = 24,
) -> None:
    """Re-wrap ``labels`` to ``parent``'s live width (minus ``margin``).

    Best-effort: fake/headless parents without ``bind``/``winfo_width`` are
    tolerated so unit tests can pass plain objects.
    """

    label_list = list(labels)

    def _sync(_event: object = None) -> None:
        try:
            width = int(parent.winfo_width())
            if width <= 1:
                return
            wrap = max(int(min_wrap), width - int(margin))
            for label in label_list:
                label.configure(wraplength=wrap)
        except WRAP_SYNC_ERRORS:
            return

    try:
        parent.bind("<Configure>", _sync)
        parent.after(0, _sync)
    except WRAP_SYNC_ERRORS:
        pass
