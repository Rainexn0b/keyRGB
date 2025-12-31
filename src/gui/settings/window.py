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

import json
import os
import sys
import webbrowser
from importlib import metadata
from threading import Thread
from urllib.request import Request, urlopen

import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk

from .diagnostics_runner import collect_diagnostics_text
from .os_autostart import detect_os_autostart_enabled, set_os_autostart
from .scrollable_area import ScrollableArea
from .settings_state import SettingsValues, apply_settings_values_to_config, load_settings_values

try:
    from src.legacy.config import Config
except Exception:
    # Fallback for direct execution (e.g. `python src/gui/settings/window.py`).
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    from src.legacy.config import Config

from src.core.version_check import compare_versions, normalize_version_text

from src.gui.window_icon import apply_keyrgb_window_icon


class PowerSettingsGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KeyRGB - Settings")
        apply_keyrgb_window_icon(self.root)
        self.root.minsize(760, 560)
        self.root.resizable(True, True)

        style = ttk.Style()
        style.theme_use("clam")

        bg_color = "#2b2b2b"
        fg_color = "#e0e0e0"

        self.root.configure(bg=bg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
        style.map(
            "TCheckbutton",
            background=[("disabled", bg_color), ("active", bg_color)],
            foreground=[("disabled", "#777777"), ("!disabled", fg_color)],
        )
        style.configure("TButton", background="#404040", foreground=fg_color)
        style.map("TButton", background=[("active", "#505050")])

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

        dim_title = ttk.Label(left, text="Screen dim sync", font=("Sans", 11, "bold"))
        dim_title.pack(anchor="w", pady=(0, 6))

        dim_desc = ttk.Label(
            left,
            text=(
                "Optionally react to your desktop's screen dimming by either\n"
                "turning keyboard LEDs off or dimming them to a temporary brightness."
            ),
            font=("Sans", 9),
        )
        dim_desc.pack(anchor="w", pady=(0, 10))

        self.chk_dim_sync = ttk.Checkbutton(
            left,
            text="Sync keyboard lighting with screen dimming",
            variable=self.var_dim_sync_enabled,
            command=self._on_toggle,
        )
        self.chk_dim_sync.pack(anchor="w", pady=(0, 8))

        dim_mode = ttk.Frame(left)
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

        self.rb_dim_temp = ttk.Radiobutton(
            dim_temp_row,
            text="When dimmed: set brightness to",
            value="temp",
            variable=self.var_dim_sync_mode,
            command=self._on_toggle,
        )
        self.rb_dim_temp.pack(side="left", anchor="w")

        self.lbl_dim_temp_val = ttk.Label(dim_temp_row, text=str(int(self.var_dim_temp_brightness.get())), font=("Sans", 9))
        self.lbl_dim_temp_val.pack(side="right")

        self.scale_dim_temp = ttk.Scale(
            dim_mode,
            from_=1,
            to=50,
            orient="horizontal",
            variable=self.var_dim_temp_brightness,
            command=lambda v: _set_label_int(self.lbl_dim_temp_val, v),
        )
        self.scale_dim_temp.pack(fill="x", pady=(6, 0))
        self.scale_dim_temp.bind("<ButtonRelease-1>", lambda _e: self._on_toggle())

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

        ver_title = ttk.Label(right, text="Version", font=("Sans", 11, "bold"))
        ver_title.pack(anchor="w", pady=(0, 6))

        ver_desc = ttk.Label(
            right,
            text=(
                "Shows your installed KeyRGB version and checks GitHub to see\n"
                "whether you're on the latest tag."
            ),
            font=("Sans", 9),
        )
        ver_desc.pack(anchor="w", pady=(0, 8))

        ver_grid = ttk.Frame(right)
        ver_grid.pack(fill="x", pady=(0, 8))

        ttk.Label(ver_grid, text="Installed", font=("Sans", 9)).grid(row=0, column=0, sticky="w")
        self.lbl_installed_version = ttk.Label(ver_grid, text="?", font=("Sans", 9))
        self.lbl_installed_version.grid(row=0, column=1, sticky="w", padx=(10, 0))

        ttk.Label(ver_grid, text="Latest", font=("Sans", 9)).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.lbl_latest_version = ttk.Label(ver_grid, text="Checking…", font=("Sans", 9))
        self.lbl_latest_version.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(4, 0))

        self.lbl_update_status = ttk.Label(right, text="", font=("Sans", 9))
        self.lbl_update_status.pack(anchor="w", pady=(0, 8))

        ver_btn_row = ttk.Frame(right)
        ver_btn_row.pack(fill="x", pady=(0, 2))

        self.btn_open_repo = ttk.Button(ver_btn_row, text="Open repo", command=self._open_repo)
        self.btn_open_repo.pack(side="left")

        self._init_version_section()
        self._start_latest_version_check()

        ttk.Separator(right).pack(fill="x", pady=(14, 10))

        as_title = ttk.Label(right, text="Autostart", font=("Sans", 11, "bold"))
        as_title.pack(anchor="w", pady=(0, 6))

        as_desc = ttk.Label(
            right,
            text=(
                "Control what happens when KeyRGB launches, and whether it\n"
                "starts automatically when you log in."
            ),
            font=("Sans", 9),
        )
        as_desc.pack(anchor="w", pady=(0, 8))

        self.chk_autostart = ttk.Checkbutton(
            right,
            text="Start lighting on launch",
            variable=self.var_autostart,
            command=self._on_toggle,
        )
        self.chk_autostart.pack(anchor="w")

        self.chk_os_autostart = ttk.Checkbutton(
            right,
            text="Start KeyRGB on login",
            variable=self.var_os_autostart,
            command=self._on_toggle,
        )
        self.chk_os_autostart.pack(anchor="w", pady=(6, 0))

        ttk.Separator(right).pack(fill="x", pady=(14, 10))

        diag_title = ttk.Label(right, text="Diagnostics", font=("Sans", 11, "bold"))
        diag_title.pack(anchor="w", pady=(0, 6))

        diag_desc = ttk.Label(
            right,
            text=(
                "Collect read-only system information to include in bug reports.\n"
                "This works even if hardware detection fails."
            ),
            font=("Sans", 9),
        )
        diag_desc.pack(anchor="w", pady=(0, 8))

        diag_btn_row = ttk.Frame(right)
        diag_btn_row.pack(fill="x", pady=(0, 8))

        self.btn_run_diagnostics = ttk.Button(diag_btn_row, text="Run diagnostics", command=self._run_diagnostics)
        self.btn_run_diagnostics.pack(side="left")

        self.btn_copy_diagnostics = ttk.Button(diag_btn_row, text="Copy output", command=self._copy_diagnostics)
        self.btn_copy_diagnostics.pack(side="left", padx=(8, 0))

        self.btn_open_issue = ttk.Button(diag_btn_row, text="Open issue", command=self._open_issue_form)
        self.btn_open_issue.pack(side="left", padx=(8, 0))

        self._diagnostics_json: str = ""

        self.txt_diagnostics = scrolledtext.ScrolledText(
            right,
            height=8,
            wrap="word",
            background=bg_color,
            foreground=fg_color,
            insertbackground=fg_color,
        )
        self.txt_diagnostics.pack(fill="both", expand=True)
        self.txt_diagnostics.insert(
            "1.0",
            "Click 'Run diagnostics', then use 'Copy output' or 'Open issue'.\n",
        )
        self.txt_diagnostics.configure(state="disabled")

        self.bottom_bar = ttk.Frame(outer, padding=(16, 8, 16, 12))
        self.bottom_bar.pack(fill="x")

        self.status = ttk.Label(self.bottom_bar, text="", font=("Sans", 9))
        self.status.pack(side="left")

        close_btn = ttk.Button(self.bottom_bar, text="Close", command=self._on_close)
        close_btn.pack(side="right")

        self._apply_enabled_state()
        self._apply_diagnostics_state()

        # Bind wheel globally within this Tk app, but filter to this toplevel + pointer location.
        self.scroll.bind_mousewheel(self.root, priority_scroll_widget=self.txt_diagnostics)

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

    def _installed_version_text(self) -> str:
        try:
            v = metadata.version("keyrgb")
        except Exception:
            return "unknown"

        v_norm = normalize_version_text(v) or str(v).strip()
        return f"v{v_norm}" if not str(v).strip().lower().startswith("v") else str(v).strip()

    def _init_version_section(self) -> None:
        self._installed_version = self._installed_version_text()
        self.lbl_installed_version.configure(text=self._installed_version)
        self.lbl_latest_version.configure(text="Checking…")
        self.lbl_update_status.configure(text="")

    def _fetch_latest_github_tag(self) -> str | None:
        # Best-effort: releases can be behind, so prefer tags.
        urls = [
            "https://api.github.com/repos/Rainexn0b/keyRGB/tags?per_page=1",
            "https://api.github.com/repos/Rainexn0b/keyRGB/releases/latest",
        ]

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "keyrgb",
        }

        for url in urls:
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=3.0) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)

                if isinstance(data, list) and data:
                    first = data[0]
                    name = first.get("name") if isinstance(first, dict) else None
                    if isinstance(name, str) and name.strip():
                        return name.strip()

                if isinstance(data, dict):
                    tag_name = data.get("tag_name")
                    if isinstance(tag_name, str) and tag_name.strip():
                        return tag_name.strip()
            except Exception:
                continue

        return None

    def _apply_latest_version_result(self, latest_tag: str | None) -> None:
        if not latest_tag:
            self.lbl_latest_version.configure(text="Unknown")
            self.lbl_update_status.configure(text="Couldn't check GitHub")
            return

        latest_norm = normalize_version_text(latest_tag) or latest_tag
        latest_display = f"v{latest_norm}" if not str(latest_tag).lower().startswith("v") else str(latest_tag)
        self.lbl_latest_version.configure(text=latest_display)

        cmp = compare_versions(self._installed_version, latest_display)
        if cmp is None:
            self.lbl_update_status.configure(text="Couldn't compare versions")
        elif cmp == 0:
            self.lbl_update_status.configure(text="✓ You are on the latest version")
        elif cmp < 0:
            self.lbl_update_status.configure(text=f"Update available: {latest_display}")
        else:
            self.lbl_update_status.configure(text="You are ahead of the latest tag")

    def _start_latest_version_check(self) -> None:
        def worker() -> None:
            latest = self._fetch_latest_github_tag()
            self.root.after(0, lambda: self._apply_latest_version_result(latest))

        Thread(target=worker, daemon=True).start()

    def _open_repo(self) -> None:
        url = "https://github.com/Rainexn0b/keyRGB"
        try:
            ok = bool(webbrowser.open(url, new=2))
        except Exception:
            ok = False

        if ok:
            self.status.configure(text="Opened repo")
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.status.configure(text="Couldn't open browser (URL copied)")
        self.root.after(2000, lambda: self.status.configure(text=""))

    def _apply_enabled_state(self) -> None:
        enabled = bool(self.var_enabled.get())
        state = "normal" if enabled else "disabled"
        for w in (
            self.chk_off_suspend,
            self.chk_restore_resume,
            self.chk_off_lid,
            self.chk_restore_lid,
            self.chk_dim_sync,
            self.rb_dim_off,
            self.rb_dim_temp,
            self.scale_dim_temp,
            self.chk_ac_enabled,
            self.chk_battery_enabled,
            self.scale_ac_brightness,
            self.scale_battery_brightness,
        ):
            w.configure(state=state)

        # Additional gating: dim temp brightness scale only makes sense in temp mode.
        if enabled and bool(self.var_dim_sync_enabled.get()) and str(self.var_dim_sync_mode.get()) == "temp":
            self.scale_dim_temp.configure(state="normal")
        else:
            self.scale_dim_temp.configure(state="disabled")

    def _apply_diagnostics_state(self) -> None:
        self.btn_copy_diagnostics.configure(state="normal" if self._diagnostics_json else "disabled")

    def _set_diagnostics_text(self, text: str) -> None:
        self.txt_diagnostics.configure(state="normal")
        self.txt_diagnostics.delete("1.0", "end")
        self.txt_diagnostics.insert("1.0", text)
        self.txt_diagnostics.configure(state="disabled")

    def _run_diagnostics(self) -> None:
        self.status.configure(text="Collecting diagnostics…")
        self.btn_run_diagnostics.configure(state="disabled")
        self.btn_copy_diagnostics.configure(state="disabled")

        def worker() -> None:
            try:
                text = collect_diagnostics_text(include_usb=True)
            except Exception as e:
                text = f"Failed to collect diagnostics: {e}"

            def on_done() -> None:
                self._diagnostics_json = text if text.strip().startswith("{") else ""
                self._set_diagnostics_text(text)
                self.btn_run_diagnostics.configure(state="normal")
                self._apply_diagnostics_state()
                if '"warnings"' in text:
                    self.status.configure(text="⚠ Diagnostics ready (warnings)")
                else:
                    self.status.configure(text="✓ Diagnostics ready")
                self.root.after(2000, lambda: self.status.configure(text=""))

            self.root.after(0, on_done)

        Thread(target=worker, daemon=True).start()

    def _copy_diagnostics(self) -> None:
        if not self._diagnostics_json:
            self.status.configure(text="Run diagnostics first")
            self.root.after(1500, lambda: self.status.configure(text=""))
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(self._diagnostics_json)
        self.status.configure(text="✓ Copied to clipboard")
        self.root.after(1500, lambda: self.status.configure(text=""))

    def _open_issue_form(self) -> None:
        url = "https://github.com/Rainexn0b/keyRGB/issues/new/choose"
        try:
            ok = bool(webbrowser.open(url, new=2))
        except Exception:
            ok = False

        if ok:
            self.status.configure(text="Opened issue form")
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.status.configure(text="Couldn't open browser (URL copied)")
        self.root.after(2000, lambda: self.status.configure(text=""))

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
