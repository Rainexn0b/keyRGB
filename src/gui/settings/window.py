#!/usr/bin/env python3
"""Settings GUI.

This is a small Tkinter window that controls how KeyRGB reacts to:
- Lid close/open
- System suspend/resume

And a basic autostart flag used by the tray runtime.

Settings are persisted in the shared `~/.config/keyrgb/config.json` via
`src.legacy.config.Config`.
"""

from __future__ import annotations

import os
import sys

import tkinter as tk
from tkinter import ttk

from .autostart_panel import AutostartPanel
from .diagnostics_panel import DiagnosticsPanel
from .dim_sync_panel import DimSyncPanel
from .os_autostart import detect_os_autostart_enabled, set_os_autostart
from .scrollable_area import ScrollableArea
from .version_panel import VersionPanel
from .settings_state import SettingsValues, apply_settings_values_to_config, load_settings_values

from src.legacy.config import Config

from src.gui.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_dark_theme


class PowerSettingsGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KeyRGB - Settings")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(760, 560)
        self.root.resizable(True, True)

        bg_color, fg_color = apply_clam_dark_theme(
            self.root,
            include_checkbuttons=True,
            map_checkbutton_state=True,
        )

        self.config = Config()

        values = load_settings_values(config=self.config, os_autostart_enabled=detect_os_autostart_enabled())

        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True)

        content_area = ttk.Frame(outer)
        content_area.pack(fill="both", expand=True)

        self.scroll = ScrollableArea(content_area, bg_color=bg_color, padding=16)
        main = self.scroll.frame

        title = ttk.Label(main, text="Settings", font=("Sans", 14, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        cols = ttk.Frame(main)
        cols.pack(fill="both", expand=True)

        left = ttk.Frame(cols)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(cols)
        right.pack(side="left", fill="both", expand=True, padx=(18, 0))

        pm_title = ttk.Label(left, text="Power Management", font=("Sans", 11, "bold"))
        pm_title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            left,
            text=(
                "Control whether KeyRGB turns the keyboard LEDs off/on\n"
                "when the lid closes/opens or the system suspends/resumes."
            ),
            font=("Sans", 9),
        )
        desc.pack(anchor="w", pady=(0, 12))

        self.var_enabled = tk.BooleanVar(value=bool(values.power_management_enabled))
        self.var_off_suspend = tk.BooleanVar(value=bool(values.power_off_on_suspend))
        self.var_off_lid = tk.BooleanVar(value=bool(values.power_off_on_lid_close))
        self.var_restore_resume = tk.BooleanVar(value=bool(values.power_restore_on_resume))
        self.var_restore_lid = tk.BooleanVar(value=bool(values.power_restore_on_lid_open))
        self.var_autostart = tk.BooleanVar(value=bool(values.autostart))
        self.var_os_autostart = tk.BooleanVar(value=bool(values.os_autostart_enabled))

        self.var_ac_enabled = tk.BooleanVar(value=bool(values.ac_lighting_enabled))
        self.var_battery_enabled = tk.BooleanVar(value=bool(values.battery_lighting_enabled))
        self.var_ac_brightness = tk.DoubleVar(value=float(values.ac_lighting_brightness))
        self.var_battery_brightness = tk.DoubleVar(value=float(values.battery_lighting_brightness))

        self.var_dim_sync_enabled = tk.BooleanVar(value=bool(values.screen_dim_sync_enabled))
        self.var_dim_sync_mode = tk.StringVar(value=str(values.screen_dim_sync_mode or "off"))
        self.var_dim_temp_brightness = tk.DoubleVar(value=float(values.screen_dim_temp_brightness))

        self.chk_enabled = ttk.Checkbutton(
            left,
            text="Enable power management",
            variable=self.var_enabled,
            command=self._on_toggle,
        )
        self.chk_enabled.pack(anchor="w", pady=(0, 8))

        self.chk_off_suspend = ttk.Checkbutton(
            left,
            text="Turn off on suspend",
            variable=self.var_off_suspend,
            command=self._on_toggle,
        )
        self.chk_off_suspend.pack(anchor="w")

        self.chk_restore_resume = ttk.Checkbutton(
            left,
            text="Restore on resume",
            variable=self.var_restore_resume,
            command=self._on_toggle,
        )
        self.chk_restore_resume.pack(anchor="w")

        self.chk_off_lid = ttk.Checkbutton(
            left,
            text="Turn off on lid close",
            variable=self.var_off_lid,
            command=self._on_toggle,
        )
        self.chk_off_lid.pack(anchor="w", pady=(8, 0))

        self.chk_restore_lid = ttk.Checkbutton(
            left,
            text="Restore on lid open",
            variable=self.var_restore_lid,
            command=self._on_toggle,
        )
        self.chk_restore_lid.pack(anchor="w")

        ttk.Separator(left).pack(fill="x", pady=(14, 10))

        self.dim_sync_panel = DimSyncPanel(
            left,
            var_dim_sync_enabled=self.var_dim_sync_enabled,
            var_dim_sync_mode=self.var_dim_sync_mode,
            var_dim_temp_brightness=self.var_dim_temp_brightness,
            on_toggle=self._on_toggle,
        )

        ttk.Separator(left).pack(fill="x", pady=(14, 10))

        ps_title = ttk.Label(left, text="Plugged In vs Battery", font=("Sans", 11, "bold"))
        ps_title.pack(anchor="w", pady=(0, 6))

        ps_desc = ttk.Label(
            left,
            text=(
                "Choose whether the keyboard lighting should be on/off and what\n"
                "brightness to use when plugged in vs running on battery."
            ),
            font=("Sans", 9),
        )
        ps_desc.pack(anchor="w", pady=(0, 10))

        def _set_label_int(lbl: ttk.Label, v: float | str) -> None:
            try:
                lbl.configure(text=str(int(float(v))))
            except Exception:
                lbl.configure(text="?")

        # AC row
        ac_row = ttk.Frame(left)
        ac_row.pack(fill="x", pady=(0, 10))
        ac_head = ttk.Frame(ac_row)
        ac_head.pack(fill="x")

        self.chk_ac_enabled = ttk.Checkbutton(
            ac_head,
            text="When plugged in (AC): enable lighting",
            variable=self.var_ac_enabled,
            command=self._on_toggle,
        )
        self.chk_ac_enabled.pack(side="left", anchor="w")

        self.lbl_ac_brightness_val = ttk.Label(ac_head, text=str(int(self.var_ac_brightness.get())), font=("Sans", 9))
        self.lbl_ac_brightness_val.pack(side="right")
        ttk.Label(ac_head, text="Brightness", font=("Sans", 9)).pack(side="right", padx=(0, 6))

        self.scale_ac_brightness = ttk.Scale(
            ac_row,
            from_=0,
            to=50,
            orient="horizontal",
            variable=self.var_ac_brightness,
            command=lambda v: _set_label_int(self.lbl_ac_brightness_val, v),
        )
        self.scale_ac_brightness.pack(fill="x", pady=(6, 0))
        self.scale_ac_brightness.bind("<ButtonRelease-1>", lambda _e: self._on_toggle())

        # Battery row
        batt_row = ttk.Frame(left)
        batt_row.pack(fill="x")
        batt_head = ttk.Frame(batt_row)
        batt_head.pack(fill="x")

        self.chk_battery_enabled = ttk.Checkbutton(
            batt_head,
            text="On battery: enable lighting",
            variable=self.var_battery_enabled,
            command=self._on_toggle,
        )
        self.chk_battery_enabled.pack(side="left", anchor="w")

        self.lbl_battery_brightness_val = ttk.Label(
            batt_head, text=str(int(self.var_battery_brightness.get())), font=("Sans", 9)
        )
        self.lbl_battery_brightness_val.pack(side="right")
        ttk.Label(batt_head, text="Brightness", font=("Sans", 9)).pack(side="right", padx=(0, 6))

        self.scale_battery_brightness = ttk.Scale(
            batt_row,
            from_=0,
            to=50,
            orient="horizontal",
            variable=self.var_battery_brightness,
            command=lambda v: _set_label_int(self.lbl_battery_brightness_val, v),
        )
        self.scale_battery_brightness.pack(fill="x", pady=(6, 0))
        self.scale_battery_brightness.bind("<ButtonRelease-1>", lambda _e: self._on_toggle())

        ttk.Separator(right).pack(fill="x", pady=(0, 10))

        self.version_panel = VersionPanel(
            right,
            root=self.root,
            get_status_label=lambda: self.status,
        )

        ttk.Separator(right).pack(fill="x", pady=(14, 10))

        self.autostart_panel = AutostartPanel(
            right,
            var_autostart=self.var_autostart,
            var_os_autostart=self.var_os_autostart,
            on_toggle=self._on_toggle,
        )

        ttk.Separator(right).pack(fill="x", pady=(14, 10))

        self.diagnostics_panel = DiagnosticsPanel(
            right,
            root=self.root,
            get_status_label=lambda: self.status,
            bg_color=bg_color,
            fg_color=fg_color,
        )

        self.bottom_bar = ttk.Frame(outer, padding=(16, 8, 16, 12))
        self.bottom_bar.pack(fill="x")

        self.status = ttk.Label(self.bottom_bar, text="", font=("Sans", 9))
        self.status.pack(side="left")

        close_btn = ttk.Button(self.bottom_bar, text="Close", command=self._on_close)
        close_btn.pack(side="right")

        self._apply_enabled_state()
        self.diagnostics_panel.apply_state()

        # Bind wheel globally within this Tk app, but filter to this toplevel + pointer location.
        self.scroll.bind_mousewheel(self.root, priority_scroll_widget=self.diagnostics_panel.txt_diagnostics)

        # Initial geometry is applied via _apply_geometry after a short delay
        # to ensure it overrides any window manager restoration/defaults.

        self.root.update_idletasks()
        try:
            self.scroll.canvas.configure(scrollregion=self.scroll.canvas.bbox("all"))
        except Exception:
            pass

        self.scroll.finalize_initial_scrollbar_state()

        # Defer geometry application to ensure it overrides any WM defaults
        self.root.after(50, self._apply_geometry)

    def _apply_geometry(self) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Calculate true content height from the inner frame + bottom bar
        content_h = self.scroll.frame.winfo_reqheight()
        footer_h = self.bottom_bar.winfo_reqheight()
        # Add some padding for window chrome/margins
        total_req_h = content_h + footer_h + 40

        req_w = self.root.winfo_reqwidth()
        
        # Conservative defaults
        default_w = 1100
        default_h = 850

        # Cap at 95% of screen size to ensure it fits
        max_w = int(screen_w * 0.95)
        max_h = int(screen_h * 0.95)

        width = min(max(req_w, default_w), max_w)
        # Use the calculated content height if it's larger than default, but still capped
        height = min(max(total_req_h, default_h), max_h)

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_enabled_state(self) -> None:
        enabled = bool(self.var_enabled.get())
        state = "normal" if enabled else "disabled"
        for w in (
            self.chk_off_suspend,
            self.chk_restore_resume,
            self.chk_off_lid,
            self.chk_restore_lid,
            self.chk_ac_enabled,
            self.chk_battery_enabled,
            self.scale_ac_brightness,
            self.scale_battery_brightness,
        ):
            w.configure(state=state)

        self.dim_sync_panel.apply_enabled_state(power_management_enabled=enabled)

    def _on_toggle(self) -> None:
        try:
            values = SettingsValues(
                power_management_enabled=bool(self.var_enabled.get()),
                power_off_on_suspend=bool(self.var_off_suspend.get()),
                power_off_on_lid_close=bool(self.var_off_lid.get()),
                power_restore_on_resume=bool(self.var_restore_resume.get()),
                power_restore_on_lid_open=bool(self.var_restore_lid.get()),
                autostart=bool(self.var_autostart.get()),
                ac_lighting_enabled=bool(self.var_ac_enabled.get()),
                battery_lighting_enabled=bool(self.var_battery_enabled.get()),
                ac_lighting_brightness=int(float(self.var_ac_brightness.get())),
                battery_lighting_brightness=int(float(self.var_battery_brightness.get())),

                screen_dim_sync_enabled=bool(self.var_dim_sync_enabled.get()),
                screen_dim_sync_mode=str(self.var_dim_sync_mode.get() or "off"),
                screen_dim_temp_brightness=int(float(self.var_dim_temp_brightness.get())),
                os_autostart_enabled=bool(self.var_os_autostart.get()),
            )
            apply_settings_values_to_config(config=self.config, values=values)
        except Exception:
            # Keep best-effort behavior identical to the previous inline implementation.
            pass

        desired_os_autostart = bool(self.var_os_autostart.get())
        try:
            set_os_autostart(desired_os_autostart)
            self.config.os_autostart = desired_os_autostart
        except Exception:
            self.var_os_autostart.set(detect_os_autostart_enabled())

        self._apply_enabled_state()

        self.status.configure(text="✓ Saved")
        self.root.after(1500, lambda: self.status.configure(text=""))

    def _on_close(self) -> None:
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    PowerSettingsGUI().run()


if __name__ == "__main__":
    main()
