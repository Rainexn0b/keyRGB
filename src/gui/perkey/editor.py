#!/usr/bin/env python3
"""KeyRGB Per-Key Editor (Tkinter)"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from src.core.config import Config
from src.core.diagnostics.device_discovery import collect_device_discovery
from src.core.utils.logging_utils import log_throttled
from src.core.resources.defaults import get_default_layout_tweaks
from src.core.resources.layout_legends import load_layout_legend_pack, resolve_layout_legend_pack_id
from src.core.resources.layout_slots import get_layout_slot_states
from src.core.resources.layout import KeyDef, get_layout_keys
from src.core.profile import profiles
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_theme

from .ui.backdrop import reset_backdrop_ui, set_backdrop_ui

from .hardware import get_keyboard, NUM_ROWS, NUM_COLS
from .overlay import auto_sync_per_key_overlays
from .profile_management import keymap_cells_for, load_profile_colors, representative_cell, sanitize_keymap_cells
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
from .ui.sample_tool import on_sample_tool_toggled_ui, on_slot_clicked_ui
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


logger = logging.getLogger(__name__)

_TK_CALL_ERRORS = (RuntimeError, tk.TclError)
_VALUE_COERCION_ERRORS = (TypeError, ValueError)


def _log_boundary_exception(key: str, msg: str, exc: Exception) -> None:
    log_throttled(logger, key, interval_s=60, level=logging.DEBUG, msg=msg, exc=exc)


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
        except _TK_CALL_ERRORS as exc:
            _log_boundary_exception(
                "perkey.editor.style_map",
                "Failed to apply perkey combobox style map",
                exc,
            )

        self.config = Config()
        self.profile_name = profiles.get_active_profile()
        self._physical_layout: str = self.config.physical_layout
        self._layout_legend_pack: str = self._normalize_layout_legend_pack(
            self._physical_layout,
            self.config.layout_legend_pack,
        )
        self.has_lightbar_device = self._detect_lightbar_device()
        self.lightbar_overlay = profiles.load_lightbar_overlay(self.profile_name)

        # Tk variable so the layout dropdown in editor_ui can bind to it.
        # Stores the layout_id (e.g. "auto", "ansi", "iso").
        self._layout_var = tk.StringVar(value=self._physical_layout)
        self._legend_pack_var = tk.StringVar(value=self._layout_legend_pack)

        self._backdrop_mode_var = tk.StringVar(value=profiles.load_backdrop_mode(self.profile_name))
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

        self.keymap: dict[str, tuple[tuple[int, int], ...]] = self._load_keymap()
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
        self.selected_slot_id: str | None = None
        self.selected_cells: tuple[tuple[int, int], ...] = ()
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
                self.select_slot_id(str(kd.slot_id or kd.key_id))
                break

    def _on_backdrop_transparency_changed(self, value: str) -> None:
        try:
            t = int(round(float(value)))
        except _VALUE_COERCION_ERRORS:
            t = 0
        t = max(0, min(100, t))

        try:
            self.backdrop_transparency.set(float(t))
        except _TK_CALL_ERRORS as exc:
            _log_boundary_exception(
                "perkey.editor.backdrop_transparency_var",
                "Failed to update perkey backdrop transparency variable",
                exc,
            )

        # Throttle redraw while dragging.
        if self._backdrop_transparency_redraw_job is not None:
            try:
                self.root.after_cancel(self._backdrop_transparency_redraw_job)
            except _TK_CALL_ERRORS as exc:
                _log_boundary_exception(
                    "perkey.editor.backdrop_transparency_redraw_cancel",
                    "Failed to cancel pending perkey backdrop redraw",
                    exc,
                )
        self._backdrop_transparency_redraw_job = self.root.after(30, self._apply_backdrop_transparency_redraw)

        # Throttle disk writes while dragging.
        if self._backdrop_transparency_save_job is not None:
            try:
                self.root.after_cancel(self._backdrop_transparency_save_job)
            except _TK_CALL_ERRORS as exc:
                _log_boundary_exception(
                    "perkey.editor.backdrop_transparency_save_cancel",
                    "Failed to cancel pending perkey backdrop transparency save",
                    exc,
                )
        self._backdrop_transparency_save_job = self.root.after(250, self._persist_backdrop_transparency)

    def _apply_backdrop_transparency_redraw(self) -> None:
        self._backdrop_transparency_redraw_job = None
        try:
            self.canvas.redraw()
        except Exception as exc:
            _log_boundary_exception(
                "perkey.editor.backdrop_transparency_redraw",
                "Failed to redraw perkey backdrop transparency change",
                exc,
            )
            return

    def _persist_backdrop_transparency(self) -> None:
        self._backdrop_transparency_save_job = None
        try:
            transparency = int(round(float(self.backdrop_transparency.get())))
        except _VALUE_COERCION_ERRORS + _TK_CALL_ERRORS:
            return

        try:
            profiles.save_backdrop_transparency(transparency, self.profile_name)
        except Exception as exc:
            _log_boundary_exception(
                "perkey.editor.backdrop_transparency_save",
                "Failed to persist perkey backdrop transparency",
                exc,
            )
            return

    def _on_backdrop_mode_changed(self, _event=None) -> None:
        mode = profiles.normalize_backdrop_mode(self._backdrop_mode_var.get())
        try:
            self._backdrop_mode_var.set(mode)
        except _TK_CALL_ERRORS as exc:
            _log_boundary_exception(
                "perkey.editor.backdrop_mode_var",
                "Failed to update perkey backdrop mode variable",
                exc,
            )

        try:
            profiles.save_backdrop_mode(mode, self.profile_name)
        except Exception as exc:
            _log_boundary_exception(
                "perkey.editor.backdrop_mode_save",
                "Failed to persist perkey backdrop mode",
                exc,
            )
            return

        try:
            self.canvas.reload_backdrop_image()
        except Exception as exc:
            _log_boundary_exception(
                "perkey.editor.backdrop_mode_reload",
                "Failed to reload perkey backdrop after mode change",
                exc,
            )
            return

    def _build_ui(self):
        build_editor_ui(self)

    def _normalize_layout_legend_pack(self, layout_id: str, legend_pack_id: str | None) -> str:
        requested = str(legend_pack_id or "auto").strip().lower()
        if not requested or requested == "auto":
            return "auto"

        pack = load_layout_legend_pack(requested)
        if not pack:
            return "auto"

        resolved_pack_layout = str(pack.get("layout_id") or layout_id).strip().lower()
        return requested if resolved_pack_layout == str(layout_id or "auto").strip().lower() else "auto"

    def _resolved_layout_legend_pack_id(self) -> str:
        selected = self._normalize_layout_legend_pack(self._physical_layout, self._layout_legend_pack)
        return resolve_layout_legend_pack_id(
            self._physical_layout,
            None if selected == "auto" else selected,
        )

    def _sync_layout_legend_pack_ui(self) -> None:
        try:
            self._legend_pack_var.set(self._layout_legend_pack)
        except _TK_CALL_ERRORS as exc:
            _log_boundary_exception(
                "perkey.editor.legend_pack_var",
                "Failed to update perkey legend pack variable",
                exc,
            )

        controls = getattr(self, "_layout_setup_controls", None)
        refresh_choices = getattr(controls, "refresh_legend_pack_choices", None)
        if callable(refresh_choices):
            refresh_choices()

    def _get_visible_layout_keys(self):
        return get_layout_keys(
            self._physical_layout,
            legend_pack_id=self._resolved_layout_legend_pack_id(),
            slot_overrides=self.layout_slot_overrides,
        )

    def _visible_key_maps(self) -> tuple[dict[str, KeyDef], dict[str, KeyDef]]:
        visible_keys = self._get_visible_layout_keys()
        by_key_id = {str(key.key_id): key for key in visible_keys}
        by_slot_id = {str(key.slot_id): key for key in visible_keys if key.slot_id}
        return by_key_id, by_slot_id

    def _visible_key_for_key_id(self, key_id: str | None) -> KeyDef | None:
        if not key_id:
            return None
        by_key_id, _by_slot_id = self._visible_key_maps()
        return by_key_id.get(str(key_id))

    def _visible_key_for_slot_id(self, slot_id: str | None) -> KeyDef | None:
        if not slot_id:
            return None
        _by_key_id, by_slot_id = self._visible_key_maps()
        return by_slot_id.get(str(slot_id))

    def _slot_id_for_key_id(self, key_id: str | None) -> str | None:
        key = self._visible_key_for_key_id(key_id)
        if key is None or not key.slot_id:
            return None
        return str(key.slot_id)

    def _key_id_for_slot_id(self, slot_id: str | None) -> str | None:
        key = self._visible_key_for_slot_id(slot_id)
        if key is None:
            return None
        return str(key.key_id)

    def _clear_selection(self) -> None:
        self.selected_key_id = None
        self.selected_slot_id = None
        self.selected_cells = ()
        self.selected_cell = None

    def _apply_selection_for_visible_key(self, key: KeyDef) -> None:
        self.selected_key_id = str(key.key_id)
        self.selected_slot_id = str(key.slot_id or key.key_id)
        self.selected_cells = keymap_cells_for(
            self.keymap,
            self.selected_key_id,
            slot_id=self.selected_slot_id,
            physical_layout=self._physical_layout,
        )
        self.selected_cell = representative_cell(self.selected_cells, colors=self.colors)

    def _selected_display_key_id(self) -> str | None:
        if self.selected_key_id:
            return str(self.selected_key_id)
        if self.selected_slot_id:
            return self._key_id_for_slot_id(self.selected_slot_id)
        return None

    def _refresh_selected_cells(self) -> None:
        self.selected_cells = keymap_cells_for(
            self.keymap,
            self._selected_display_key_id(),
            slot_id=self.selected_slot_id,
            physical_layout=self._physical_layout,
        )
        self.selected_cell = representative_cell(self.selected_cells, colors=self.colors)

    def _finalize_selection(self, requested_identity: str) -> None:
        display_key_id = self._selected_display_key_id() or str(requested_identity)

        if self.overlay_scope.get() == "key":
            self.overlay_controls.sync_vars_from_scope()

        if not self.selected_cells:
            set_status(self, selected_unmapped(display_key_id))
            self.canvas.redraw()
            return

        row, col = self.selected_cells[0]
        display_cell = representative_cell(self.selected_cells, colors=self.colors)
        color = self.colors.get(display_cell, (0, 0, 0)) if display_cell is not None else (0, 0, 0)

        if tuple(color) == (0, 0, 0):
            self.color_wheel.set_color(*self._last_non_black_color)
        else:
            self._last_non_black_color = (int(color[0]), int(color[1]), int(color[2]))
            self.color_wheel.set_color(*color)

        set_status(self, selected_mapped(display_key_id, row, col, len(self.selected_cells)))
        self.canvas.redraw()

    def _refresh_layout_slot_controls(self) -> None:
        from .ui.layout_slots import refresh_layout_slots_ui

        refresh_layout_slots_ui(self)

    def _get_layout_slot_states(self):
        return get_layout_slot_states(
            self._physical_layout,
            self.layout_slot_overrides,
            legend_pack_id=self._resolved_layout_legend_pack_id(),
        )

    def _selected_overlay_identity(self) -> str | None:
        return self.selected_slot_id or self.selected_key_id

    def _layout_slot_state_for_identity(self, identity: str | None):
        if not identity:
            return None
        for state in self._get_layout_slot_states():
            if identity in {state.slot_id, state.key_id}:
                return state
        return None

    def _sync_visible_layout_state(self) -> None:
        visible_keys = self._get_visible_layout_keys()
        visible_slot_ids = {str(key.slot_id or key.key_id) for key in visible_keys}
        current_slot_id = (
            self.selected_slot_id or self._slot_id_for_key_id(self.selected_key_id) or self.selected_key_id
        )
        if current_slot_id not in visible_slot_ids:
            self._clear_selection()
            for key in visible_keys:
                if keymap_cells_for(
                    self.keymap,
                    str(key.key_id),
                    slot_id=str(key.slot_id or key.key_id),
                    physical_layout=self._physical_layout,
                ):
                    self.select_slot_id(str(key.slot_id or key.key_id))
                    break
        else:
            self.selected_slot_id = str(current_slot_id) if current_slot_id else None
            self._refresh_selected_cells()

    def _load_layout_slot_overrides(self) -> dict[str, dict[str, object]]:
        return profiles.load_layout_slots(self.profile_name, physical_layout=self._physical_layout)

    def _detect_lightbar_device(self) -> bool:
        try:
            payload = collect_device_discovery(include_usb=True)
        except Exception as exc:
            _log_boundary_exception(
                "perkey.editor.lightbar_discovery",
                "Failed to collect perkey lightbar discovery snapshot",
                exc,
            )
            return False

        for section in ("supported", "candidates"):
            entries = payload.get(section)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("device_type") or "") == "lightbar":
                    return True
        return False

    def _persist_layout_slot_overrides(self) -> None:
        self.layout_slot_overrides = profiles.save_layout_slots(
            dict(self.layout_slot_overrides),
            self.profile_name,
            physical_layout=self._physical_layout,
        )

    def _set_layout_slot_visibility(self, slot_id: str, visible: bool) -> None:
        state = self._layout_slot_state_for_identity(slot_id)
        normalized_slot_id = state.slot_id if state is not None else str(slot_id)
        override = dict(self.layout_slot_overrides.get(normalized_slot_id, {}))
        if bool(visible):
            override.pop("visible", None)
        else:
            override["visible"] = False

        if override:
            self.layout_slot_overrides[normalized_slot_id] = override
        else:
            self.layout_slot_overrides.pop(normalized_slot_id, None)

        self._persist_layout_slot_overrides()
        self._refresh_layout_slot_controls()
        self._sync_visible_layout_state()
        self.canvas.redraw()
        set_status(
            self, layout_slot_visibility_updated(state.key_id if state is not None else normalized_slot_id, visible)
        )

    def _set_layout_slot_label(self, slot_id: str, label: str) -> None:
        states = self._get_layout_slot_states()
        state = self._layout_slot_state_for_identity(slot_id)
        normalized_slot_id = state.slot_id if state is not None else str(slot_id)
        default_labels = {slot_state.slot_id: slot_state.default_label for slot_state in states}
        normalized_label = str(label).strip()
        override = dict(self.layout_slot_overrides.get(normalized_slot_id, {}))
        default_label = default_labels.get(
            normalized_slot_id, state.key_id if state is not None else normalized_slot_id
        )

        if normalized_label and normalized_label != default_label:
            override["label"] = normalized_label
        else:
            override.pop("label", None)

        if override:
            self.layout_slot_overrides[normalized_slot_id] = override
        else:
            self.layout_slot_overrides.pop(normalized_slot_id, None)

        self._persist_layout_slot_overrides()
        self._refresh_layout_slot_controls()
        self.canvas.redraw()
        set_status(
            self,
            layout_slot_label_updated(
                state.key_id if state is not None else normalized_slot_id, normalized_label or default_label
            ),
        )

    def select_slot_id(self, slot_id: str) -> None:
        key = self._visible_key_for_slot_id(slot_id)
        if key is None:
            self._clear_selection()
            self.canvas.redraw()
            return

        self._apply_selection_for_visible_key(key)
        self._finalize_selection(str(slot_id))

    def _on_sample_tool_toggled(self) -> None:
        on_sample_tool_toggled_ui(self)

    def on_slot_clicked(self, slot_id: str) -> None:
        on_slot_clicked_ui(self, slot_id, num_rows=NUM_ROWS, num_cols=NUM_COLS)

    def sync_overlay_vars(self):
        self.overlay_controls.sync_vars_from_scope()

    def save_layout_tweaks(self):
        selected_identity = self._selected_overlay_identity()
        if self.overlay_scope.get() == "key" and selected_identity:
            profiles.save_layout_per_key(self.per_key_layout_tweaks, self.profile_name)
            set_status(self, saved_overlay_tweaks_for_key(self.selected_key_id or selected_identity))
        else:
            profiles.save_layout_global(self.layout_tweaks, self.profile_name)
            set_status(self, saved_overlay_tweaks_global())

    def reset_layout_tweaks(self):
        selected_identity = self._selected_overlay_identity()
        if self.overlay_scope.get() == "key" and selected_identity:
            self.per_key_layout_tweaks.pop(selected_identity, None)
            self.overlay_controls.sync_vars_from_scope()
            self.canvas.redraw()
            set_status(self, reset_overlay_tweaks_for_key(self.selected_key_id or selected_identity))
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
        self._layout_legend_pack = self._normalize_layout_legend_pack(layout_id, self._layout_legend_pack)
        self.config.layout_legend_pack = self._layout_legend_pack
        self._sync_layout_legend_pack_ui()

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

    def _on_layout_legend_pack_changed(self) -> None:
        legend_pack_id = self._legend_pack_var.get()
        self._layout_legend_pack = self._normalize_layout_legend_pack(self._physical_layout, legend_pack_id)
        self.config.layout_legend_pack = self._layout_legend_pack
        self._sync_layout_legend_pack_ui()
        self._sync_visible_layout_state()
        self.canvas.redraw()

    def _hide_setup_panel(self) -> None:
        self._overlay_setup_panel.grid_remove()
        self._layout_setup_controls.grid_remove()
        self._setup_panel_mode = None

    def _show_setup_panel(self, mode: str) -> None:
        self._hide_setup_panel()
        if mode == "overlay":
            self._overlay_setup_panel.grid()
            self.overlay_controls.sync_vars_from_scope()
            if getattr(self, "lightbar_controls", None) is not None:
                self.lightbar_controls.sync_vars_from_editor()
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

    def _load_keymap(self) -> dict[str, tuple[tuple[int, int], ...]]:
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
