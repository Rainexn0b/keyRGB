from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import ttk


_LABEL_VALUE_ERRORS = (TypeError, ValueError, OverflowError)
_LABEL_WIDGET_ERRORS = (RuntimeError, tk.TclError)


class DimSyncPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_dim_sync_enabled: tk.BooleanVar,
        var_dim_sync_mode: tk.StringVar,
        var_dim_temp_brightness: tk.DoubleVar,
        var_debounce_enter: tk.IntVar,
        var_debounce_exit: tk.IntVar,
        on_toggle: Callable[[], None],
    ) -> None:
        self.var_dim_sync_enabled = var_dim_sync_enabled
        self.var_dim_sync_mode = var_dim_sync_mode
        self.var_dim_temp_brightness = var_dim_temp_brightness
        self.var_debounce_enter = var_debounce_enter
        self.var_debounce_exit = var_debounce_exit
        self._on_toggle = on_toggle

        dim_title = ttk.Label(parent, text="Screen dim/brightness sync", font=("Sans", 11, "bold"))
        dim_title.pack(anchor="w", pady=(0, 6))

        dim_desc = ttk.Label(
            parent,
            text=(
                "React to screen dimming or brightness changes by turning keyboard LEDs off "
                "or dropping them to a temporary brightness."
            ),
            font=("Sans", 9),
            justify="left",
            wraplength=520,
        )
        dim_desc.pack(anchor="w", fill="x", pady=(0, 8))

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
        dim_temp_row.columnconfigure(0, weight=1)

        self.rb_dim_temp = ttk.Radiobutton(
            dim_temp_row,
            text="When dimmed: set brightness to",
            value="temp",
            variable=self.var_dim_sync_mode,
            command=self._on_toggle,
        )
        self.rb_dim_temp.grid(row=0, column=0, sticky="w")

        self.lbl_dim_temp_val = ttk.Label(
            dim_temp_row,
            text=str(int(float(self.var_dim_temp_brightness.get()))),
            font=("Sans", 9),
        )
        self.lbl_dim_temp_val.grid(row=0, column=1, sticky="e", padx=(12, 0))

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

        debounce_frame = ttk.Frame(parent)
        debounce_frame.pack(fill="x", pady=(10, 0))
        debounce_desc = ttk.Label(
            debounce_frame,
            text="Delay before reacting to screen dimming/brightening (polls x 0.5s each).",
            font=("Sans", 8),
        )
        debounce_desc.pack(anchor="w", pady=(0, 4))

        enter_row = ttk.Frame(debounce_frame)
        enter_row.pack(fill="x")
        enter_row.columnconfigure(0, weight=1)
        ttk.Label(enter_row, text="Turn-off delay").grid(row=0, column=0, sticky="w")
        self.spn_enter = ttk.Spinbox(
            enter_row,
            from_=1,
            to=60,
            textvariable=self.var_debounce_enter,
            width=5,
            command=self._on_toggle,
        )
        self.spn_enter.grid(row=0, column=1, sticky="e")
        self.spn_enter.bind("<Return>", lambda _e: self._on_toggle())

        exit_row = ttk.Frame(debounce_frame)
        exit_row.pack(fill="x", pady=(4, 0))
        exit_row.columnconfigure(0, weight=1)
        ttk.Label(exit_row, text="Restore delay").grid(row=0, column=0, sticky="w")
        self.spn_exit = ttk.Spinbox(
            exit_row,
            from_=1,
            to=60,
            textvariable=self.var_debounce_exit,
            width=5,
            command=self._on_toggle,
        )
        self.spn_exit.grid(row=0, column=1, sticky="e")
        self.spn_exit.bind("<Return>", lambda _e: self._on_toggle())

    def apply_enabled_state(self, *, power_management_enabled: bool) -> None:
        state = "normal" if power_management_enabled else "disabled"
        for w in (
            self.chk_dim_sync,
            self.rb_dim_off,
            self.rb_dim_temp,
            self.scale_dim_temp,
            self.spn_enter,
            self.spn_exit,
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
