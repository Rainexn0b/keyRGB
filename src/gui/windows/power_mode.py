#!/usr/bin/env python3
"""Standalone lightweight power mode settings window."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from src.core.runtime.imports import ensure_repo_root_on_sys_path

try:
    from src.core.config import Config
    from src.core.power.system import (
        DEFAULT_EXTREME_SAVER_CAP_KHZ,
        MAX_EXTREME_SAVER_CAP_KHZ,
        MIN_EXTREME_SAVER_CAP_KHZ,
        PowerMode,
        get_current_freq_stats_khz,
        get_status,
        normalize_extreme_saver_cap_khz,
        set_mode,
    )
    from src.gui.theme import apply_clam_theme
    from src.gui.utils.window_geometry import compute_centered_window_geometry
    from src.gui.utils.window_icon import apply_keyrgb_window_icon
except ImportError:
    ensure_repo_root_on_sys_path(Path(__file__))
    from src.core.config import Config
    from src.core.power.system import (
        DEFAULT_EXTREME_SAVER_CAP_KHZ,
        MAX_EXTREME_SAVER_CAP_KHZ,
        MIN_EXTREME_SAVER_CAP_KHZ,
        PowerMode,
        get_current_freq_stats_khz,
        get_status,
        normalize_extreme_saver_cap_khz,
        set_mode,
    )
    from src.gui.theme import apply_clam_theme
    from src.gui.utils.window_geometry import compute_centered_window_geometry
    from src.gui.utils.window_icon import apply_keyrgb_window_icon


logger = logging.getLogger(__name__)

_GUI_RUNTIME_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_GEOMETRY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_CONTENT_WRAP_PX = 760
_LIVE_PREVIEW_INTERVAL_MS = 1000

_INTRO_TEXT = (
    "Tune KeyRGB's lightweight CPU power-mode integration. Changes here only affect "
    "what happens when you pick Extreme Saver from the tray."
)
_EXTREME_HELP_TEXT = (
    "Extreme Saver pins the CPU min/max frequency to the configured target, "
    "prefers the powersave governor, and turns boost off."
)
_BALANCED_HELP_TEXT = (
    "Balanced restores the CPU min/max frequency range, prefers the schedutil governor, and keeps boost on."
)
_PERFORMANCE_HELP_TEXT = (
    "Performance restores the CPU min/max frequency range, prefers the performance governor, and keeps boost on."
)
_CAP_NOTE_TEXT = (
    "The configured target is stored in KeyRGB config and applied the next time you "
    "choose Extreme Saver. KeyRGB clamps the final write to your CPU's supported "
    "min/max before pinning the range."
)


def _cap_mhz_bounds() -> tuple[int, int]:
    return (MIN_EXTREME_SAVER_CAP_KHZ // 1000, MAX_EXTREME_SAVER_CAP_KHZ // 1000)


def _format_cap_mhz_label(cap_khz: int) -> str:
    return f"{int(normalize_extreme_saver_cap_khz(cap_khz) / 1000)} MHz"


def _mode_title(mode_value: object) -> str:
    raw = str(mode_value or "unknown").strip().replace("-", " ").lower()
    return raw.title() if raw else "Unknown"


def _format_status_text() -> str:
    try:
        status = get_status()
    except _GUI_RUNTIME_ERRORS:
        logger.exception("Failed to read system power mode status")
        return "Status: unavailable"

    if not bool(status.supported):
        reason = str(status.reason or "unsupported").strip() or "unsupported"
        return f"Status: unavailable ({reason})"

    identifiers = dict(status.identifiers or {})
    helper_present = "yes" if identifiers.get("helper_present") == "true" else "no"
    sysfs_writable = "yes" if identifiers.get("sysfs_writable") == "true" else "no"
    can_apply = "yes" if identifiers.get("can_apply") == "true" else "no"
    configured_cap = identifiers.get("configured_extreme_cap_khz")
    cap_suffix = ""
    if configured_cap:
        try:
            cap_suffix = f" | Configured target: {_format_cap_mhz_label(int(configured_cap))}"
        except _GUI_RUNTIME_ERRORS:
            cap_suffix = ""
    return (
        f"Current mode: {_mode_title(getattr(status.mode, 'value', status.mode))} | "
        f"Can apply: {can_apply} | Helper installed: {helper_present} | "
        f"Direct sysfs writable: {sysfs_writable}"
        f"{cap_suffix}"
    )


def _format_live_freq_text() -> str:
    try:
        average_khz, max_khz = get_current_freq_stats_khz()
    except _GUI_RUNTIME_ERRORS:
        logger.exception("Failed to read live CPU frequency preview")
        return "Live CPU avg/max: unavailable"

    if average_khz is None:
        return "Live CPU avg/max: unavailable"

    average_mhz = int(round(average_khz / 1000))
    if max_khz is None:
        return f"Live CPU avg/max: {average_mhz} MHz / unavailable"
    max_mhz = int(round(max_khz / 1000))
    return f"Live CPU avg/max: {average_mhz} / {max_mhz} MHz"


class PowerModeSettingsGUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("KeyRGB - Power Mode Settings")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(700, 460)
        self.root.resizable(True, True)

        apply_clam_theme(self.root)

        self.config = Config()
        self._cap_var = tk.DoubleVar(value=float(self._configured_cap_mhz()))
        self._cap_value_var = tk.StringVar(value=_format_cap_mhz_label(self._configured_cap_khz()))
        self._status_var = tk.StringVar(value=_format_status_text())
        self._save_status_var = tk.StringVar(value="")
        self._live_freq_var = tk.StringVar(value=_format_live_freq_text())

        self._build_ui()
        self._apply_geometry()
        self.root.after(50, self._apply_geometry)
        self.root.after(_LIVE_PREVIEW_INTERVAL_MS, self._refresh_live_freq_preview)

    def _configured_cap_khz(self) -> int:
        return normalize_extreme_saver_cap_khz(
            getattr(self.config, "system_power_extreme_cap_khz", DEFAULT_EXTREME_SAVER_CAP_KHZ)
        )

    def _configured_cap_mhz(self) -> int:
        return int(round(self._configured_cap_khz() / 1000))

    def _selected_cap_khz(self) -> int:
        return normalize_extreme_saver_cap_khz(int(round(float(self._cap_var.get()))) * 1000)

    def _apply_geometry(self) -> None:
        try:
            self.root.update_idletasks()
            geometry = compute_centered_window_geometry(
                self.root,
                content_height_px=int(self._main_frame.winfo_reqheight()),
                content_width_px=int(self._main_frame.winfo_reqwidth()),
                footer_height_px=0,
                chrome_padding_px=40,
                default_w=760,
                default_h=520,
                screen_ratio_cap=0.95,
            )
            self.root.geometry(geometry)
        except _GEOMETRY_ERRORS:
            return

    def _sync_cap_label(self, raw_value: float | str) -> None:
        try:
            khz = int(round(float(raw_value))) * 1000
        except _GUI_RUNTIME_ERRORS:
            khz = self._configured_cap_khz()
        self._cap_value_var.set(_format_cap_mhz_label(khz))

    def _refresh_status(self) -> None:
        self._status_var.set(_format_status_text())
        self._live_freq_var.set(_format_live_freq_text())

    def _refresh_live_freq_preview(self) -> None:
        try:
            self._live_freq_var.set(_format_live_freq_text())
            self.root.after(_LIVE_PREVIEW_INTERVAL_MS, self._refresh_live_freq_preview)
        except _GEOMETRY_ERRORS:
            return

    def _save(self) -> None:
        was_extreme_active = False
        try:
            status = get_status()
            was_extreme_active = bool(status.supported) and status.mode == PowerMode.EXTREME_SAVER
        except _GUI_RUNTIME_ERRORS:
            logger.exception("Failed to read system power mode status before saving target")

        self.config.system_power_extreme_cap_khz = self._selected_cap_khz()
        self._cap_value_var.set(_format_cap_mhz_label(self.config.system_power_extreme_cap_khz))

        if was_extreme_active:
            try:
                if set_mode(PowerMode.EXTREME_SAVER):
                    self._save_status_var.set("Saved and reapplied Extreme Saver.")
                else:
                    self._save_status_var.set(
                        "Saved. Re-select Extreme Saver if the new target does not apply immediately."
                    )
            except _GUI_RUNTIME_ERRORS:
                logger.exception("Failed to reapply Extreme Saver after saving target")
                self._save_status_var.set(
                    "Saved. Re-select Extreme Saver if the new target does not apply immediately."
                )
        else:
            self._save_status_var.set(
                "Saved. The new Extreme Saver target applies the next time you choose Extreme Saver."
            )
        self._refresh_status()

    def _close(self) -> None:
        self.root.destroy()

    def _build_ui(self) -> None:
        self._main_frame = ttk.Frame(self.root, padding=14)
        self._main_frame.pack(fill="both", expand=True)

        ttk.Label(self._main_frame, text="Power Mode Settings", font=("Sans", 14, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            self._main_frame,
            text=_INTRO_TEXT,
            justify="left",
            wraplength=_CONTENT_WRAP_PX,
        ).pack(anchor="w", fill="x", pady=(0, 10))

        status_frame = ttk.LabelFrame(self._main_frame, text="Current Status", padding=10)
        status_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            status_frame,
            textvariable=self._status_var,
            justify="left",
            wraplength=_CONTENT_WRAP_PX,
        ).pack(anchor="w", fill="x")

        help_frame = ttk.LabelFrame(self._main_frame, text="What The Modes Do", padding=10)
        help_frame.pack(fill="x", pady=(0, 10))
        for text in (_EXTREME_HELP_TEXT, _BALANCED_HELP_TEXT, _PERFORMANCE_HELP_TEXT):
            ttk.Label(help_frame, text=text, justify="left", wraplength=_CONTENT_WRAP_PX).pack(
                anchor="w", fill="x", pady=(0, 6)
            )

        cap_frame = ttk.LabelFrame(self._main_frame, text="Extreme Saver Target", padding=10)
        cap_frame.pack(fill="x", pady=(0, 10))

        header = ttk.Frame(cap_frame)
        header.pack(fill="x")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Configured CPU frequency target").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self._cap_value_var, font=("Sans", 10, "bold")).grid(row=0, column=1, sticky="e")

        min_mhz, max_mhz = _cap_mhz_bounds()
        self.scale_cap = ttk.Scale(
            cap_frame,
            from_=float(min_mhz),
            to=float(max_mhz),
            orient="horizontal",
            variable=self._cap_var,
            command=self._sync_cap_label,
        )
        self.scale_cap.pack(fill="x", pady=(8, 6))

        ttk.Label(cap_frame, text=_CAP_NOTE_TEXT, justify="left", wraplength=_CONTENT_WRAP_PX).pack(
            anchor="w", fill="x"
        )

        footer = ttk.Frame(self._main_frame)
        footer.pack(fill="x", pady=(6, 0))
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure(1, weight=0)
        footer.columnconfigure(2, weight=0)
        footer.columnconfigure(3, weight=0)

        ttk.Label(footer, textvariable=self._save_status_var, justify="left", wraplength=420).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(0, 10),
        )
        ttk.Button(footer, text="Refresh Status", command=self._refresh_status).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(0, 8),
        )
        ttk.Button(footer, text="Save", command=self._save).grid(row=1, column=2, sticky="ew", padx=(0, 8))
        ttk.Button(footer, text="Close", command=self._close).grid(row=1, column=3, sticky="ew")
        ttk.Label(footer, textvariable=self._live_freq_var, justify="left", wraplength=_CONTENT_WRAP_PX).grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(12, 0),
        )

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    PowerModeSettingsGUI().run()


if __name__ == "__main__":
    main()
