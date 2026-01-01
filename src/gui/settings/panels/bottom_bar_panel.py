from __future__ import annotations

from collections.abc import Callable

from tkinter import ttk


class BottomBarPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        on_close: Callable[[], None],
    ) -> None:
        self.frame = ttk.Frame(parent, padding=(16, 8, 16, 12))

        self.status = ttk.Label(self.frame, text="", font=("Sans", 9))
        self.status.pack(side="left")

        self.close_btn = ttk.Button(self.frame, text="Close", command=on_close)
        self.close_btn.pack(side="right")
