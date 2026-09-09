from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from keyrgb.gui.theme import metrics as theme_metrics

from ._wrap_sync import bind_wraplength_sync


class AutostartPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_autostart: tk.BooleanVar,
        var_os_autostart: tk.BooleanVar,
        on_toggle: Callable[[], None],
    ) -> None:
        as_title = ttk.Label(parent, text="Autostart", style=theme_metrics.SECTION_LABEL_STYLE)
        as_title.pack(anchor="w", pady=(0, theme_metrics.CONTROL_GAP_Y))

        as_desc = ttk.Label(
            parent,
            text="Control what happens when KeyRGB launches, and whether it starts automatically when you log in.",
            style=theme_metrics.BODY_LABEL_STYLE,
            justify="left",
            wraplength=420,
        )
        as_desc.pack(anchor="w", fill="x", pady=(0, theme_metrics.CONTROL_GAP_Y))
        bind_wraplength_sync(parent, [as_desc])

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
        self.chk_os_autostart.pack(anchor="w", pady=(theme_metrics.CONTROL_GAP_Y, 0))
