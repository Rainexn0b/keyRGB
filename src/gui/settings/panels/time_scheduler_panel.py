from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import ttk


_LABEL_VALUE_ERRORS = (TypeError, ValueError, OverflowError)
_LABEL_WIDGET_ERRORS = (RuntimeError, tk.TclError)


class TimeSchedulerPanel:
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_enabled: tk.BooleanVar,
        var_day_start: tk.StringVar,
        var_night_start: tk.StringVar,
        var_day_base: tk.DoubleVar,
        var_day_reactive: tk.DoubleVar,
        var_night_base: tk.DoubleVar,
        var_night_reactive: tk.DoubleVar,
        on_toggle: Callable[[], None],
    ) -> None:
        self.var_enabled = var_enabled
        self.var_day_start = var_day_start
        self.var_night_start = var_night_start
        self.var_day_base = var_day_base
        self.var_day_reactive = var_day_reactive
        self.var_night_base = var_night_base
        self.var_night_reactive = var_night_reactive
        self._on_toggle = on_toggle
        self._scales: list[ttk.Scale] = []

        title = ttk.Label(parent, text="Time-of-day brightness scheduler", font=("Sans", 11, "bold"))
        title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            parent,
            text=(
                "Adjust keyboard brightness by local time. During the day, 'Plugged In vs Battery' "
                "still controls base brightness. Reactive brightness follows the schedule, and at "
                "night these values always apply."
            ),
            font=("Sans", 9),
            justify="left",
            wraplength=520,
        )
        desc.pack(anchor="w", fill="x", pady=(0, 8))

        self.chk_enabled = ttk.Checkbutton(
            parent,
            text="Enable time-of-day brightness scheduler",
            variable=self.var_enabled,
            command=self._on_toggle,
        )
        self.chk_enabled.pack(anchor="w", pady=(0, 6))

        # Schedule row
        schedule_frame = ttk.Frame(parent)
        schedule_frame.pack(fill="x", pady=(0, 8))
        schedule_frame.columnconfigure(0, weight=1)
        schedule_frame.columnconfigure(2, weight=1)

        ttk.Label(schedule_frame, text="Day starts at", font=("Sans", 9)).grid(row=0, column=0, sticky="w")
        self.ent_day_start = ttk.Entry(
            schedule_frame,
            textvariable=self.var_day_start,
            width=6,
        )
        self.ent_day_start.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.ent_day_start.bind("<Return>", lambda _e: self._on_toggle())
        self.ent_day_start.bind("<FocusOut>", lambda _e: self._on_toggle())

        ttk.Label(schedule_frame, text="Night starts at", font=("Sans", 9)).grid(
            row=0, column=2, sticky="e", padx=(12, 6)
        )
        self.ent_night_start = ttk.Entry(
            schedule_frame,
            textvariable=self.var_night_start,
            width=6,
        )
        self.ent_night_start.grid(row=0, column=3, sticky="e")
        self.ent_night_start.bind("<Return>", lambda _e: self._on_toggle())
        self.ent_night_start.bind("<FocusOut>", lambda _e: self._on_toggle())

        # Day values
        day_frame = ttk.LabelFrame(parent, text="Day values", padding=(8, 5))
        day_frame.pack(fill="x", pady=(0, 8))

        self._build_brightness_row(
            day_frame,
            label="Base brightness (used when power policy is off)",
            var=self.var_day_base,
            row=0,
        )
        self._build_brightness_row(
            day_frame,
            label="Reactive brightness",
            var=self.var_day_reactive,
            row=1,
        )

        # Night values
        night_frame = ttk.LabelFrame(parent, text="Night values (always used at night)", padding=(8, 5))
        night_frame.pack(fill="x", pady=(0, 0))

        self._build_brightness_row(
            night_frame,
            label="Base brightness",
            var=self.var_night_base,
            row=0,
        )
        self._build_brightness_row(
            night_frame,
            label="Reactive brightness",
            var=self.var_night_reactive,
            row=1,
        )

    def _build_brightness_row(
        self,
        parent: ttk.LabelFrame,
        *,
        label: str,
        var: tk.DoubleVar,
        row: int,
    ) -> None:
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill="x", pady=(3, 0))
        row_frame.columnconfigure(0, weight=1)

        ttk.Label(row_frame, text=label, font=("Sans", 9)).grid(row=0, column=0, sticky="w")

        lbl_val = ttk.Label(row_frame, text=str(int(var.get())), font=("Sans", 9), width=3)
        lbl_val.grid(row=0, column=1, sticky="e", padx=(12, 0))

        scale = ttk.Scale(
            parent,
            from_=0,
            to=50,
            orient="horizontal",
            variable=var,
            command=lambda v, lbl=lbl_val: self._set_label_int(lbl, v),
        )
        scale.pack(fill="x", pady=(1, 0))
        scale.bind("<ButtonRelease-1>", lambda _e: self._on_toggle())
        self._scales.append(scale)

    def apply_enabled_state(self) -> None:
        state = "normal" if self.var_enabled.get() else "disabled"
        for w in (
            self.ent_day_start,
            self.ent_night_start,
        ):
            w.configure(state=state)

        for scale in self._scales:
            scale.configure(state=state)

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
