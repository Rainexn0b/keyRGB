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
                "Validated backends are always eligible. Experimental backends stay\n"
                "off until you opt in. Dormant backends remain disabled."
            ),
            font=("Sans", 9),
        )
        desc.pack(anchor="w", pady=(0, 8))

        self.chk_experimental = ttk.Checkbutton(
            parent,
            text="Enable experimental backends (takes effect next launch)",
            variable=var_experimental_backends,
            command=on_toggle,
        )
        self.chk_experimental.pack(anchor="w")

        hint = ttk.Label(
            parent,
            text="Current plan: `ite8910` is experimental; `ite8297` remains dormant.",
            font=("Sans", 9),
        )
        hint.pack(anchor="w", pady=(6, 0))