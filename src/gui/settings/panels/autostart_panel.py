from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class AutostartPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_autostart: tk.BooleanVar,
        var_os_autostart: tk.BooleanVar,
        on_toggle: callable,
    ) -> None:
        as_title = ttk.Label(parent, text="Autostart", font=("Sans", 11, "bold"))
        as_title.pack(anchor="w", pady=(0, 6))

        as_desc = ttk.Label(
            parent,
            text=(
                "Control what happens when KeyRGB launches, and whether it\n"
                "starts automatically when you log in."
            ),
            font=("Sans", 9),
        )
        as_desc.pack(anchor="w", pady=(0, 8))

        self.chk_autostart = ttk.Checkbutton(
            parent,
            text="Start lighting on launch",
            variable=var_autostart,
            command=on_toggle,
        )
        self.chk_autostart.pack(anchor="w")

        self.chk_os_autostart = ttk.Checkbutton(
            parent,
            text="Start KeyRGB on login",
            variable=var_os_autostart,
            command=on_toggle,
        )
        self.chk_os_autostart.pack(anchor="w", pady=(6, 0))
