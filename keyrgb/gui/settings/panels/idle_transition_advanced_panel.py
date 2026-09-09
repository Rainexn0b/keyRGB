from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from keyrgb.gui.theme import metrics as theme_metrics

from ._wrap_sync import bind_wraplength_sync

_LABEL_VALUE_ERRORS = (TypeError, ValueError, OverflowError)
_LABEL_WIDGET_ERRORS = (RuntimeError, tk.TclError)


class IdleTransitionAdvancedPanel:
    """Advanced idle-transition timing and controller sleep policy (UX-02)."""

    def __init__(
        self,
        parent: ttk.Frame,
        *,
        var_controller_sleep_respect: tk.BooleanVar,
        var_debounce_enter: tk.DoubleVar,
        var_debounce_exit: tk.DoubleVar,
        var_idle_fade_duration: tk.DoubleVar,
        on_toggle: Callable[[], None],
    ) -> None:
        self.var_controller_sleep_respect = var_controller_sleep_respect
        self.var_debounce_enter = var_debounce_enter
        self.var_debounce_exit = var_debounce_exit
        self.var_idle_fade_duration = var_idle_fade_duration
        self._on_toggle = on_toggle

        title = ttk.Label(parent, text="Controller sleep and idle timing", style=theme_metrics.SECTION_LABEL_STYLE)
        title.pack(anchor="w", pady=(0, theme_metrics.CONTROL_GAP_Y))

        self.chk_controller_sleep = ttk.Checkbutton(
            parent,
            text="Let the controller's own sleep timeout turn the keyboard off",
            variable=self.var_controller_sleep_respect,
            command=self._on_toggle,
        )
        self.chk_controller_sleep.pack(anchor="w")

        controller_sleep_desc = ttk.Label(
            parent,
            text=(
                "Recommended for supported ITE controllers: firmware sleeps after ~10 min without typing. When "
                "it or screen-idle sync turns the deck off, only a non-modifier keypress restores lighting."
            ),
            style=theme_metrics.CAPTION_LABEL_STYLE,
            justify="left",
            wraplength=400,
        )
        controller_sleep_desc.pack(anchor="w", fill="x", padx=(24, 0), pady=(0, 8))
        bind_wraplength_sync(parent, [controller_sleep_desc], margin=48)

        debounce_frame = ttk.Frame(parent)
        debounce_frame.pack(fill="x", pady=(theme_metrics.SECTION_GAP_Y, 0))
        debounce_desc = ttk.Label(
            debounce_frame,
            text="Delay before reacting to screen idle/blanking, in seconds.",
            style=theme_metrics.CAPTION_LABEL_STYLE,
        )
        debounce_desc.pack(anchor="w", pady=(0, theme_metrics.INLINE_GAP_X))

        enter_row = ttk.Frame(debounce_frame)
        enter_row.pack(fill="x")
        enter_row.columnconfigure(0, weight=1)
        ttk.Label(enter_row, text="Turn-off delay", style=theme_metrics.BODY_LABEL_STYLE).grid(
            row=0, column=0, sticky="w"
        )
        self.spn_enter = ttk.Spinbox(
            enter_row,
            from_=0.5,
            to=30.0,
            increment=0.5,
            format="%.1f",
            textvariable=self.var_debounce_enter,
            width=5,
            command=self._on_toggle,
        )
        self.spn_enter.grid(row=0, column=1, sticky="e")
        self.spn_enter.bind("<Return>", lambda _e: self._on_toggle())

        exit_row = ttk.Frame(debounce_frame)
        exit_row.pack(fill="x", pady=(theme_metrics.INLINE_GAP_X, 0))
        exit_row.columnconfigure(0, weight=1)
        ttk.Label(exit_row, text="Restore delay", style=theme_metrics.BODY_LABEL_STYLE).grid(
            row=0, column=0, sticky="w"
        )
        self.spn_exit = ttk.Spinbox(
            exit_row,
            from_=0.5,
            to=30.0,
            increment=0.5,
            format="%.1f",
            textvariable=self.var_debounce_exit,
            width=5,
            command=self._on_toggle,
        )
        self.spn_exit.grid(row=0, column=1, sticky="e")
        self.spn_exit.bind("<Return>", lambda _e: self._on_toggle())

        fade_frame = ttk.Frame(parent)
        fade_frame.pack(fill="x", pady=(theme_metrics.SECTION_GAP_Y, 0))
        fade_desc = ttk.Label(
            fade_frame,
            text="Fade length when keyboard lighting dims, turns off, or restores.",
            style=theme_metrics.CAPTION_LABEL_STYLE,
        )
        fade_desc.pack(anchor="w", pady=(0, theme_metrics.INLINE_GAP_X))

        fade_row = ttk.Frame(fade_frame)
        fade_row.pack(fill="x")
        fade_row.columnconfigure(0, weight=1)
        ttk.Label(fade_row, text="Fade duration", style=theme_metrics.BODY_LABEL_STYLE).grid(
            row=0, column=0, sticky="w"
        )
        self.lbl_fade_duration_val = ttk.Label(
            fade_row,
            text=f"{float(self.var_idle_fade_duration.get()):.1f} s",
            style=theme_metrics.VALUE_LABEL_STYLE,
        )
        self.lbl_fade_duration_val.grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.scale_fade_duration = ttk.Scale(
            fade_frame,
            from_=0.1,
            to=3.0,
            orient="horizontal",
            variable=self.var_idle_fade_duration,
            command=lambda v: self._set_label_seconds(self.lbl_fade_duration_val, v),
        )
        self.scale_fade_duration.pack(fill="x", pady=(theme_metrics.CONTROL_GAP_Y, 0))
        self.scale_fade_duration.bind("<ButtonRelease-1>", lambda _e: self._on_toggle())

    def apply_enabled_state(self, *, power_management_enabled: bool) -> None:
        # The controller-sleep checkbox is intentionally never disabled with
        # power management; only the timing controls follow that toggle.
        state = "normal" if power_management_enabled else "disabled"
        for w in (
            self.spn_enter,
            self.spn_exit,
            self.scale_fade_duration,
        ):
            w.configure(state=state)

    @staticmethod
    def _set_label_seconds(lbl: ttk.Label, v: float | str) -> None:
        try:
            text = f"{float(v):.1f} s"
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
