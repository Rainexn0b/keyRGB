from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ExperimentalBackendsPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_experimental_backends: tk.BooleanVar,
        on_toggle: callable,
    ) -> None:
        title = ttk.Label(parent, text="Backend policy", font=("Sans", 11, "bold"))
        title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            parent,
            text=(
                "Experimental backends are opt-in. Some are speculative. Others are research-backed, "
                "which means KeyRGB has public protocol notes or reverse-engineering references, but the "
                "backend is still not broadly validated on user hardware. Use at your own risk."
            ),
            font=("Sans", 9),
            justify="left",
            wraplength=420,
        )
        desc.pack(anchor="w", pady=(0, 8))

        self.chk_experimental = ttk.Checkbutton(
            parent,
            text="Enable experimental backends (takes effect next launch)",
            variable=var_experimental_backends,
            command=on_toggle,
        )
        self.chk_experimental.pack(anchor="w")
