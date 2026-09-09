from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from keyrgb.gui.theme import metrics as theme_metrics

from ._wrap_sync import bind_wraplength_sync

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
        on_toggle: Callable[[], None],
        idle_source_label: str = "Unknown",
    ) -> None:
        self.var_dim_sync_enabled = var_dim_sync_enabled
        self.var_dim_sync_mode = var_dim_sync_mode
        self.var_dim_temp_brightness = var_dim_temp_brightness
        self._on_toggle = on_toggle
        self._idle_source_label = str(idle_source_label)

        dim_title = ttk.Label(parent, text="Screen idle/blanking sync", style=theme_metrics.SECTION_LABEL_STYLE)
        dim_title.pack(anchor="w", pady=(0, theme_metrics.CONTROL_GAP_Y))

        dim_desc = ttk.Label(
            parent,
            text=(
                "React to screen blanking or session idle by turning keyboard LEDs off "
                "or dropping them to a temporary brightness."
            ),
            style=theme_metrics.BODY_LABEL_STYLE,
            justify="left",
            wraplength=400,
        )
        dim_desc.pack(anchor="w", fill="x", pady=(0, 8))
        bind_wraplength_sync(parent, [dim_desc])

        self.lbl_idle_source = ttk.Label(
            parent,
            text=f"Idle source: {self._idle_source_label}",
            style=theme_metrics.CAPTION_LABEL_STYLE,
        )
        self.lbl_idle_source.pack(anchor="w", pady=(0, 8))

        self.chk_dim_sync = ttk.Checkbutton(
            parent,
            text="Sync keyboard lighting with screen idle/blanking",
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
        dim_temp_row.pack(fill="x", pady=(theme_metrics.CONTROL_GAP_Y, 0))
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
            style=theme_metrics.VALUE_LABEL_STYLE,
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
        self.scale_dim_temp.pack(fill="x", pady=(theme_metrics.CONTROL_GAP_Y, 0))
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

        if self.lbl_idle_source is not None:
            self.lbl_idle_source.configure(state=state)

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
