from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import ttk


class PowerSourcePanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_ac_enabled: tk.BooleanVar,
        var_battery_enabled: tk.BooleanVar,
        var_ac_brightness: tk.DoubleVar,
        var_battery_brightness: tk.DoubleVar,
        on_toggle: Callable[[], None],
    ) -> None:
        self._on_toggle = on_toggle

        ps_title = ttk.Label(parent, text="Plugged In vs Battery", font=("Sans", 11, "bold"))
        ps_title.pack(anchor="w", pady=(0, 6))

        ps_desc = ttk.Label(
            parent,
            text=(
                "Choose whether the keyboard lighting should be on/off and what\n"
                "brightness to use when plugged in vs running on battery."
            ),
            font=("Sans", 9),
        )
        ps_desc.pack(anchor="w", pady=(0, 10))

        # AC row
        ac_row = ttk.Frame(parent)
        ac_row.pack(fill="x", pady=(0, 10))
        ac_head = ttk.Frame(ac_row)
        ac_head.pack(fill="x")

        self.chk_ac_enabled = ttk.Checkbutton(
            ac_head,
            text="When plugged in (AC): enable lighting",
            variable=var_ac_enabled,
            command=self._on_toggle,
        )
        self.chk_ac_enabled.pack(side="left", anchor="w")

        self.lbl_ac_brightness_val = ttk.Label(
            ac_head,
            text=str(int(float(var_ac_brightness.get()))),
            font=("Sans", 9),
        )
        self.lbl_ac_brightness_val.pack(side="right")
        ttk.Label(ac_head, text="Brightness", font=("Sans", 9)).pack(side="right", padx=(0, 6))

        self.scale_ac_brightness = ttk.Scale(
            ac_row,
            from_=0,
            to=50,
            orient="horizontal",
            variable=var_ac_brightness,
            command=lambda v: self._set_label_int(self.lbl_ac_brightness_val, v),
        )
        self.scale_ac_brightness.pack(fill="x", pady=(6, 0))
        self.scale_ac_brightness.bind("<ButtonRelease-1>", lambda _e: self._on_toggle())

        # Battery row
        batt_row = ttk.Frame(parent)
        batt_row.pack(fill="x")
        batt_head = ttk.Frame(batt_row)
        batt_head.pack(fill="x")

        self.chk_battery_enabled = ttk.Checkbutton(
            batt_head,
            text="On battery: enable lighting",
            variable=var_battery_enabled,
            command=self._on_toggle,
        )
        self.chk_battery_enabled.pack(side="left", anchor="w")

        self.lbl_battery_brightness_val = ttk.Label(
            batt_head,
            text=str(int(float(var_battery_brightness.get()))),
            font=("Sans", 9),
        )
        self.lbl_battery_brightness_val.pack(side="right")
        ttk.Label(batt_head, text="Brightness", font=("Sans", 9)).pack(side="right", padx=(0, 6))

        self.scale_battery_brightness = ttk.Scale(
            batt_row,
            from_=0,
            to=50,
            orient="horizontal",
            variable=var_battery_brightness,
            command=lambda v: self._set_label_int(self.lbl_battery_brightness_val, v),
        )
        self.scale_battery_brightness.pack(fill="x", pady=(6, 0))
        self.scale_battery_brightness.bind("<ButtonRelease-1>", lambda _e: self._on_toggle())

    def apply_enabled_state(self, *, power_management_enabled: bool) -> None:
        state = "normal" if power_management_enabled else "disabled"
        for w in (
            self.chk_ac_enabled,
            self.chk_battery_enabled,
            self.scale_ac_brightness,
            self.scale_battery_brightness,
        ):
            w.configure(state=state)

    @staticmethod
    def _set_label_int(lbl: ttk.Label, v: float | str) -> None:
        try:
            lbl.configure(text=str(int(float(v))))
        except Exception:
            lbl.configure(text="?")
