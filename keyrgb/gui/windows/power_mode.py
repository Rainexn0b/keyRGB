"""Standalone lightweight power mode settings window."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import ttk

from keyrgb.core.config import Config
from keyrgb.core.power import system as _power_system
from keyrgb.gui import theme as gui_theme
from keyrgb.gui.utils.tk_async import TkAsyncCoordinator, submit_gui_work
from keyrgb.gui.utils.window_bindings import install_window_bindings
from keyrgb.gui.utils.window_geometry import compute_centered_window_geometry
from keyrgb.gui.utils.window_icon import apply_keyrgb_window_icon
from keyrgb.gui.utils.window_state import WindowGeometryTracker

from . import _power_mode_ui

_CONTENT_WRAP_PX = _power_mode_ui._CONTENT_WRAP_PX
_INTRO_TEXT = _power_mode_ui._INTRO_TEXT
_EXTREME_HELP_TEXT = _power_mode_ui._EXTREME_HELP_TEXT
_BALANCED_HELP_TEXT = _power_mode_ui._BALANCED_HELP_TEXT
_PERFORMANCE_HELP_TEXT = _power_mode_ui._PERFORMANCE_HELP_TEXT
_CAP_NOTE_TEXT = _power_mode_ui._CAP_NOTE_TEXT

DEFAULT_EXTREME_SAVER_CAP_KHZ = _power_system.DEFAULT_EXTREME_SAVER_CAP_KHZ
MAX_EXTREME_SAVER_CAP_KHZ = _power_system.MAX_EXTREME_SAVER_CAP_KHZ
MIN_EXTREME_SAVER_CAP_KHZ = _power_system.MIN_EXTREME_SAVER_CAP_KHZ
PowerMode = _power_system.PowerMode
get_current_freq_stats_khz = _power_system.get_current_freq_stats_khz
get_status = _power_system.get_status
normalize_extreme_saver_cap_khz = _power_system.normalize_extreme_saver_cap_khz
set_mode = _power_system.set_mode

logger = logging.getLogger(__name__)

# Keep module-level dependency names explicit so tests can monkeypatch this
# module directly while the implementation still resolves through the package.
apply_clam_theme = gui_theme.apply_clam_theme
schedule_initial_focus = gui_theme.schedule_initial_focus

_GUI_RUNTIME_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_GEOMETRY_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_LIVE_PREVIEW_INTERVAL_MS = 1000


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

    average_mhz = round(average_khz / 1000)
    if max_khz is None:
        return f"Live CPU avg/max: {average_mhz} MHz / unavailable"
    max_mhz = round(max_khz / 1000)
    return f"Live CPU avg/max: {average_mhz} / {max_mhz} MHz"


class PowerModeSettingsGUI:
    _geometry_restored = False
    _main_frame: ttk.Frame
    scale_cap: ttk.Scale
    btn_save: ttk.Button

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.tk_jobs = TkAsyncCoordinator()
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
        # UX-06: restore persisted geometry before the centered fallback
        # passes. When restoration wins, both centered passes are suppressed;
        # otherwise the exact previous fallback behavior runs. Tracking starts
        # just after the last initial programmatic pass.
        self._geometry_tracker = WindowGeometryTracker(self.root, "power-mode", 700, 460, 0.95)
        self._geometry_restored = bool(self._geometry_tracker.restore())
        if not self._geometry_restored:
            self._apply_geometry()
            self.root.after(50, self._apply_geometry)
        self.root.after(60, self._geometry_tracker.start_tracking)
        protocol = getattr(self.root, "protocol", None)
        if callable(protocol):
            protocol("WM_DELETE_WINDOW", self._close)
        # UX-08: Ctrl+W/Escape share the exact orderly close above; Ctrl+S
        # shares the exact Save-button handler (additive, focus-preserving).
        install_window_bindings(self.root, on_close=self._close, on_save=self._save)
        self.root.after(_LIVE_PREVIEW_INTERVAL_MS, self._refresh_live_freq_preview)

    def _configured_cap_khz(self) -> int:
        return normalize_extreme_saver_cap_khz(
            getattr(self.config, "system_power_extreme_cap_khz", DEFAULT_EXTREME_SAVER_CAP_KHZ)
        )

    def _configured_cap_mhz(self) -> int:
        return round(self._configured_cap_khz() / 1000)

    def _selected_cap_khz(self) -> int:
        return normalize_extreme_saver_cap_khz(round(float(self._cap_var.get())) * 1000)

    def _apply_geometry(self) -> None:
        if bool(vars(self).get("_geometry_restored", False)):
            return
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
            khz = round(float(raw_value)) * 1000
        except _GUI_RUNTIME_ERRORS:
            khz = self._configured_cap_khz()
        self._cap_value_var.set(_format_cap_mhz_label(khz))

    def _refresh_status(self) -> None:
        self._status_var.set(_format_status_text())
        self._live_freq_var.set(_format_live_freq_text())

    def _refresh_live_freq_preview(self) -> None:
        def on_done(text: str) -> None:
            try:
                self._live_freq_var.set(text)
                self.root.after(_LIVE_PREVIEW_INTERVAL_MS, self._refresh_live_freq_preview)
            except _GEOMETRY_ERRORS:
                return

        submit_gui_work(self, getattr(self, "root", None), _format_live_freq_text, on_done)

    def _save(self) -> None:
        selected_cap = self._selected_cap_khz()

        def work() -> tuple[int, str]:
            was_extreme_active = False
            try:
                status = get_status()
                was_extreme_active = bool(status.supported) and status.mode == PowerMode.EXTREME_SAVER
            except _GUI_RUNTIME_ERRORS:
                logger.exception("Failed to read system power mode status before saving target")

            self.config.system_power_extreme_cap_khz = selected_cap
            persisted = int(self.config.system_power_extreme_cap_khz)
            if was_extreme_active:
                try:
                    if set_mode(PowerMode.EXTREME_SAVER):
                        return persisted, "Saved and reapplied Extreme Saver."
                    return (
                        persisted,
                        "Saved. Re-select Extreme Saver if the new target does not apply immediately.",
                    )
                except _GUI_RUNTIME_ERRORS:
                    logger.exception("Failed to reapply Extreme Saver after saving target")
                    return (
                        persisted,
                        "Saved. Re-select Extreme Saver if the new target does not apply immediately.",
                    )
            return persisted, "Saved. The new Extreme Saver target applies the next time you choose Extreme Saver."

        def on_done(result: tuple[int, str]) -> None:
            persisted, message = result
            self._cap_value_var.set(_format_cap_mhz_label(persisted))
            self._save_status_var.set(message)
            self._refresh_status()

        submit_gui_work(self, getattr(self, "root", None), work, on_done)

    def _close(self) -> None:
        try:
            self._save_geometry_now()
        finally:
            try:
                self.tk_jobs.cancel()
            except AttributeError:
                pass
            self.root.destroy()

    def _save_geometry_now(self) -> None:
        tracker = vars(self).get("_geometry_tracker")
        save_now = getattr(tracker, "save_now", None)
        if callable(save_now):
            save_now()

    def _build_ui(self) -> None:
        _power_mode_ui.build_power_mode_ui(
            self,
            ttk=ttk,
            schedule_initial_focus_fn=schedule_initial_focus,
            cap_mhz_bounds=_cap_mhz_bounds(),
        )

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    from keyrgb.gui import single_instance

    single_instance.acquire_gui_instance_or_exit("power-mode")
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    PowerModeSettingsGUI().run()


if __name__ == "__main__":
    main()
