#!/usr/bin/env python3
"""KeyRGB Per-Key Editor (Tkinter)"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog

from src.gui.widgets.color_wheel import ColorWheel
from src.legacy.config import Config
from src.core.layout import Y15_PRO_KEYS
from src.core import profiles
from src.gui.profile_backdrop_storage import reset_backdrop_image, save_backdrop_image
from src.gui.launch_keymap_calibrator import launch_keymap_calibrator
from src.gui.window_icon import apply_keyrgb_window_icon

from .canvas import KeyboardCanvas
from .overlay import OverlayControls
from .hardware import get_keyboard, NUM_ROWS, NUM_COLS
from .overlay_autosync import auto_sync_per_key_overlays
from .profile_management import activate_profile, delete_profile, save_profile
from .keyboard_apply import push_per_key_colors
from .editor_ui import build_editor_ui
from .color_map_ops import clear_all, ensure_full_map, fill_all
from .color_apply_ops import apply_color_to_map


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
        apply_keyrgb_window_icon(self.root)
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
        style.configure("TCheckbutton", background=self.bg_color, foreground=self.fg_color)

        self.config = Config()
        self.profile_name = profiles.get_active_profile()

        base_color = (
            tuple(self.config.color)
            if isinstance(self.config.color, (list, tuple)) and len(self.config.color) == 3
            else (255, 0, 0)
        )
        self._last_non_black_color: tuple[int, int, int] = (
            (int(base_color[0]), int(base_color[1]), int(base_color[2]))
            if base_color != (0, 0, 0)
            else (255, 0, 0)
        )

        # Prefer profile-stored per-key colors over whatever happens to be in
        # config.json (e.g., the calibrator probe state).
        prof_colors = profiles.load_per_key_colors(self.profile_name)
        if prof_colors:
            self.colors = dict(prof_colors)
        else:
            self.colors = dict(self.config.per_key_colors)

        self.keymap: dict[str, tuple[int, int]] = self._load_keymap()
        self.layout_tweaks = self._load_layout_tweaks()
        self.per_key_layout_tweaks: dict[str, dict[str, float]] = self._load_per_key_layout_tweaks()
        
        self.overlay_scope = tk.StringVar(value="global")  # global | key
        self.apply_all_keys = tk.BooleanVar(value=False)
        self._profiles_visible = False
        self._overlay_visible = False
        self._profile_name_var = tk.StringVar(value=self.profile_name)
        self.selected_key_id: str | None = None
        self.selected_cell: tuple[int, int] | None = None

        self._last_commit_ts = 0.0
        self._commit_interval = 0.06

        self.kb = None
        self.kb = get_keyboard()

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
        build_editor_ui(self)

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

        # If the key is currently "off" (black), start the wheel at a usable
        # brightness so users can immediately pick a color. This matches the
        # common flow of starting from a unified color and tweaking individual keys.
        if tuple(color) == (0, 0, 0):
            self.color_wheel.set_color(*self._last_non_black_color)
        else:
            self._last_non_black_color = (int(color[0]), int(color[1]), int(color[2]))
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

    def auto_sync_per_key_overlays(self):
        auto_sync_per_key_overlays(
            layout_tweaks=self.layout_tweaks,
            per_key_layout_tweaks=self.per_key_layout_tweaks,
        )

        # Refresh UI.
        if self._overlay_visible:
            self.overlay_controls.sync_vars_from_scope()
        self.canvas.redraw()
        self.status_label.config(text="Auto-synced overlay tweaks")

    def _run_calibrator(self):
        try:
            launch_keymap_calibrator()
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

        self.kb = push_per_key_colors(
            self.kb,
            self.colors,
            brightness=int(self.config.brightness),
            enable_user_mode=True,
        )

    def _on_color_change(self, r: int, g: int, b: int):
        color = (r, g, b)
        if color != (0, 0, 0):
            self._last_non_black_color = color

        if (not self.apply_all_keys.get()) and (self.selected_cell is None or not self.selected_key_id):
            return

        self.colors = apply_color_to_map(
            colors=dict(self.colors),
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
            color=color,
            apply_all_keys=bool(self.apply_all_keys.get()),
            selected_cell=self.selected_cell,
        )

        if self.apply_all_keys.get():
            self.canvas.redraw()
        else:
            self.canvas.update_key_visual(self.selected_key_id, color)
        self._commit(force=False)

    def _on_color_release(self, r: int, g: int, b: int):
        color = (r, g, b)
        if color != (0, 0, 0):
            self._last_non_black_color = color

        if (not self.apply_all_keys.get()) and (self.selected_cell is None or not self.selected_key_id):
            return

        self.colors = apply_color_to_map(
            colors=dict(self.colors),
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
            color=color,
            apply_all_keys=bool(self.apply_all_keys.get()),
            selected_cell=self.selected_cell,
        )

        if self.apply_all_keys.get():
            self.canvas.redraw()
        else:
            self.canvas.update_key_visual(self.selected_key_id, color)
        self._commit(force=True)
        if self.apply_all_keys.get():
            self.status_label.config(text=f"Saved all keys = RGB({r},{g},{b})")
        elif self.selected_key_id is not None and self.selected_cell is not None:
            self.status_label.config(text=f"Saved {self.selected_key_id} = RGB({r},{g},{b})")

    def _set_backdrop(self):
        path = filedialog.askopenfilename(
            title="Select keyboard backdrop image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            save_backdrop_image(profile_name=self.profile_name, source_path=path)
            self.canvas._load_deck_image()
            self.canvas.redraw()
            self.status_label.config(text="Backdrop updated")
        except Exception:
            self.status_label.config(text="Failed to set backdrop")

    def _reset_backdrop(self):
        try:
            reset_backdrop_image(self.profile_name)
            self.canvas._load_deck_image()
            self.canvas.redraw()
            self.status_label.config(text="Backdrop reset")
        except Exception:
            self.status_label.config(text="Failed to reset backdrop")

    def _fill_all(self):
        r, g, b = self.color_wheel.get_color()
        color = (r, g, b)

        self.colors = fill_all(num_rows=NUM_ROWS, num_cols=NUM_COLS, color=color)

        self.canvas.redraw()
        self._commit(force=True)
        self.status_label.config(text=f"Filled all keys = RGB({r},{g},{b})")

    def _ensure_full_map(self):
        # Use the last non-black wheel color as the base fill. This matches the
        # expected workflow: start from a unified color, then override a few keys
        # without blanking the rest of the keyboard.
        base = tuple(getattr(self, "_last_non_black_color", tuple(self.config.color)))
        fallback = tuple(self.config.color)
        self.colors = ensure_full_map(
            colors=dict(self.colors),
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
            base_color=base,
            fallback_color=fallback,
        )

    def _clear_all(self):
        self.colors = clear_all(num_rows=NUM_ROWS, num_cols=NUM_COLS)
        self.canvas.redraw()
        self.config.effect = "perkey"
        self.config.per_key_colors = self.colors

        self.kb = push_per_key_colors(
            self.kb,
            self.colors,
            brightness=int(self.config.brightness),
            enable_user_mode=True,
        )

        self.status_label.config(text="Cleared all keys")

    def _load_layout_tweaks(self) -> dict[str, float]:
        return profiles.load_layout_global(self.profile_name)

    def _load_per_key_layout_tweaks(self) -> dict[str, dict[str, float]]:
        return profiles.load_layout_per_key(self.profile_name)

    def _toggle_profiles(self):
        if self._profiles_visible:
            self._profiles_frame.grid_remove()
            self._profiles_visible = False
        else:
            self._profiles_combo.configure(values=profiles.list_profiles())
            self._profiles_frame.grid()
            self._profiles_visible = True

    def _toggle_overlay(self):
        if self._overlay_visible:
            self.overlay_controls.grid_remove()
            self._overlay_visible = False
        else:
            self.overlay_controls.grid()
            self._overlay_visible = True
            self.overlay_controls.sync_vars_from_scope()

    def _activate_profile(self):
        result = activate_profile(
            self._profile_name_var.get(),
            config=self.config,
            current_colors=dict(getattr(self, "colors", {}) or {}),
        )
        self.profile_name = result.name
        self._profile_name_var.set(result.name)

        self.keymap = result.keymap
        self.layout_tweaks = result.layout_tweaks
        self.per_key_layout_tweaks = result.per_key_layout_tweaks
        self.colors = result.colors

        # Ensure we're applying a full map, then push it to hardware.
        self._ensure_full_map()
        self._commit(force=True)

        self.overlay_controls.sync_vars_from_scope()
        self.canvas.redraw()
        self.status_label.config(text=f"Active profile: {self.profile_name}")

        if self.selected_key_id:
            self.select_key_id(self.selected_key_id)

    def _save_profile(self):
        name = save_profile(
            self._profile_name_var.get(),
            config=self.config,
            keymap=self.keymap,
            layout_tweaks=self.layout_tweaks,
            per_key_layout_tweaks=self.per_key_layout_tweaks,
            colors=self.colors,
        )
        self.profile_name = name
        self._profile_name_var.set(name)

        # Persist + push the saved state immediately.
        self._ensure_full_map()
        self._commit(force=True)
        self.status_label.config(text=f"Saved profile: {self.profile_name}")

    def _delete_profile(self):
        result = delete_profile(self._profile_name_var.get())
        if not result.deleted:
            if result.message:
                self.status_label.config(text=result.message)
            return

        self.profile_name = result.active_profile
        self._profile_name_var.set(result.active_profile)
        self._profiles_combo.configure(values=profiles.list_profiles())
        self.status_label.config(text=result.message)

    def _load_keymap(self) -> dict[str, tuple[int, int]]:
        return profiles.load_keymap(self.profile_name)

    def run(self):
        self.root.mainloop()

def main():
    PerKeyEditor().run()

if __name__ == "__main__":
    main()
