from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import ttk


_LABEL_VALUE_ERRORS = (TypeError, ValueError, OverflowError)
_LABEL_WIDGET_ERRORS = (RuntimeError, tk.TclError)


class PowerSourcePanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_ac_enabled: tk.BooleanVar,
        var_battery_enabled: tk.BooleanVar,
        var_ac_brightness: tk.DoubleVar,
        var_battery_brightness: tk.DoubleVar,
        var_ac_power_mode: tk.StringVar,
        var_battery_power_mode: tk.StringVar,
        power_mode_options: tuple[str, ...],
        on_toggle: Callable[[], None],
    ) -> None:
        self._on_toggle = on_toggle

        ps_title = ttk.Label(parent, text="Plugged In vs Battery", font=("Sans", 11, "bold"))
        ps_title.pack(anchor="w", pady=(0, 6))

        ps_desc = ttk.Label(
            parent,
            text="Choose whether keyboard lighting stays on, and what brightness to use on AC and on battery.",
            font=("Sans", 9),
            justify="left",
            wraplength=400,
        )
        ps_desc.pack(anchor="w", fill="x", pady=(0, 8))

        # AC row
        ac_row = ttk.Frame(parent)
        ac_row.pack(fill="x", pady=(0, 8))
        ac_head = ttk.Frame(ac_row)
        ac_head.pack(fill="x")
        ac_head.columnconfigure(0, weight=1)

        self.chk_ac_enabled = ttk.Checkbutton(
            ac_head,
            text="When plugged in (AC): enable lighting",
            variable=var_ac_enabled,
            command=self._on_toggle,
        )
        self.chk_ac_enabled.grid(row=0, column=0, sticky="w")

        ttk.Label(ac_head, text="Brightness", font=("Sans", 9)).grid(row=0, column=1, sticky="e", padx=(12, 6))

        self.lbl_ac_brightness_val = ttk.Label(
            ac_head,
            text=str(int(float(var_ac_brightness.get()))),
            font=("Sans", 9),
        )
        self.lbl_ac_brightness_val.grid(row=0, column=2, sticky="e")

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

        ac_profile_row = ttk.Frame(ac_row)
        ac_profile_row.pack(fill="x", pady=(6, 0))
        ac_profile_row.columnconfigure(1, weight=1)

        ttk.Label(ac_profile_row, text="Power mode", font=("Sans", 9)).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.combo_ac_power_mode = ttk.Combobox(
            ac_profile_row,
            textvariable=var_ac_power_mode,
            values=power_mode_options,
            state="readonly",
        )
        self.combo_ac_power_mode.grid(row=0, column=1, sticky="ew")
        self.combo_ac_power_mode.bind("<<ComboboxSelected>>", lambda _e: self._on_toggle())

        # Battery row
        batt_row = ttk.Frame(parent)
        batt_row.pack(fill="x")
        batt_head = ttk.Frame(batt_row)
        batt_head.pack(fill="x")
        batt_head.columnconfigure(0, weight=1)

        self.chk_battery_enabled = ttk.Checkbutton(
            batt_head,
            text="On battery: enable lighting",
            variable=var_battery_enabled,
            command=self._on_toggle,
        )
        self.chk_battery_enabled.grid(row=0, column=0, sticky="w")

        ttk.Label(batt_head, text="Brightness", font=("Sans", 9)).grid(row=0, column=1, sticky="e", padx=(12, 6))

        self.lbl_battery_brightness_val = ttk.Label(
            batt_head,
            text=str(int(float(var_battery_brightness.get()))),
            font=("Sans", 9),
        )
        self.lbl_battery_brightness_val.grid(row=0, column=2, sticky="e")

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

        batt_profile_row = ttk.Frame(batt_row)
        batt_profile_row.pack(fill="x", pady=(6, 0))
        batt_profile_row.columnconfigure(1, weight=1)

        ttk.Label(batt_profile_row, text="Power mode", font=("Sans", 9)).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.combo_battery_power_mode = ttk.Combobox(
            batt_profile_row,
            textvariable=var_battery_power_mode,
            values=power_mode_options,
            state="readonly",
        )
        self.combo_battery_power_mode.grid(row=0, column=1, sticky="ew")
        self.combo_battery_power_mode.bind("<<ComboboxSelected>>", lambda _e: self._on_toggle())

    def apply_enabled_state(self, *, power_management_enabled: bool) -> None:
        state = "normal" if power_management_enabled else "disabled"
        combo_state = "readonly" if power_management_enabled else "disabled"
        for w in (
            self.chk_ac_enabled,
            self.chk_battery_enabled,
            self.scale_ac_brightness,
            self.scale_battery_brightness,
        ):
            w.configure(state=state)
        for w in (self.combo_ac_power_mode, self.combo_battery_power_mode):
            w.configure(state=combo_state)

    @staticmethod
    def _set_label_int(lbl: ttk.Label, v: float | str) -> None:
        try:
            text = str(int(float(v)))
        except _LABEL_VALUE_ERRORS:
            text = "?"

        try:
            lbl.configure(text=text)
        except _LABEL_WIDGET_ERRORS:
            if text == "?":
                return
            try:
                lbl.configure(text="?")
            except _LABEL_WIDGET_ERRORS:
                return
