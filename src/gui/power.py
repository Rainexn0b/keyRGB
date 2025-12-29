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
from pathlib import Path

import tkinter as tk
from tkinter import ttk

try:
    from src.legacy.config import Config
except Exception:
    # Fallback for direct execution (e.g. `python src/gui/power.py`).
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.legacy.config import Config


class PowerSettingsGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("KeyRGB - Settings")
        self.root.geometry("420x520")
        # Allow vertical resize for systems with larger fonts / window chrome.
        self.root.resizable(False, True)

        # Match the existing dark-ish styling used by other KeyRGB Tk windows.
        style = ttk.Style()
        style.theme_use("clam")

        bg_color = "#2b2b2b"
        fg_color = "#e0e0e0"

        self.root.configure(bg=bg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
        # Fix dark-mode highlight/disabled rendering: keep background dark for all states.
        style.map(
            "TCheckbutton",
            background=[("disabled", bg_color), ("active", bg_color)],
            foreground=[("disabled", "#777777"), ("!disabled", fg_color)],
        )
        style.configure("TButton", background="#404040", foreground=fg_color)
        style.map("TButton", background=[("active", "#505050")])

        self.config = Config()

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Settings", font=("Sans", 14, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        pm_title = ttk.Label(main, text="Power Management", font=("Sans", 11, "bold"))
        pm_title.pack(anchor="w", pady=(0, 6))

        desc = ttk.Label(
            main,
            text=(
                "Control whether KeyRGB turns the keyboard LEDs off/on\n"
                "when the lid closes/opens or the system suspends/resumes."
            ),
            font=("Sans", 9),
        )
        desc.pack(anchor="w", pady=(0, 12))

        self.var_enabled = tk.BooleanVar(value=bool(getattr(self.config, "power_management_enabled", True)))
        self.var_off_suspend = tk.BooleanVar(value=bool(getattr(self.config, "power_off_on_suspend", True)))
        self.var_off_lid = tk.BooleanVar(value=bool(getattr(self.config, "power_off_on_lid_close", True)))
        self.var_restore_resume = tk.BooleanVar(value=bool(getattr(self.config, "power_restore_on_resume", True)))
        self.var_restore_lid = tk.BooleanVar(value=bool(getattr(self.config, "power_restore_on_lid_open", True)))
        self.var_autostart = tk.BooleanVar(value=bool(getattr(self.config, "autostart", True)))
        self.var_os_autostart = tk.BooleanVar(value=self._detect_os_autostart_enabled())

        self.chk_enabled = ttk.Checkbutton(
            main,
            text="Enable power management",
            variable=self.var_enabled,
            command=self._on_toggle,
        )
        self.chk_enabled.pack(anchor="w", pady=(0, 8))

        self.chk_off_suspend = ttk.Checkbutton(
            main,
            text="Turn off on suspend",
            variable=self.var_off_suspend,
            command=self._on_toggle,
        )
        self.chk_off_suspend.pack(anchor="w")

        self.chk_restore_resume = ttk.Checkbutton(
            main,
            text="Restore on resume",
            variable=self.var_restore_resume,
            command=self._on_toggle,
        )
        self.chk_restore_resume.pack(anchor="w")

        self.chk_off_lid = ttk.Checkbutton(
            main,
            text="Turn off on lid close",
            variable=self.var_off_lid,
            command=self._on_toggle,
        )
        self.chk_off_lid.pack(anchor="w", pady=(8, 0))

        self.chk_restore_lid = ttk.Checkbutton(
            main,
            text="Restore on lid open",
            variable=self.var_restore_lid,
            command=self._on_toggle,
        )
        self.chk_restore_lid.pack(anchor="w")

        ttk.Separator(main).pack(fill="x", pady=(14, 10))

        as_title = ttk.Label(main, text="Autostart", font=("Sans", 11, "bold"))
        as_title.pack(anchor="w", pady=(0, 6))

        as_desc = ttk.Label(
            main,
            text=(
                "Control what happens when KeyRGB launches, and whether it\n"
                "starts automatically when you log in."
            ),
            font=("Sans", 9),
        )
        as_desc.pack(anchor="w", pady=(0, 8))

        self.chk_autostart = ttk.Checkbutton(
            main,
            text="Start lighting on launch",
            variable=self.var_autostart,
            command=self._on_toggle,
        )
        self.chk_autostart.pack(anchor="w")

        self.chk_os_autostart = ttk.Checkbutton(
            main,
            text="Start KeyRGB on login",
            variable=self.var_os_autostart,
            command=self._on_toggle,
        )
        self.chk_os_autostart.pack(anchor="w", pady=(6, 0))

        btn_row = ttk.Frame(main)
        btn_row.pack(fill="x", pady=(16, 0))

        close_btn = ttk.Button(btn_row, text="Close", command=self._on_close)
        close_btn.pack(side="right")

        self.status = ttk.Label(main, text="", font=("Sans", 9))
        self.status.pack(anchor="w", pady=(8, 0))

        self._apply_enabled_state()

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
        self.root.geometry(f"+{x}+{y}")

    def _apply_enabled_state(self) -> None:
        enabled = bool(self.var_enabled.get())
        state = "normal" if enabled else "disabled"
        for w in (
            self.chk_off_suspend,
            self.chk_restore_resume,
            self.chk_off_lid,
            self.chk_restore_lid,
        ):
            w.configure(state=state)

    def _on_toggle(self) -> None:
        self.config.power_management_enabled = bool(self.var_enabled.get())
        self.config.power_off_on_suspend = bool(self.var_off_suspend.get())
        self.config.power_off_on_lid_close = bool(self.var_off_lid.get())
        self.config.power_restore_on_resume = bool(self.var_restore_resume.get())
        self.config.power_restore_on_lid_open = bool(self.var_restore_lid.get())
        self.config.autostart = bool(self.var_autostart.get())

        # Best-effort OS autostart (XDG). If it fails, revert the checkbox.
        desired_os_autostart = bool(self.var_os_autostart.get())
        try:
            self._set_os_autostart(desired_os_autostart)
            self.config.os_autostart = desired_os_autostart
        except Exception:
            # Re-sync to actual state on error.
            self.var_os_autostart.set(self._detect_os_autostart_enabled())

        self._apply_enabled_state()

        self.status.configure(text="✓ Saved")
        self.root.after(1500, lambda: self.status.configure(text=""))

    @staticmethod
    def _autostart_desktop_path() -> Path:
        return Path.home() / ".config" / "autostart" / "keyrgb.desktop"

    def _detect_os_autostart_enabled(self) -> bool:
        try:
            return self._autostart_desktop_path().exists()
        except Exception:
            return False

    def _set_os_autostart(self, enabled: bool) -> None:
        desktop_path = self._autostart_desktop_path()
        if not enabled:
            try:
                desktop_path.unlink(missing_ok=True)
            except Exception:
                # If removal fails, surface as error.
                raise
            return

        desktop_path.parent.mkdir(parents=True, exist_ok=True)

        # Use the installed console script entrypoint.
        desktop_contents = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=KeyRGB\n"
            "Comment=Keyboard RGB tray\n"
            "Exec=keyrgb\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )

        desktop_path.write_text(desktop_contents, encoding="utf-8")

    def _on_close(self) -> None:
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    PowerSettingsGUI().run()


if __name__ == "__main__":
    main()
