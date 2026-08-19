from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ._wrap_sync import bind_wraplength_sync


class ExperimentalBackendsPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_experimental_backends: tk.BooleanVar,
        on_toggle: Callable[[], None],
    ) -> None:
        title = ttk.Label(parent, text="Backend policy", font=("Sans", 11, "bold"))
        title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            parent,
            text=(
                "Experimental backends are opt-in. Some are speculative; others have protocol notes or "
                "reverse-engineering references but still need broader user validation."
            ),
            font=("Sans", 9),
            justify="left",
            wraplength=420,
        )
        desc.pack(anchor="w", fill="x", pady=(0, 8))
        bind_wraplength_sync(parent, [desc])

        self.chk_experimental = ttk.Checkbutton(
            parent,
            text="Enable experimental backends (takes effect next launch)",
            variable=var_experimental_backends,
            command=on_toggle,
        )
        self.chk_experimental.pack(anchor="w")
