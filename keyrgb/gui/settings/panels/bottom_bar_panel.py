from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from keyrgb.gui.theme import metrics as theme_metrics

_WRAPLENGTH_SYNC_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_TK_CALLBACK_SETUP_ERRORS = (RuntimeError, tk.TclError)


class BottomBarPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        on_close: Callable[[], None],
    ) -> None:
        self.frame = ttk.Frame(parent, padding=(16, 8, 16, 12))
        try:
            self.frame.columnconfigure(0, weight=1)
        except _TK_CALLBACK_SETUP_ERRORS:
            pass

        self.hardware_hint = ttk.Label(
            self.frame,
            text="",
            style=theme_metrics.STATUS_LABEL_STYLE,
            wraplength=820,
            justify="left",
            anchor="w",
        )
        self._hardware_hint_packed = False

        self.status = ttk.Label(self.frame, text="", style=theme_metrics.STATUS_LABEL_STYLE)
        self.status.grid(row=0, column=1, sticky="w")

        # Close stays on the default button style: Settings autosaves, so
        # there is no primary save action and nothing destructive here.
        self.close_btn = ttk.Button(self.frame, text="Close", command=on_close)
        self.close_btn.grid(row=0, column=2, sticky="e", padx=(theme_metrics.OUTER_PAD_X, 0))

        def _sync_wraplength(_e=None) -> None:
            try:
                # Reserve space for the Close button + status, plus padding.
                w = int(self.frame.winfo_width())
                if w <= 1:
                    return
                self.hardware_hint.configure(wraplength=max(200, w - 260))
            except _WRAPLENGTH_SYNC_ERRORS:
                return

        try:
            self.frame.bind("<Configure>", _sync_wraplength)
        except _TK_CALLBACK_SETUP_ERRORS:
            pass
        try:
            self.frame.after(0, _sync_wraplength)
        except _TK_CALLBACK_SETUP_ERRORS:
            pass

    def set_hardware_hint(self, text: str) -> None:
        text = text or ""
        if text.strip():
            self.hardware_hint.configure(text=text)
            if not self._hardware_hint_packed:
                self.hardware_hint.grid(row=0, column=0, sticky="ew", padx=(0, theme_metrics.OUTER_PAD_X))
                self._hardware_hint_packed = True
            return

        self.hardware_hint.configure(text="")
        if self._hardware_hint_packed:
            self.hardware_hint.grid_remove()
            self._hardware_hint_packed = False
