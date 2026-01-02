#!/usr/bin/env python3
"""Settings GUI.

This is a small Tkinter window that controls how KeyRGB reacts to:
- Lid close/open
- System suspend/resume

And a basic autostart flag used by the tray runtime.

Settings are persisted in the shared `~/.config/keyrgb/config.json` via
`src.core.config.Config`.
"""

from __future__ import annotations

from threading import Thread
import tkinter as tk
from tkinter import ttk

from .panels.bottom_bar_panel import BottomBarPanel
from .panels.autostart_panel import AutostartPanel
from .panels.diagnostics_panel import DiagnosticsPanel
from .panels.dim_sync_panel import DimSyncPanel
from .os_autostart import detect_os_autostart_enabled, set_os_autostart
from .panels.power_management_panel import PowerManagementPanel
from .panels.power_source_panel import PowerSourcePanel
from .scrollable_area import ScrollableArea
from .panels.version_panel import VersionPanel
from .window_geometry import compute_centered_window_geometry
from .settings_state import SettingsValues, apply_settings_values_to_config, load_settings_values

from src.core.config import Config

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
        self._init_layout(bg_color=bg_color)
        self._init_vars(values)
        self._init_panels(bg_color=bg_color, fg_color=fg_color)
        self._finalize_layout()
        self._start_footer_hardware_probe()

    def _start_footer_hardware_probe(self) -> None:
        """Populate the footer hardware hint (best-effort, read-only).

        Goal: when a device is present but not supported (e.g. ITE 8297/5702),
        show a clear hint to help users file actionable reports.
        """

        def extract_hint(backends_snapshot: dict) -> str:
            probes = backends_snapshot.get("probes")
            if not isinstance(probes, list):
                return ""

            unsupported: list[str] = []
            for p in probes:
                if not isinstance(p, dict):
                    continue
                reason = str(p.get("reason") or "")
                ids = p.get("identifiers")
                if not isinstance(ids, dict):
                    continue

                vid = ids.get("usb_vid")
                pid = ids.get("usb_pid")
                if not (isinstance(vid, str) and isinstance(pid, str)):
                    continue

                if "unsupported by ite8291r3 backend" in reason.lower():
                    unsupported.append(f"{vid}:{pid}")

            if not unsupported:
                return ""

            joined = ", ".join(unsupported)
            return f"Detected unsupported RGB controller(s): {joined} (Tier 3 / Fusion 2)."

        def worker() -> None:
            text = ""
            try:
                from src.core.diagnostics.collectors_backends import backend_probe_snapshot

                snap = backend_probe_snapshot()
                text = extract_hint(snap)
            except Exception:
                text = ""

            def apply() -> None:
                try:
                    # Only show the footer hint when we have something actionable.
                    self.bottom_bar_panel.set_hardware_hint(text)
                except Exception:
                    pass

            self.root.after(0, apply)

        # Defer slightly so the window paints immediately.
        self.root.after(100, lambda: Thread(target=worker, daemon=True).start())

    def _init_layout(self, *, bg_color: str) -> None:
        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True)

        self.bottom_bar_panel = BottomBarPanel(outer, on_close=self._on_close)
        self.bottom_bar = self.bottom_bar_panel.frame
        self.bottom_bar.pack(side="bottom", fill="x")
        self.status = self.bottom_bar_panel.status

        content_area = ttk.Frame(outer)
        content_area.pack(side="top", fill="both", expand=True)

        self.scroll = ScrollableArea(content_area, bg_color=bg_color, padding=16)
        main = self.scroll.frame

        title = ttk.Label(main, text="Settings", font=("Sans", 14, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        cols = ttk.Frame(main)
        cols.pack(fill="both", expand=True)

        self._left = ttk.Frame(cols)
        self._left.pack(side="left", fill="both", expand=True)

        self._right = ttk.Frame(cols)
        self._right.pack(side="left", fill="both", expand=True, padx=(18, 0))

    def _init_vars(self, values: SettingsValues) -> None:
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

    def _init_panels(self, *, bg_color: str, fg_color: str) -> None:
        left = self._left
        right = self._right

        self.power_management_panel = PowerManagementPanel(
            left,
            var_enabled=self.var_enabled,
            var_off_suspend=self.var_off_suspend,
            var_restore_resume=self.var_restore_resume,
            var_off_lid=self.var_off_lid,
            var_restore_lid=self.var_restore_lid,
            on_toggle=self._on_toggle,
        )

        ttk.Separator(left).pack(fill="x", pady=(14, 10))

        self.dim_sync_panel = DimSyncPanel(
            left,
            var_dim_sync_enabled=self.var_dim_sync_enabled,
            var_dim_sync_mode=self.var_dim_sync_mode,
            var_dim_temp_brightness=self.var_dim_temp_brightness,
            on_toggle=self._on_toggle,
        )

        ttk.Separator(left).pack(fill="x", pady=(14, 10))

        self.power_source_panel = PowerSourcePanel(
            left,
            var_ac_enabled=self.var_ac_enabled,
            var_battery_enabled=self.var_battery_enabled,
            var_ac_brightness=self.var_ac_brightness,
            var_battery_brightness=self.var_battery_brightness,
            on_toggle=self._on_toggle,
        )

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

    def _finalize_layout(self) -> None:
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
        geometry = compute_centered_window_geometry(
            self.root,
            content_height_px=int(self.scroll.frame.winfo_reqheight()),
            content_width_px=int(self.root.winfo_reqwidth()),
            footer_height_px=int(self.bottom_bar.winfo_reqheight()),
            chrome_padding_px=40,
            default_w=1100,
            default_h=850,
            screen_ratio_cap=0.95,
        )
        self.root.geometry(geometry)

    def _apply_enabled_state(self) -> None:
        enabled = bool(self.var_enabled.get())

        self.power_management_panel.apply_enabled_state()
        self.dim_sync_panel.apply_enabled_state(power_management_enabled=enabled)
        self.power_source_panel.apply_enabled_state(power_management_enabled=enabled)

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
