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
import webbrowser
from threading import Thread

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


class PowerSettingsGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KeyRGB - Settings")
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

        scroll = ScrollableArea(content_area, bg_color=bg_color, padding=16)
        main = scroll.frame

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

        bottom_bar = ttk.Frame(outer, padding=(16, 8, 16, 12))
        bottom_bar.pack(fill="x")

        self.status = ttk.Label(bottom_bar, text="", font=("Sans", 9))
        self.status.pack(side="left")

        close_btn = ttk.Button(bottom_bar, text="Close", command=self._on_close)
        close_btn.pack(side="right")

        self._apply_enabled_state()
        self._apply_diagnostics_state()

        # Bind wheel globally within this Tk app, but filter to this toplevel + pointer location.
        scroll.bind_mousewheel(self.root, priority_scroll_widget=self.txt_diagnostics)

        # Size-to-content, but clamp to the current screen so nothing is forced off-screen.
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        req_w = outer.winfo_reqwidth()
        req_h = outer.winfo_reqheight()

        margin_w = 80
        margin_h = 120

        default_w = 980
        default_h = 720

        width = min(max(req_w, default_w), max(320, screen_w - margin_w))
        height = min(max(req_h, default_h), max(320, screen_h - margin_h))

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.root.update_idletasks()
        try:
            scroll.canvas.configure(scrollregion=scroll.canvas.bbox("all"))
        except Exception:
            pass

        scroll.finalize_initial_scrollbar_state()

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
