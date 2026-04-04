from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import ttk


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

        self.hardware_hint = ttk.Label(
            self.frame,
            text="",
            font=("Sans", 9),
            wraplength=820,
            justify="left",
            anchor="w",
        )
        self._hardware_hint_packed = False

        self.status = ttk.Label(self.frame, text="", font=("Sans", 9))
        self.status.pack(side="left")

        self.close_btn = ttk.Button(self.frame, text="Close", command=on_close)
        self.close_btn.pack(side="right")

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
                self.hardware_hint.pack(side="left", fill="x", expand=True, padx=(0, 12), before=self.status)
                self._hardware_hint_packed = True
            return

        self.hardware_hint.configure(text="")
        if self._hardware_hint_packed:
            self.hardware_hint.pack_forget()
            self._hardware_hint_packed = False
