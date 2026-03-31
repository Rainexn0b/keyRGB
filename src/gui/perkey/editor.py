#!/usr/bin/env python3
"""KeyRGB Per-Key Editor (Tkinter)"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.core.config import Config
from src.core.resources.defaults import get_default_layout_tweaks
from src.core.resources.layout_slots import get_layout_slot_states
from src.core.resources.layout import get_layout_keys
from src.core.profile import profiles
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_theme

from .ui.backdrop import reset_backdrop_ui, set_backdrop_ui

from .hardware import get_keyboard, NUM_ROWS, NUM_COLS
from .overlay import auto_sync_per_key_overlays
from .profile_management import load_profile_colors, sanitize_keymap_cells
from .keyboard_apply import push_per_key_colors
from .editor_ui import build_editor_ui
from .window_geometry import apply_perkey_editor_geometry
from .commit_pipeline import PerKeyCommitPipeline
from .color_utils import initial_last_non_black_color, rgb_ints

from .ui.profile_actions import (
    activate_profile_ui,
    delete_profile_ui,
    new_profile_ui,
    reset_layout_defaults_ui,
    save_profile_ui,
    set_default_profile_ui,
)
from .ui.calibrator import run_keymap_calibrator_ui
from .ui.keymap import reload_keymap_ui
from .ui.bulk_color import clear_all_ui, fill_all_ui
from .ui.wheel_apply import on_wheel_color_change_ui, on_wheel_color_release_ui
from .ui.full_map import ensure_full_map_ui
from .ui.sample_tool import on_key_clicked_ui, on_sample_tool_toggled_ui
from .ui.status import (
    auto_synced_overlay_tweaks,
    layout_slot_label_updated,
    layout_slot_visibility_updated,
    no_keymap_found_initial,
    reset_overlay_tweaks_for_key,
    reset_overlay_tweaks_global,
    saved_overlay_tweaks_for_key,
    saved_overlay_tweaks_global,
    selected_mapped,
    selected_unmapped,
    set_status,
    hardware_write_paused,
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
        self.root.title("KeyRGB - Per-key Colors")
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
        self.bg_color, self.fg_color = apply_clam_theme(self.root)
        style.configure("TCheckbutton", background=self.bg_color, foreground=self.fg_color)
        style.configure("TLabelframe", background=self.bg_color, foreground=self.fg_color)
        style.configure("TLabelframe.Label", background=self.bg_color, foreground=self.fg_color)
        style.configure("TRadiobutton", background=self.bg_color, foreground=self.fg_color)

        # Keep input widgets readable. Colors come from the active theme,
        # so this works for both dark and light system preferences.
        field_bg = style.lookup("TEntry", "fieldbackground") or "#3a3a3a"
        style.configure("TEntry", fieldbackground=field_bg, foreground=self.fg_color)
        style.configure("TCombobox", fieldbackground=field_bg, foreground=self.fg_color)
        try:
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", field_bg), ("disabled", field_bg)],
                foreground=[("readonly", self.fg_color), ("disabled", self.fg_color)],
            )
        except Exception:
            pass

        self.config = Config()
        self.profile_name = profiles.get_active_profile()
        self._physical_layout: str = self.config.physical_layout

        # Tk variable so the layout dropdown in editor_ui can bind to it.
        # Stores the layout_id (e.g. "auto", "ansi", "iso").
        self._layout_var = tk.StringVar(value=self._physical_layout)

        self.backdrop_transparency = tk.DoubleVar(value=float(profiles.load_backdrop_transparency(self.profile_name)))
        self._backdrop_transparency_save_job: str | None = None
        self._backdrop_transparency_redraw_job: str | None = None

        self._last_non_black_color = initial_last_non_black_color(self.config.color)

        # Prefer profile-stored per-key colors over whatever happens to be in
        # config.json (e.g., the calibrator probe state).
        self.colors = load_profile_colors(
            name=self.profile_name,
            config=self.config,
            current_colors={},
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )

        self.keymap: dict[str, tuple[int, int]] = self._load_keymap()
        self.layout_tweaks = self._load_layout_tweaks()
        self.per_key_layout_tweaks: dict[str, dict[str, float]] = self._load_per_key_layout_tweaks()
        self.layout_slot_overrides: dict[str, dict[str, object]] = self._load_layout_slot_overrides()

        self.overlay_scope = tk.StringVar(value="global")  # global | key
        self.apply_all_keys = tk.BooleanVar(value=False)
        self.sample_tool_enabled = tk.BooleanVar(value=False)
        self._sample_tool_has_sampled = False
        self._setup_panel_mode: str | None = None
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

        visible_keys = self._get_visible_layout_keys()
        for kd in visible_keys:
            if kd.key_id in self.keymap:
                self.select_key_id(kd.key_id)
                break

    def _on_backdrop_transparency_changed(self, value: str) -> None:
        try:
            t = int(round(float(value)))
        except Exception:
            t = 0
        t = max(0, min(100, t))

        try:
            self.backdrop_transparency.set(float(t))
        except Exception:
            pass

        # Throttle redraw while dragging.
        if self._backdrop_transparency_redraw_job is not None:
            try:
                self.root.after_cancel(self._backdrop_transparency_redraw_job)
            except Exception:
                pass
        self._backdrop_transparency_redraw_job = self.root.after(30, self._apply_backdrop_transparency_redraw)

        # Throttle disk writes while dragging.
        if self._backdrop_transparency_save_job is not None:
            try:
                self.root.after_cancel(self._backdrop_transparency_save_job)
            except Exception:
                pass
        self._backdrop_transparency_save_job = self.root.after(250, self._persist_backdrop_transparency)

    def _apply_backdrop_transparency_redraw(self) -> None:
        self._backdrop_transparency_redraw_job = None
        try:
            self.canvas.redraw()
        except Exception:
            return

    def _persist_backdrop_transparency(self) -> None:
        self._backdrop_transparency_save_job = None
        try:
            profiles.save_backdrop_transparency(int(round(float(self.backdrop_transparency.get()))), self.profile_name)
        except Exception:
            return

    def _build_ui(self):
        build_editor_ui(self)

    def _get_visible_layout_keys(self):
        return get_layout_keys(self._physical_layout, slot_overrides=self.layout_slot_overrides)

    def _refresh_layout_slot_controls(self) -> None:
        from .ui.layout_slots import refresh_layout_slots_ui

        refresh_layout_slots_ui(self)

    def _sync_visible_layout_state(self) -> None:
        visible_keys = self._get_visible_layout_keys()
        visible_key_ids = {key.key_id for key in visible_keys}
        if self.selected_key_id not in visible_key_ids:
            self.selected_key_id = None
            self.selected_cell = None
            for key in visible_keys:
                if key.key_id in self.keymap:
                    self.select_key_id(key.key_id)
                    break

    def _load_layout_slot_overrides(self) -> dict[str, dict[str, object]]:
        return profiles.load_layout_slots(self.profile_name, physical_layout=self._physical_layout)

    def _persist_layout_slot_overrides(self) -> None:
        self.layout_slot_overrides = profiles.save_layout_slots(
            dict(self.layout_slot_overrides),
            self.profile_name,
            physical_layout=self._physical_layout,
        )

    def _set_layout_slot_visibility(self, key_id: str, visible: bool) -> None:
        override = dict(self.layout_slot_overrides.get(key_id, {}))
        if bool(visible):
            override.pop("visible", None)
        else:
            override["visible"] = False

        if override:
            self.layout_slot_overrides[key_id] = override
        else:
            self.layout_slot_overrides.pop(key_id, None)

        self._persist_layout_slot_overrides()
        self._refresh_layout_slot_controls()
        self._sync_visible_layout_state()
        self.canvas.redraw()
        set_status(self, layout_slot_visibility_updated(key_id, visible))

    def _set_layout_slot_label(self, key_id: str, label: str) -> None:
        default_labels = {state.key_id: state.default_label for state in get_layout_slot_states(self._physical_layout)}
        normalized_label = str(label).strip()
        override = dict(self.layout_slot_overrides.get(key_id, {}))
        default_label = default_labels.get(key_id, key_id)

        if normalized_label and normalized_label != default_label:
            override["label"] = normalized_label
        else:
            override.pop("label", None)

        if override:
            self.layout_slot_overrides[key_id] = override
        else:
            self.layout_slot_overrides.pop(key_id, None)

        self._persist_layout_slot_overrides()
        self._refresh_layout_slot_controls()
        self.canvas.redraw()
        set_status(self, layout_slot_label_updated(key_id, normalized_label or default_label))

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

    def _on_sample_tool_toggled(self) -> None:
        on_sample_tool_toggled_ui(self)

    def on_key_clicked(self, key_id: str) -> None:
        on_key_clicked_ui(self, key_id, num_rows=NUM_ROWS, num_cols=NUM_COLS)

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

        self.layout_tweaks = get_default_layout_tweaks(self._physical_layout)
        self.overlay_controls.sync_vars_from_scope()
        self.canvas.redraw()
        set_status(self, reset_overlay_tweaks_global())

    def auto_sync_per_key_overlays(self):
        auto_sync_per_key_overlays(
            layout_tweaks=self.layout_tweaks,
            per_key_layout_tweaks=self.per_key_layout_tweaks,
            keys=self._get_visible_layout_keys(),
        )

        # Refresh UI.
        if self._setup_panel_mode == "overlay":
            self.overlay_controls.sync_vars_from_scope()
        self.canvas.redraw()
        set_status(self, auto_synced_overlay_tweaks())

    def _run_calibrator(self):
        run_keymap_calibrator_ui(self)

    def _reload_keymap(self):
        reload_keymap_ui(self)

    def _commit(self, *, force: bool = False):
        prev_kb = self.kb
        base = tuple(getattr(self, "_last_non_black_color", tuple(self.config.color)))
        fallback = tuple(self.config.color)
        self.kb, self.colors = self._commit_pipeline.commit(
            kb=self.kb,
            colors=dict(self.colors),
            config=self.config,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
            base_color=rgb_ints(base),
            fallback_color=rgb_ints(fallback),
            push_fn=push_per_key_colors,
            force=bool(force),
        )

        # If hardware writes get paused (e.g., device busy), tell the user what to do next.
        if prev_kb is not None and self.kb is None:
            set_status(self, hardware_write_paused())

    def _on_color_change(self, r: int, g: int, b: int):
        on_wheel_color_change_ui(self, r, g, b, num_rows=NUM_ROWS, num_cols=NUM_COLS)

    def _on_color_release(self, r: int, g: int, b: int):
        on_wheel_color_release_ui(self, r, g, b, num_rows=NUM_ROWS, num_cols=NUM_COLS)

    def _set_backdrop(self):
        set_backdrop_ui(self)

    def _reset_backdrop(self):
        reset_backdrop_ui(self)

    def _fill_all(self):
        fill_all_ui(self, num_rows=NUM_ROWS, num_cols=NUM_COLS)

    def _ensure_full_map(self):
        ensure_full_map_ui(self, num_rows=NUM_ROWS, num_cols=NUM_COLS)

    def _clear_all(self):
        clear_all_ui(self, num_rows=NUM_ROWS, num_cols=NUM_COLS)

    def _load_layout_tweaks(self) -> dict[str, float]:
        return profiles.load_layout_global(self.profile_name, physical_layout=self._physical_layout)

    def _load_per_key_layout_tweaks(self) -> dict[str, dict[str, float]]:
        return profiles.load_layout_per_key(self.profile_name, physical_layout=self._physical_layout)

    def _on_layout_changed(self) -> None:
        """Handle layout dropdown change — update overlay and persist to config."""
        layout_id = self._layout_var.get()
        self._physical_layout = layout_id
        self.config.physical_layout = layout_id

        profile_paths = profiles.paths_for(self.profile_name)
        if not profile_paths.keymap.exists():
            self.keymap = self._load_keymap()
        if not profile_paths.layout_global.exists():
            self.layout_tweaks = self._load_layout_tweaks()
        if not profile_paths.layout_per_key.exists():
            self.per_key_layout_tweaks = self._load_per_key_layout_tweaks()

        self.layout_slot_overrides = self._load_layout_slot_overrides()

        if self._setup_panel_mode == "overlay":
            self.overlay_controls.sync_vars_from_scope()

        self._refresh_layout_slot_controls()
        self._sync_visible_layout_state()

        self.canvas.redraw()

    def _hide_setup_panel(self) -> None:
        self.overlay_controls.grid_remove()
        self._layout_setup_controls.grid_remove()
        self._setup_panel_mode = None

    def _show_setup_panel(self, mode: str) -> None:
        self._hide_setup_panel()
        if mode == "overlay":
            self.overlay_controls.grid()
            self.overlay_controls.sync_vars_from_scope()
        elif mode == "layout":
            self._layout_setup_controls.grid()
            self._refresh_layout_slot_controls()
        self._setup_panel_mode = mode

    def _toggle_overlay(self):
        if self._setup_panel_mode == "overlay":
            self._hide_setup_panel()
        else:
            self._show_setup_panel("overlay")

    def _toggle_layout_setup(self):
        if self._setup_panel_mode == "layout":
            self._hide_setup_panel()
        else:
            self._show_setup_panel("layout")

    def _new_profile(self):
        new_profile_ui(self)

    def _activate_profile(self):
        activate_profile_ui(self)

    def _save_profile(self):
        save_profile_ui(self)

    def _delete_profile(self):
        delete_profile_ui(self)

    def _set_default_profile(self):
        set_default_profile_ui(self)

    def _reset_layout_defaults(self):
        reset_layout_defaults_ui(self)

    def _load_keymap(self) -> dict[str, tuple[int, int]]:
        return sanitize_keymap_cells(
            profiles.load_keymap(self.profile_name, physical_layout=self._physical_layout),
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )

    def run(self):
        self.root.mainloop()


def main():
    PerKeyEditor().run()


if __name__ == "__main__":
    main()
