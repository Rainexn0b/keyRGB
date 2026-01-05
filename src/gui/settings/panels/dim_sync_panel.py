from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import ttk


class DimSyncPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_dim_sync_enabled: tk.BooleanVar,
        var_dim_sync_mode: tk.StringVar,
        var_dim_temp_brightness: tk.DoubleVar,
        on_toggle: Callable[[], None],
    ) -> None:
        self.var_dim_sync_enabled = var_dim_sync_enabled
        self.var_dim_sync_mode = var_dim_sync_mode
        self.var_dim_temp_brightness = var_dim_temp_brightness
        self._on_toggle = on_toggle

        dim_title = ttk.Label(parent, text="Screen dim/brightness sync", font=("Sans", 11, "bold"))
        dim_title.pack(anchor="w", pady=(0, 6))

        dim_desc = ttk.Label(
            parent,
            text=(
                "Optionally react to your desktop's screen dimming/brightness changes\n"
                "(e.g. KDE brightness slider) by turning keyboard LEDs off or dimming\n"
                "them to a temporary brightness."
            ),
            font=("Sans", 9),
        )
        dim_desc.pack(anchor="w", pady=(0, 10))

        self.chk_dim_sync = ttk.Checkbutton(
            parent,
            text="Sync keyboard lighting with screen dimming/brightness",
            variable=self.var_dim_sync_enabled,
            command=self._on_toggle,
        )
        self.chk_dim_sync.pack(anchor="w", pady=(0, 8))

        dim_mode = ttk.Frame(parent)
        dim_mode.pack(fill="x")

        self.rb_dim_off = ttk.Radiobutton(
            dim_mode,
            text="When dimmed: turn off",
            value="off",
            variable=self.var_dim_sync_mode,
            command=self._on_toggle,
        )
        self.rb_dim_off.pack(anchor="w")

        dim_temp_row = ttk.Frame(dim_mode)
        dim_temp_row.pack(fill="x", pady=(6, 0))

        self.rb_dim_temp = ttk.Radiobutton(
            dim_temp_row,
            text="When dimmed: set brightness to",
            value="temp",
            variable=self.var_dim_sync_mode,
            command=self._on_toggle,
        )
        self.rb_dim_temp.pack(side="left", anchor="w")

        self.lbl_dim_temp_val = ttk.Label(
            dim_temp_row,
            text=str(int(float(self.var_dim_temp_brightness.get()))),
            font=("Sans", 9),
        )
        self.lbl_dim_temp_val.pack(side="right")

        self.scale_dim_temp = ttk.Scale(
            dim_mode,
            from_=1,
            to=50,
            orient="horizontal",
            variable=self.var_dim_temp_brightness,
            command=lambda v: self._set_label_int(self.lbl_dim_temp_val, v),
        )
        self.scale_dim_temp.pack(fill="x", pady=(6, 0))
        self.scale_dim_temp.bind("<ButtonRelease-1>", lambda _e: self._on_toggle())

    def apply_enabled_state(self, *, power_management_enabled: bool) -> None:
        state = "normal" if power_management_enabled else "disabled"
        for w in (
            self.chk_dim_sync,
            self.rb_dim_off,
            self.rb_dim_temp,
            self.scale_dim_temp,
        ):
            w.configure(state=state)

        if (
            power_management_enabled
            and bool(self.var_dim_sync_enabled.get())
            and str(self.var_dim_sync_mode.get()) == "temp"
        ):
            self.scale_dim_temp.configure(state="normal")
        else:
            self.scale_dim_temp.configure(state="disabled")

    @staticmethod
    def _set_label_int(lbl: ttk.Label, v: float | str) -> None:
        try:
            lbl.configure(text=str(int(float(v))))
        except Exception:
            lbl.configure(text="?")
