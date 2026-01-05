from __future__ import annotations

import webbrowser
from typing import Callable

import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk

from ..diagnostics_runner import collect_diagnostics_text
from src.gui.utils.tk_async import run_in_thread


class DiagnosticsPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        root: tk.Misc,
        get_status_label: Callable[[], ttk.Label],
        bg_color: str,
        fg_color: str,
    ) -> None:
        self._root = root
        self._get_status_label = get_status_label
        self._bg_color = bg_color
        self._fg_color = fg_color

        self._diagnostics_json: str = ""

        title = ttk.Label(parent, text="Diagnostics", font=("Sans", 11, "bold"))
        title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            parent,
            text=(
                "Collect read-only system information to include in bug reports.\n"
                "This works even if hardware detection fails."
            ),
            font=("Sans", 9),
        )
        desc.pack(anchor="w", pady=(0, 8))

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=(0, 8))

        self.btn_run_diagnostics = ttk.Button(btn_row, text="Run diagnostics", command=self.run_diagnostics)
        self.btn_run_diagnostics.pack(side="left")

        self.btn_copy_diagnostics = ttk.Button(btn_row, text="Copy output", command=self.copy_output)
        self.btn_copy_diagnostics.pack(side="left", padx=(8, 0))

        self.btn_open_issue = ttk.Button(btn_row, text="Open issue", command=self.open_issue_form)
        self.btn_open_issue.pack(side="left", padx=(8, 0))

        self.txt_diagnostics = scrolledtext.ScrolledText(
            parent,
            height=8,
            wrap="word",
            background=self._bg_color,
            foreground=self._fg_color,
            insertbackground=self._fg_color,
        )
        self.txt_diagnostics.pack(fill="both", expand=True)
        self.txt_diagnostics.insert(
            "1.0",
            "Click 'Run diagnostics', then use 'Copy output' or 'Open issue'.\n",
        )
        self.txt_diagnostics.configure(state="disabled")

        self.apply_state()

    def _status(self) -> ttk.Label | None:
        try:
            return self._get_status_label()
        except Exception:
            return None

    def apply_state(self) -> None:
        self.btn_copy_diagnostics.configure(state="normal" if self._diagnostics_json else "disabled")

    def _set_text(self, text: str) -> None:
        self.txt_diagnostics.configure(state="normal")
        self.txt_diagnostics.delete("1.0", "end")
        self.txt_diagnostics.insert("1.0", text)
        self.txt_diagnostics.configure(state="disabled")

    def run_diagnostics(self) -> None:
        status = self._status()
        if status is not None:
            status.configure(text="Collecting diagnostics…")
        self.btn_run_diagnostics.configure(state="disabled")
        self.btn_copy_diagnostics.configure(state="disabled")

        def work() -> str:
            try:
                return collect_diagnostics_text(include_usb=True)
            except Exception as e:
                return f"Failed to collect diagnostics: {e}"

        def on_done(text: str) -> None:
            self._diagnostics_json = text if text.strip().startswith("{") else ""
            self._set_text(text)
            self.btn_run_diagnostics.configure(state="normal")
            self.apply_state()

            status2 = self._status()
            if status2 is not None:
                if '"warnings"' in text:
                    status2.configure(text="⚠ Diagnostics ready (warnings)")
                else:
                    status2.configure(text="✓ Diagnostics ready")
                self._root.after(2000, lambda: status2.configure(text=""))

        run_in_thread(self._root, work, on_done)

    def copy_output(self) -> None:
        status = self._status()
        if not self._diagnostics_json:
            if status is not None:
                status.configure(text="Run diagnostics first")
                self._root.after(1500, lambda: status.configure(text=""))
            return

        try:
            self._root.clipboard_clear()
            self._root.clipboard_append(self._diagnostics_json)
        except Exception:
            pass

        if status is not None:
            status.configure(text="✓ Copied to clipboard")
            self._root.after(1500, lambda: status.configure(text=""))

    def open_issue_form(self) -> None:
        url = "https://github.com/Rainexn0b/keyRGB/issues/new/choose"
        try:
            ok = bool(webbrowser.open(url, new=2))
        except Exception:
            ok = False

        status = self._status()
        if ok:
            if status is not None:
                status.configure(text="Opened issue form")
        else:
            try:
                self._root.clipboard_clear()
                self._root.clipboard_append(url)
            except Exception:
                pass
            if status is not None:
                status.configure(text="Couldn't open browser (URL copied)")

        if status is not None:
            self._root.after(2000, lambda: status.configure(text=""))


__all__ = ["DiagnosticsPanel"]
