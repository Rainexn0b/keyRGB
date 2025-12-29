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
from pathlib import Path
from threading import Thread

import tkinter as tk
from tkinter import scrolledtext
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
        # Layout is content-driven; initial size is computed after widgets are created.
        self.root.minsize(760, 560)
        self.root.resizable(True, True)

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

        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True)

        # Scrollable content area (prevents sections from being cut off on smaller screens)
        # with a fixed bottom bar for Close/status.
        content_area = ttk.Frame(outer)
        content_area.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(content_area, highlightthickness=0, bg=bg_color)
        self._vscroll = ttk.Scrollbar(content_area, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vscroll.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        # Scrollbar is conditionally shown based on content height.
        self._vscroll_visible = True
        self._vscroll.pack(side="right", fill="y")

        main = ttk.Frame(self._canvas, padding=16)
        self._main_window_id = self._canvas.create_window((0, 0), window=main, anchor="nw")

        def _sync_scrollregion(_event=None) -> None:
            try:
                self._canvas.configure(scrollregion=self._canvas.bbox("all"))
            except Exception:
                pass

            _update_scrollbar_visibility()

        def _sync_content_width(event) -> None:
            # Keep content frame width in sync with the canvas, avoiding horizontal scrolling.
            try:
                self._canvas.itemconfigure(self._main_window_id, width=event.width)
            except Exception:
                pass

            _update_scrollbar_visibility()

        def _content_needs_scroll() -> bool:
            try:
                bbox = self._canvas.bbox("all")
                if not bbox:
                    return False
                content_h = bbox[3] - bbox[1]
                canvas_h = self._canvas.winfo_height()
                return content_h > max(1, canvas_h)
            except Exception:
                return False

        def _update_scrollbar_visibility() -> None:
            # Hide the scrollbar when everything fits.
            try:
                needs_scroll = _content_needs_scroll()

                if needs_scroll and not self._vscroll_visible:
                    self._vscroll.pack(side="right", fill="y")
                    self._vscroll_visible = True
                elif (not needs_scroll) and self._vscroll_visible:
                    self._vscroll.pack_forget()
                    self._vscroll_visible = False
            except Exception:
                pass

        main.bind("<Configure>", _sync_scrollregion)
        self._canvas.bind("<Configure>", _sync_content_width)

        def _is_descendant(widget: tk.Misc, ancestor: tk.Misc) -> bool:
            cur = widget
            while cur is not None:
                if cur == ancestor:
                    return True
                try:
                    cur = cur.master  # type: ignore[assignment]
                except Exception:
                    break
            return False

        def _on_mousewheel(event) -> str | None:
            # Handle scrolling reliably without depending on fragile Enter/Leave bindings.
            try:
                # Only act if the pointer is over this window.
                x_root = getattr(event, "x_root", None)
                y_root = getattr(event, "y_root", None)
                if x_root is None or y_root is None:
                    return None

                target = self.root.winfo_containing(x_root, y_root)
                if target is None or target.winfo_toplevel() != self.root:
                    return None

                # Determine scroll direction/amount.
                units: int | None = None
                if getattr(event, "num", None) == 4:
                    units = -1
                elif getattr(event, "num", None) == 5:
                    units = 1
                elif hasattr(event, "delta") and event.delta:
                    units = int(-1 * (event.delta / 120))

                if not units:
                    return None

                # Prefer scrolling the diagnostics text box if the pointer is over it.
                if _is_descendant(target, self.txt_diagnostics):
                    try:
                        self.txt_diagnostics.yview_scroll(units, "units")
                        return "break"
                    except Exception:
                        return None

                # Otherwise scroll the main canvas if content overflows.
                if _content_needs_scroll():
                    self._canvas.yview_scroll(units, "units")
                    return "break"

                return None
            except Exception:
                return None

        # Bind wheel globally within this Tk app, but filter to this toplevel + pointer location.
        self.root.bind_all("<MouseWheel>", _on_mousewheel)
        self.root.bind_all("<Button-4>", _on_mousewheel)
        self.root.bind_all("<Button-5>", _on_mousewheel)

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

        self.var_enabled = tk.BooleanVar(value=bool(getattr(self.config, "power_management_enabled", True)))
        self.var_off_suspend = tk.BooleanVar(value=bool(getattr(self.config, "power_off_on_suspend", True)))
        self.var_off_lid = tk.BooleanVar(value=bool(getattr(self.config, "power_off_on_lid_close", True)))
        self.var_restore_resume = tk.BooleanVar(value=bool(getattr(self.config, "power_restore_on_resume", True)))
        self.var_restore_lid = tk.BooleanVar(value=bool(getattr(self.config, "power_restore_on_lid_open", True)))
        self.var_autostart = tk.BooleanVar(value=bool(getattr(self.config, "autostart", True)))
        self.var_os_autostart = tk.BooleanVar(value=self._detect_os_autostart_enabled())

        # Power-source lighting defaults: if no explicit overrides exist, seed UI with
        # effective current values so saving doesn't change behavior unexpectedly.
        try:
            base_brightness = int(getattr(self.config, "brightness", 25) or 0)
        except Exception:
            base_brightness = 25

        try:
            bs_enabled = bool(getattr(self.config, "battery_saver_enabled", False))
        except Exception:
            bs_enabled = False

        try:
            bs_brightness = int(getattr(self.config, "battery_saver_brightness", 25) or 0)
        except Exception:
            bs_brightness = 25

        try:
            ac_b = getattr(self.config, "ac_lighting_brightness", None)
        except Exception:
            ac_b = None
        ac_b_init = int(ac_b) if ac_b is not None else int(base_brightness)

        try:
            batt_b = getattr(self.config, "battery_lighting_brightness", None)
        except Exception:
            batt_b = None
        if batt_b is not None:
            batt_b_init = int(batt_b)
        else:
            batt_b_init = int(bs_brightness) if bs_enabled else int(base_brightness)

        self.var_ac_enabled = tk.BooleanVar(value=bool(getattr(self.config, "ac_lighting_enabled", True)))
        self.var_battery_enabled = tk.BooleanVar(value=bool(getattr(self.config, "battery_lighting_enabled", True)))
        self.var_ac_brightness = tk.DoubleVar(value=float(max(0, min(50, ac_b_init))))
        self.var_battery_brightness = tk.DoubleVar(value=float(max(0, min(50, batt_b_init))))

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

        self._diagnostics_json: str = ""

        self.txt_diagnostics = scrolledtext.ScrolledText(
            right,
            height=8,
            wrap="word",
            background=bg_color,
            foreground=fg_color,
            insertbackground=fg_color,
        )
        # Keep a stable initial size; the window itself (and content area) is scrollable.
        self.txt_diagnostics.pack(fill="both", expand=True)
        self.txt_diagnostics.insert(
            "1.0",
            "Click 'Run diagnostics' then 'Copy output' and paste into a GitHub issue.\n",
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

        # Size-to-content, but clamp to the current screen so nothing is forced off-screen.
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        req_w = outer.winfo_reqwidth()
        req_h = outer.winfo_reqheight()

        margin_w = 80
        margin_h = 120

        # Default to a comfortably wide/tall window so the two-column layout
        # doesn't feel cramped on first open, but still clamp to screen size.
        default_w = 980
        default_h = 720

        width = min(max(req_w, default_w), max(320, screen_w - margin_w))
        height = min(max(req_h, default_h), max(320, screen_h - margin_h))

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # Ensure scroll region is correct after the final geometry.
        self.root.update_idletasks()
        try:
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        except Exception:
            pass

        # Ensure scrollbar visibility matches initial geometry.
        try:
            bbox = self._canvas.bbox("all")
            if bbox:
                content_h = bbox[3] - bbox[1]
                needs_scroll = content_h > max(1, self._canvas.winfo_height())
                if not needs_scroll and self._vscroll_visible:
                    self._vscroll.pack_forget()
                    self._vscroll_visible = False
        except Exception:
            pass

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
        # Copy is only useful once we have JSON content.
        self.btn_copy_diagnostics.configure(state="normal" if self._diagnostics_json else "disabled")

    def _set_diagnostics_text(self, text: str) -> None:
        self.txt_diagnostics.configure(state="normal")
        self.txt_diagnostics.delete("1.0", "end")
        self.txt_diagnostics.insert("1.0", text)
        self.txt_diagnostics.configure(state="disabled")

    def _run_diagnostics(self) -> None:
        # Collect in a background thread to keep the UI responsive.
        self.status.configure(text="Collecting diagnostics…")
        self.btn_run_diagnostics.configure(state="disabled")
        self.btn_copy_diagnostics.configure(state="disabled")

        def worker() -> None:
            try:
                try:
                    from src.core.diagnostics import collect_diagnostics
                except Exception:
                    # Fallback for direct execution.
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    from src.core.diagnostics import collect_diagnostics

                diag = collect_diagnostics(include_usb=True)
                payload = diag.to_dict()

                warnings: list[str] = []
                expected_holder_pids: set[int] = set()
                try:
                    tray_pid = os.environ.get("KEYRGB_TRAY_PID")
                    if tray_pid:
                        expected_holder_pids.add(int(tray_pid))
                except Exception:
                    expected_holder_pids = set()

                # Fallback: if the tray didn't set KEYRGB_TRAY_PID (older build)
                # and Settings was launched as a subprocess, the parent PID is
                # typically the tray. Treat parent 'keyrgb' as expected.
                try:
                    if not expected_holder_pids:
                        ppid = int(os.getppid())
                        comm_path = Path(f"/proc/{ppid}/comm")
                        if comm_path.exists():
                            parent_comm = comm_path.read_text(encoding="utf-8", errors="ignore").strip()
                            if parent_comm == "keyrgb":
                                expected_holder_pids.add(ppid)
                except Exception:
                    pass
                try:
                    usb_devices = payload.get("usb_devices")
                    if isinstance(usb_devices, list):
                        for dev in usb_devices:
                            if not isinstance(dev, dict):
                                continue
                            others = dev.get("devnode_open_by_others")
                            if not isinstance(others, list) or not others:
                                continue

                            # Filter out the tray process when Settings is launched
                            # from the tray. In that case, the tray holding the
                            # device is expected and not a conflict.
                            if expected_holder_pids:
                                filtered: list[dict[str, object]] = []
                                for h in others:
                                    if not isinstance(h, dict):
                                        continue
                                    pid = h.get("pid")
                                    try:
                                        if pid is not None and int(pid) in expected_holder_pids:
                                            continue
                                    except Exception:
                                        pass
                                    filtered.append(h)
                                others = filtered

                            if not others:
                                continue

                            devnode = dev.get("devnode") or dev.get("sysfs_path") or "(unknown)"
                            summaries: list[str] = []
                            for h in others:
                                if not isinstance(h, dict):
                                    continue
                                pid = h.get("pid")
                                comm = h.get("comm")
                                exe = h.get("exe")
                                parts = []
                                if pid is not None:
                                    parts.append(f"pid={pid}")
                                if comm:
                                    parts.append(f"comm={comm}")
                                if exe:
                                    parts.append(f"exe={exe}")
                                if parts:
                                    summaries.append(" ".join(parts))

                            if summaries:
                                warnings.append(
                                    f"Device busy: {devnode} is open by other process(es): " + "; ".join(summaries)
                                )
                            else:
                                warnings.append(f"Device busy: {devnode} is open by other process(es)")
                except Exception:
                    pass

                if warnings:
                    payload["warnings"] = warnings

                text = json.dumps(payload, indent=2, sort_keys=True)
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

    def _on_toggle(self) -> None:
        self.config.power_management_enabled = bool(self.var_enabled.get())
        self.config.power_off_on_suspend = bool(self.var_off_suspend.get())
        self.config.power_off_on_lid_close = bool(self.var_off_lid.get())
        self.config.power_restore_on_resume = bool(self.var_restore_resume.get())
        self.config.power_restore_on_lid_open = bool(self.var_restore_lid.get())
        self.config.autostart = bool(self.var_autostart.get())

        # Plugged-in vs battery lighting profile.
        try:
            self.config.ac_lighting_enabled = bool(self.var_ac_enabled.get())
            self.config.battery_lighting_enabled = bool(self.var_battery_enabled.get())

            ac_b = int(float(self.var_ac_brightness.get()))
            batt_b = int(float(self.var_battery_brightness.get()))
            self.config.ac_lighting_brightness = max(0, min(50, ac_b))
            self.config.battery_lighting_brightness = max(0, min(50, batt_b))
        except Exception:
            pass

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
