#!/usr/bin/env python3
"""KeyRGB Per-Key Editor (Tkinter)"""

from __future__ import annotations

import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk
import subprocess
from pathlib import Path

from src.gui.widgets.color_wheel import ColorWheel
from src.legacy.config import Config
from src.core.layout import BASE_IMAGE_SIZE, Y15_PRO_KEYS, KeyDef
from src.core import profiles

from .canvas import KeyboardCanvas
from .overlay import OverlayControls

try:
    from ite8291r3_ctl.ite8291r3 import get, NUM_ROWS, NUM_COLS
except Exception:
    # Repo fallback if dependency wasn't installed.
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    vendored = repo_root / "ite8291r3-ctl"
    if vendored.exists():
        sys.path.insert(0, str(vendored))
    try:
        from ite8291r3_ctl.ite8291r3 import get, NUM_ROWS, NUM_COLS
    except Exception:
        get = None
        NUM_ROWS, NUM_COLS = 6, 21


class PerKeyEditor:
    def __init__(self):
        self._key_size = 28
        self._key_gap = 2
        self._key_margin = 8
        self._wheel_size = 240
        self._right_panel_width = 320
        self._resize_job = None

        self.root = tk.Tk()
        self.root.title("KeyRGB - Per-Key Colors")
        self.root.update_idletasks()

        keyboard_w = (self._key_margin * 2) + (NUM_COLS * self._key_size) + ((NUM_COLS - 1) * self._key_gap)
        keyboard_h = (self._key_margin * 2) + (NUM_ROWS * self._key_size) + ((NUM_ROWS - 1) * self._key_gap)

        chrome_w = 16 * 2 + 16
        chrome_h = 16 * 2 + 80

        w0 = keyboard_w + self._right_panel_width + chrome_w
        h0 = max(keyboard_h + chrome_h, self._wheel_size + 420)

        screen_w = int(self.root.winfo_screenwidth())
        screen_h = int(self.root.winfo_screenheight())
        max_w = int(screen_w * 0.92)
        max_h = int(screen_h * 0.92)

        w = min(int(w0 * 1.5), max_w)
        h = min(int(h0 * 1.5), max_h)

        self.root.geometry(f"{w}x{h}")
        self.root.minsize(min(w0, max_w), min(h0, max_h))

        style = ttk.Style()
        style.theme_use("clam")

        self.bg_color = "#2b2b2b"
        self.fg_color = "#e0e0e0"

        self.root.configure(bg=self.bg_color)
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color)
        style.configure("TButton", background="#404040", foreground=self.fg_color)
        style.map("TButton", background=[("active", "#505050")])

        self.config = Config()
        self.colors: dict[tuple[int, int], tuple[int, int, int]] = dict(self.config.per_key_colors)

        self.profile_name = profiles.get_active_profile()

        self.keymap: dict[str, tuple[int, int]] = self._load_keymap()
        self.layout_tweaks = self._load_layout_tweaks()
        self.per_key_layout_tweaks: dict[str, dict[str, float]] = self._load_per_key_layout_tweaks()
        
        self.overlay_scope = tk.StringVar(value="global")  # global | key
        self._profiles_visible = False
        self._profile_name_var = tk.StringVar(value=self.profile_name)
        self.selected_key_id: str | None = None
        self.selected_cell: tuple[int, int] | None = None

        self._last_commit_ts = 0.0
        self._commit_interval = 0.06

        self.kb = None
        if get is not None:
            try:
                self.kb = get()
            except Exception:
                self.kb = None

        self._build_ui()
        self.canvas.redraw()

        if not self.keymap:
            self.status_label.config(text="No keymap found — click 'Run Keymap Calibrator'")

        self.root.bind("<FocusIn>", lambda _e: self._reload_keymap())

        for kd in Y15_PRO_KEYS:
            if kd.key_id in self.keymap:
                self.select_key_id(kd.key_id)
                break

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Per-Key Keyboard Colors", font=("Sans", 14, "bold"))
        title.pack(pady=(0, 10))

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)

        left = ttk.Frame(content)
        left.pack(side="left", fill="both", expand=True)

        canvas_frame = ttk.Frame(left)
        canvas_frame.pack(fill="both", expand=True)

        self.canvas = KeyboardCanvas(
            canvas_frame,
            editor=self,
            bg=self.bg_color,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill="both", expand=True)

        right = ttk.Frame(content, width=self._right_panel_width)
        right.pack(side="left", fill="y", padx=(16, 0))
        right.pack_propagate(False)

        self.status_label = ttk.Label(right, text="Click a key to start", font=("Sans", 9), width=32)
        self.status_label.pack(pady=(0, 8))

        initial = (
            tuple(self.config.color)
            if isinstance(self.config.color, (list, tuple)) and len(self.config.color) == 3
            else (255, 0, 0)
        )
        self.color_wheel = ColorWheel(
            right,
            size=self._wheel_size,
            initial_color=initial,
            callback=self._on_color_change,
            release_callback=self._on_color_release,
        )
        self.color_wheel.pack()

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=12)
        ttk.Button(btns, text="Fill All", command=self._fill_all).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Clear All", command=self._clear_all).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Run Keymap Calibrator", command=self._run_calibrator).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Reload Keymap", command=self._reload_keymap).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Profiles", command=self._toggle_profiles).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Close", command=self.root.destroy).pack(fill="x")

        self._profiles_frame = ttk.LabelFrame(right, text="Profiles", padding=10)

        ttk.Label(self._profiles_frame, text="Profile").grid(row=0, column=0, sticky="w")
        self._profiles_combo = ttk.Combobox(
            self._profiles_frame,
            textvariable=self._profile_name_var,
            values=profiles.list_profiles(),
            width=22,
        )
        self._profiles_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self._profiles_frame.columnconfigure(1, weight=1)

        pbtns = ttk.Frame(self._profiles_frame)
        pbtns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        pbtns.columnconfigure(0, weight=1)
        pbtns.columnconfigure(1, weight=1)
        pbtns.columnconfigure(2, weight=1)

        ttk.Button(pbtns, text="Activate", command=self._activate_profile).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(pbtns, text="Save", command=self._save_profile).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(pbtns, text="Delete", command=self._delete_profile).grid(row=0, column=2, sticky="ew")

        self.overlay_controls = OverlayControls(right, editor=self)
        self.overlay_controls.pack(fill="x", pady=(6, 0))
        self.overlay_controls.sync_vars_from_scope()

    def select_key_id(self, key_id: str):
        self.selected_key_id = key_id
        self.selected_cell = self.keymap.get(key_id)

        if self.overlay_scope.get() == "key":
            self.overlay_controls.sync_vars_from_scope()

        if self.selected_cell is None:
            self.status_label.config(text=f"Selected {key_id} (unmapped) — run keymap calibrator")
            self.canvas.redraw()
            return

        row, col = self.selected_cell
        color = self.colors.get((row, col), (0, 0, 0))
        self.color_wheel.set_color(*color)
        self.status_label.config(text=f"Selected {key_id} -> {row},{col}")
        self.canvas.redraw()

    def sync_overlay_vars(self):
        self.overlay_controls.sync_vars_from_scope()

    def save_layout_tweaks(self):
        if self.overlay_scope.get() == "key" and self.selected_key_id:
            profiles.save_layout_per_key(self.per_key_layout_tweaks, self.profile_name)
            self.status_label.config(text=f"Saved overlay tweaks for {self.selected_key_id}")
        else:
            profiles.save_layout_global(self.layout_tweaks, self.profile_name)
            self.status_label.config(text="Saved global overlay alignment tweaks")

    def reset_layout_tweaks(self):
        if self.overlay_scope.get() == "key" and self.selected_key_id:
            self.per_key_layout_tweaks.pop(self.selected_key_id, None)
            self.overlay_controls.sync_vars_from_scope()
            self.canvas.redraw()
            self.status_label.config(text=f"Reset overlay tweaks for {self.selected_key_id}")
            return

        self.layout_tweaks = {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
        self.overlay_controls.sync_vars_from_scope()
        self.canvas.redraw()
        self.status_label.config(text="Reset global overlay alignment tweaks")

    def _run_calibrator(self):
        parent_path = os.path.dirname(os.path.dirname(__file__))
        try:
            subprocess.Popen([sys.executable, "-m", "src.gui.calibrator"], cwd=parent_path)
            self.status_label.config(text="Calibrator started — map keys then Save")
        except Exception:
            self.status_label.config(text="Failed to start calibrator")

    def _reload_keymap(self):
        old = dict(self.keymap)
        self.keymap = self._load_keymap()
        if self.selected_key_id is not None:
            self.selected_cell = self.keymap.get(self.selected_key_id)
        if old != self.keymap:
            if self.keymap:
                self.status_label.config(text="Keymap reloaded")
            else:
                self.status_label.config(text="No keymap found — run keymap calibrator")
        self.canvas.redraw()

    def _commit(self, *, force: bool = False):
        now = time.monotonic()
        if not force and (now - self._last_commit_ts) < self._commit_interval:
            return
        self._last_commit_ts = now

        self._ensure_full_map()

        if self.config.brightness == 0:
            self.config.brightness = 25

        self.config.effect = "perkey"
        self.config.per_key_colors = self.colors

        if self.kb is not None:
            try:
                self.kb.set_key_colors(
                    self.colors,
                    brightness=self.config.brightness,
                    enable_user_mode=True,
                )
            except OSError as e:
                if getattr(e, "errno", None) == 16:
                    self.kb = None
            except Exception:
                pass

    def _on_color_change(self, r: int, g: int, b: int):
        if self.selected_cell is None:
            return

        row, col = self.selected_cell
        color = (r, g, b)
        self.colors[(row, col)] = color
        self.canvas.update_key_visual(self.selected_key_id, color)
        self._commit(force=False)

    def _on_color_release(self, r: int, g: int, b: int):
        if self.selected_cell is None:
            return

        row, col = self.selected_cell
        color = (r, g, b)
        self.colors[(row, col)] = color
        self.canvas.update_key_visual(self.selected_key_id, color)
        self._commit(force=True)
        if self.selected_key_id is not None:
            self.status_label.config(text=f"Saved {self.selected_key_id} = RGB({r},{g},{b})")
        else:
            self.status_label.config(text=f"Saved key {row},{col} = RGB({r},{g},{b})")

    def _fill_all(self):
        r, g, b = self.color_wheel.get_color()
        color = (r, g, b)

        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self.colors[(row, col)] = color

        self.canvas.redraw()
        self._commit(force=True)
        self.status_label.config(text=f"Filled all keys = RGB({r},{g},{b})")

    def _ensure_full_map(self):
        if len(self.colors) >= (NUM_ROWS * NUM_COLS):
            return

        base = tuple(self.config.color)
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self.colors.setdefault((row, col), base)

    def _clear_all(self):
        self.colors = {(row, col): (0, 0, 0) for row in range(NUM_ROWS) for col in range(NUM_COLS)}
        self.canvas.redraw()
        self.config.effect = "perkey"
        self.config.per_key_colors = self.colors

        if self.kb is not None:
            try:
                self.kb.set_key_colors(self.colors, brightness=self.config.brightness, enable_user_mode=True)
            except OSError as e:
                if getattr(e, "errno", None) == 16:
                    self.kb = None
            except Exception:
                pass

        self.status_label.config(text="Cleared all keys")

    def _load_layout_tweaks(self) -> dict[str, float]:
        return profiles.load_layout_global(self.profile_name)

    def _load_per_key_layout_tweaks(self) -> dict[str, dict[str, float]]:
        return profiles.load_layout_per_key(self.profile_name)

    def _toggle_profiles(self):
        if self._profiles_visible:
            self._profiles_frame.pack_forget()
            self._profiles_visible = False
        else:
            self._profiles_combo.configure(values=profiles.list_profiles())
            self._profiles_frame.pack(fill="x", pady=(6, 0))
            self._profiles_visible = True

    def _activate_profile(self):
        name = profiles.set_active_profile(self._profile_name_var.get())
        self.profile_name = name
        self._profile_name_var.set(name)

        self.keymap = self._load_keymap()
        self.layout_tweaks = self._load_layout_tweaks()
        self.per_key_layout_tweaks = self._load_per_key_layout_tweaks()

        prof_colors = profiles.load_per_key_colors(self.profile_name)
        self.colors = dict(prof_colors)
        profiles.apply_profile_to_config(self.config, self.colors)

        self.overlay_controls.sync_vars_from_scope()
        self.canvas.redraw()
        self.status_label.config(text=f"Active profile: {self.profile_name}")

    def _save_profile(self):
        name = profiles.set_active_profile(self._profile_name_var.get())
        self.profile_name = name
        self._profile_name_var.set(name)
        profiles.save_keymap(self.keymap, self.profile_name)
        profiles.save_layout_global(self.layout_tweaks, self.profile_name)
        profiles.save_layout_per_key(self.per_key_layout_tweaks, self.profile_name)
        profiles.save_per_key_colors(self.colors, self.profile_name)
        self.status_label.config(text=f"Saved profile: {self.profile_name}")

    def _delete_profile(self):
        name = self._profile_name_var.get().strip()
        if not name:
            return
        if not profiles.delete_profile(name):
            self.status_label.config(text="Cannot delete 'default'")
            return
        if profiles.get_active_profile() == profiles._safe_name(name):
            profiles.set_active_profile("default")
            self.profile_name = "default"
            self._profile_name_var.set("default")
        self._profiles_combo.configure(values=profiles.list_profiles())
        self.status_label.config(text=f"Deleted profile: {profiles._safe_name(name)}")

    def _load_keymap(self) -> dict[str, tuple[int, int]]:
        path = profiles.paths_for(self.profile_name).keymap
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        out: dict[str, tuple[int, int]] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(k, str) and isinstance(v, str) and "," in v:
                    a, b = v.split(",", 1)
                    try:
                        out[k] = (int(a), int(b))
                    except ValueError:
                        continue
                elif isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) == 2:
                    try:
                        out[k] = (int(v[0]), int(v[1]))
                    except Exception:
                        continue
        return out

    def run(self):
        self.root.mainloop()

def main():
    PerKeyEditor().run()

if __name__ == "__main__":
    main()
