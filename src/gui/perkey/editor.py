#!/usr/bin/env python3
"""KeyRGB Per-Key Editor (Tkinter)"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog

from src.gui.widgets.color_wheel import ColorWheel
from src.legacy.config import Config
from src.core.layout import Y15_PRO_KEYS
from src.core import profiles
from src.gui.profile_backdrop_storage import reset_backdrop_image, save_backdrop_image
from src.gui.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_dark_theme

from .canvas import KeyboardCanvas
from .overlay import OverlayControls
from .hardware import get_keyboard, NUM_ROWS, NUM_COLS
from .overlay_autosync import auto_sync_per_key_overlays
from .profile_management import load_profile_colors
from .keyboard_apply import push_per_key_colors
from .editor_ui import build_editor_ui
from .color_map_ops import clear_all, ensure_full_map, fill_all
from .color_apply_ops import apply_color_to_map
from .window_geometry import apply_perkey_editor_geometry
from .commit_pipeline import PerKeyCommitPipeline
from .profile_actions_ui import activate_profile_ui, delete_profile_ui, save_profile_ui
from .calibrator_ui import run_keymap_calibrator_ui
from .keymap_ui import reload_keymap_ui
from .status_ui import (
    active_profile,
    auto_synced_overlay_tweaks,
    backdrop_reset,
    backdrop_reset_failed,
    backdrop_update_failed,
    backdrop_updated,
    calibrator_failed,
    calibrator_started,
    cleared_all_keys,
    filled_all_keys_rgb,
    no_keymap_found_initial,
    reset_overlay_tweaks_for_key,
    reset_overlay_tweaks_global,
    saved_all_keys_rgb,
    saved_key_rgb,
    saved_overlay_tweaks_for_key,
    saved_overlay_tweaks_global,
    selected_mapped,
    selected_unmapped,
    set_status,
)


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

        apply_perkey_editor_geometry(
            self.root,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
            key_margin=self._key_margin,
            key_size=self._key_size,
            key_gap=self._key_gap,
            right_panel_width=self._right_panel_width,
            wheel_size=self._wheel_size,
        )

        style = ttk.Style()
        self.bg_color, self.fg_color = apply_clam_dark_theme(self.root)
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
        self.colors = load_profile_colors(name=self.profile_name, config=self.config, current_colors={})

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

        self._commit_pipeline = PerKeyCommitPipeline(commit_interval_s=0.06)

        self.kb = None
        self.kb = get_keyboard()

        self._build_ui()
        self.canvas.redraw()

        if not self.keymap:
            set_status(self, no_keymap_found_initial())

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
            set_status(self, selected_unmapped(key_id))
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
        set_status(self, selected_mapped(key_id, row, col))
        self.canvas.redraw()

    def sync_overlay_vars(self):
        self.overlay_controls.sync_vars_from_scope()

    def save_layout_tweaks(self):
        if self.overlay_scope.get() == "key" and self.selected_key_id:
            profiles.save_layout_per_key(self.per_key_layout_tweaks, self.profile_name)
            set_status(self, saved_overlay_tweaks_for_key(self.selected_key_id))
        else:
            profiles.save_layout_global(self.layout_tweaks, self.profile_name)
            set_status(self, saved_overlay_tweaks_global())

    def reset_layout_tweaks(self):
        if self.overlay_scope.get() == "key" and self.selected_key_id:
            self.per_key_layout_tweaks.pop(self.selected_key_id, None)
            self.overlay_controls.sync_vars_from_scope()
            self.canvas.redraw()
            set_status(self, reset_overlay_tweaks_for_key(self.selected_key_id))
            return

        self.layout_tweaks = {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
        self.overlay_controls.sync_vars_from_scope()
        self.canvas.redraw()
        set_status(self, reset_overlay_tweaks_global())

    def auto_sync_per_key_overlays(self):
        auto_sync_per_key_overlays(
            layout_tweaks=self.layout_tweaks,
            per_key_layout_tweaks=self.per_key_layout_tweaks,
        )

        # Refresh UI.
        if self._overlay_visible:
            self.overlay_controls.sync_vars_from_scope()
        self.canvas.redraw()
        set_status(self, auto_synced_overlay_tweaks())

    def _run_calibrator(self):
        run_keymap_calibrator_ui(self)

    def _reload_keymap(self):
        reload_keymap_ui(self)

    def _commit(self, *, force: bool = False):
        base = tuple(getattr(self, "_last_non_black_color", tuple(self.config.color)))
        fallback = tuple(self.config.color)
        self.kb, self.colors = self._commit_pipeline.commit(
            kb=self.kb,
            colors=dict(self.colors),
            config=self.config,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
            base_color=(int(base[0]), int(base[1]), int(base[2])),
            fallback_color=(int(fallback[0]), int(fallback[1]), int(fallback[2])),
            push_fn=push_per_key_colors,
            force=bool(force),
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
            set_status(self, saved_all_keys_rgb(r, g, b))
        elif self.selected_key_id is not None and self.selected_cell is not None:
            set_status(self, saved_key_rgb(self.selected_key_id, r, g, b))

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
            self.canvas.reload_backdrop_image()
            set_status(self, backdrop_updated())
        except Exception:
            set_status(self, backdrop_update_failed())

    def _reset_backdrop(self):
        try:
            reset_backdrop_image(self.profile_name)
            self.canvas.reload_backdrop_image()
            set_status(self, backdrop_reset())
        except Exception:
            set_status(self, backdrop_reset_failed())

    def _fill_all(self):
        r, g, b = self.color_wheel.get_color()
        color = (r, g, b)

        self.colors = fill_all(num_rows=NUM_ROWS, num_cols=NUM_COLS, color=color)

        self.canvas.redraw()
        self._commit(force=True)
        set_status(self, filled_all_keys_rgb(r, g, b))

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

        set_status(self, cleared_all_keys())

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
        activate_profile_ui(self)

    def _save_profile(self):
        save_profile_ui(self)

    def _delete_profile(self):
        delete_profile_ui(self)

    def _load_keymap(self) -> dict[str, tuple[int, int]]:
        return profiles.load_keymap(self.profile_name)

    def run(self):
        self.root.mainloop()

def main():
    PerKeyEditor().run()

if __name__ == "__main__":
    main()
