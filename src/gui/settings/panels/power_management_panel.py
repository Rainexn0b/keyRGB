from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import ttk


class PowerManagementPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_enabled: tk.BooleanVar,
        var_off_suspend: tk.BooleanVar,
        var_restore_resume: tk.BooleanVar,
        var_off_lid: tk.BooleanVar,
        var_restore_lid: tk.BooleanVar,
        on_toggle: Callable[[], None],
    ) -> None:
        self._var_enabled = var_enabled

        pm_title = ttk.Label(parent, text="Power Management", font=("Sans", 11, "bold"))
        pm_title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            parent,
            text=(
                "Control whether KeyRGB turns the keyboard LEDs off/on\n"
                "when the lid closes/opens or the system suspends/resumes."
            ),
            font=("Sans", 9),
        )
        desc.pack(anchor="w", pady=(0, 12))

        self.chk_enabled = ttk.Checkbutton(
            parent,
            text="Enable power management",
            variable=var_enabled,
            command=on_toggle,
        )
        self.chk_enabled.pack(anchor="w", pady=(0, 8))

        self.chk_off_suspend = ttk.Checkbutton(
            parent,
            text="Turn off on suspend",
            variable=var_off_suspend,
            command=on_toggle,
        )
        self.chk_off_suspend.pack(anchor="w")

        self.chk_restore_resume = ttk.Checkbutton(
            parent,
            text="Restore on resume",
            variable=var_restore_resume,
            command=on_toggle,
        )
        self.chk_restore_resume.pack(anchor="w")

        self.chk_off_lid = ttk.Checkbutton(
            parent,
            text="Turn off on lid close",
            variable=var_off_lid,
            command=on_toggle,
        )
        self.chk_off_lid.pack(anchor="w", pady=(8, 0))

        self.chk_restore_lid = ttk.Checkbutton(
            parent,
            text="Restore on lid open",
            variable=var_restore_lid,
            command=on_toggle,
        )
        self.chk_restore_lid.pack(anchor="w")

    def apply_enabled_state(self) -> None:
        enabled = bool(self._var_enabled.get())
        state = "normal" if enabled else "disabled"
        for w in (
            self.chk_off_suspend,
            self.chk_restore_resume,
            self.chk_off_lid,
            self.chk_restore_lid,
        ):
            w.configure(state=state)
