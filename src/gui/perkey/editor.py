#!/usr/bin/env python3
"""KeyRGB Per-Key Editor (Tkinter)"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from src.core.backends.base import KeyboardDevice
from src.core.config import Config
from src.core.diagnostics.device_discovery import collect_device_discovery
from src.core.resources.defaults import get_default_layout_tweaks
from src.core.profile import profiles
from src.core.utils.logging_utils import log_throttled
from src.gui.theme import apply_clam_theme
from src.gui.utils.window_icon import apply_keyrgb_window_icon
from . import color_utils, commit_pipeline, hardware, keyboard_apply, overlay, profile_management
from . import window_geometry
from .editor_support import backdrop as editor_backdrop
from .editor_support import bootstrap as editor_bootstrap
from .editor_support import layout as editor_layout
from .editor_support import runtime as editor_runtime
from .editor_support import selection as editor_selection
from .editor_support import ui as editor_ui
from .ui import backdrop, bulk_color, calibrator, full_map, keymap, profile_actions, sample_tool, status, wheel_apply

logger = logging.getLogger(__name__)

NUM_ROWS = hardware.NUM_ROWS
NUM_COLS = hardware.NUM_COLS
on_sample_tool_toggled_ui = sample_tool.on_sample_tool_toggled_ui
on_slot_clicked_ui = sample_tool.on_slot_clicked_ui

_TK_CALL_ERRORS = (RuntimeError, tk.TclError)
_VALUE_COERCION_ERRORS = (TypeError, ValueError)
_BACKDROP_PERSISTENCE_ERRORS = (AttributeError, OSError, TypeError, ValueError)


def _log_boundary_exception(key: str, msg: str, exc: Exception) -> None:
    log_throttled(logger, key, interval_s=60, level=logging.DEBUG, msg=msg, exc=exc)


def _last_non_black_color_or(editor: object, default: object) -> object:
    try:
        return editor._last_non_black_color
    except AttributeError:
        return default


class PerKeyEditor:
    # Attributes initialized by editor_bootstrap.initialize_editor
    config: Config
    kb: KeyboardDevice | None
    colors: profile_management.PerKeyColors
    _commit_pipeline: commit_pipeline.PerKeyCommitPipeline
    per_key_layout_tweaks: dict[str, dict[str, float]]
    lightbar_overlay: dict[str, bool | float]
    profile_name: str
    _physical_layout: str

    def __init__(self):
        editor_bootstrap.initialize_editor(
            self,
            tk=tk,
            ttk=ttk,
            config_cls=Config,
            profiles=profiles,
            apply_keyrgb_window_icon=apply_keyrgb_window_icon,
            apply_perkey_editor_geometry=window_geometry.apply_perkey_editor_geometry,
            compute_perkey_editor_min_content_size=window_geometry.compute_perkey_editor_min_content_size,
            fit_perkey_editor_geometry_to_content=window_geometry.fit_perkey_editor_geometry_to_content,
            apply_clam_theme=apply_clam_theme,
            tk_call_errors=_TK_CALL_ERRORS,
            log_boundary_exception=_log_boundary_exception,
            normalize_layout_legend_pack_fn=self._normalize_layout_legend_pack,
            initial_last_non_black_color=color_utils.initial_last_non_black_color,
            load_profile_colors=profile_management.load_profile_colors,
            sanitize_keymap_cells=profile_management.sanitize_keymap_cells,
            per_key_commit_pipeline_cls=commit_pipeline.PerKeyCommitPipeline,
            get_keyboard=hardware.get_keyboard,
            build_ui_fn=self._build_ui,
            set_status=status.set_status,
            no_keymap_found_initial=status.no_keymap_found_initial,
            num_rows=hardware.NUM_ROWS,
            num_cols=hardware.NUM_COLS,
        )

    def _on_backdrop_transparency_changed(self, value: str) -> None:
        editor_backdrop.on_backdrop_transparency_changed(
            self,
            value,
            value_coercion_errors=_VALUE_COERCION_ERRORS,
            tk_call_errors=_TK_CALL_ERRORS,
            log_boundary_exception=_log_boundary_exception,
        )

    def _apply_backdrop_transparency_redraw(self) -> None:
        editor_backdrop.apply_backdrop_transparency_redraw(self, log_boundary_exception=_log_boundary_exception)

    def _persist_backdrop_transparency(self) -> None:
        editor_backdrop.persist_backdrop_transparency(
            self,
            profiles=profiles,
            value_coercion_errors=_VALUE_COERCION_ERRORS,
            tk_call_errors=_TK_CALL_ERRORS,
            backdrop_persistence_errors=_BACKDROP_PERSISTENCE_ERRORS,
            log_boundary_exception=_log_boundary_exception,
        )

    def _on_backdrop_mode_changed(self, _event=None) -> None:
        editor_backdrop.on_backdrop_mode_changed(
            self,
            profiles=profiles,
            tk_call_errors=_TK_CALL_ERRORS,
            backdrop_persistence_errors=_BACKDROP_PERSISTENCE_ERRORS,
            log_boundary_exception=_log_boundary_exception,
        )

    def _build_ui(self):
        editor_ui.build_editor_ui(self)

    _normalize_layout_legend_pack = staticmethod(editor_layout.normalize_layout_legend_pack)
    _resolved_layout_legend_pack_id = editor_layout.resolved_layout_legend_pack_id

    def _sync_layout_legend_pack_ui(self) -> None:
        editor_layout.sync_layout_legend_pack_ui(
            self,
            tk_call_errors=_TK_CALL_ERRORS,
            log_boundary_exception=_log_boundary_exception,
        )

    _get_visible_layout_keys = editor_selection.get_visible_layout_keys
    _visible_key_maps = editor_selection.visible_key_maps
    _visible_key_for_key_id = editor_selection.visible_key_for_key_id
    _visible_key_for_slot_id = editor_selection.visible_key_for_slot_id
    _slot_id_for_key_id = editor_selection.slot_id_for_key_id
    _key_id_for_slot_id = editor_selection.key_id_for_slot_id
    _clear_selection = editor_selection.clear_selection
    _apply_selection_for_visible_key = editor_selection.apply_selection_for_visible_key
    _selected_display_key_id = editor_selection.selected_display_key_id
    _refresh_selected_cells = editor_selection.refresh_selected_cells
    _finalize_selection = editor_selection.finalize_selection
    _refresh_layout_slot_controls = editor_layout.refresh_layout_slot_controls
    _get_layout_slot_states = editor_layout.get_layout_slot_states_for_editor
    _selected_overlay_identity = editor_layout.selected_overlay_identity
    _layout_slot_state_for_identity = editor_layout.layout_slot_state_for_identity
    _sync_visible_layout_state = editor_layout.sync_visible_layout_state
    _load_layout_slot_overrides = editor_layout.load_layout_slot_overrides

    def _detect_lightbar_device(self) -> bool:
        return editor_layout.detect_lightbar_device(
            collect_device_discovery=collect_device_discovery,
            log_boundary_exception=_log_boundary_exception,
        )

    def _persist_layout_slot_overrides(self) -> None:
        editor_layout.persist_layout_slot_overrides(self)

    def _set_layout_slot_visibility(self, slot_id: str, visible: bool) -> None:
        editor_layout.set_layout_slot_visibility(self, slot_id, visible)

    def _set_layout_slot_label(self, slot_id: str, label: str) -> None:
        editor_layout.set_layout_slot_label(self, slot_id, label)

    select_slot_id = editor_selection.select_slot_id

    def _on_sample_tool_toggled(self) -> None:
        on_sample_tool_toggled_ui(self)

    def on_slot_clicked(self, slot_id: str) -> None:
        on_slot_clicked_ui(self, slot_id, num_rows=hardware.NUM_ROWS, num_cols=hardware.NUM_COLS)

    def sync_overlay_vars(self):
        self.overlay_controls.sync_vars_from_scope()

    def save_layout_tweaks(self):
        editor_runtime.save_layout_tweaks(self, profiles=profiles, status=status)

    def reset_layout_tweaks(self):
        editor_runtime.reset_layout_tweaks(
            self,
            get_default_layout_tweaks=get_default_layout_tweaks,
            status=status,
        )

    def auto_sync_per_key_overlays(self):
        editor_runtime.auto_sync_per_key_overlays(self, overlay=overlay, status=status)

    def _run_calibrator(self):
        calibrator.run_keymap_calibrator_ui(self)

    def _reload_keymap(self):
        keymap.reload_keymap_ui(self)

    def _commit(self, *, force: bool = False):
        editor_runtime.commit(
            self,
            force=force,
            hardware=hardware,
            color_utils=color_utils,
            keyboard_apply=keyboard_apply,
            status=status,
            last_non_black_color_or=_last_non_black_color_or,
        )

    def _on_color_change(self, r: int, g: int, b: int):
        wheel_apply.on_wheel_color_change_ui(self, r, g, b, num_rows=hardware.NUM_ROWS, num_cols=hardware.NUM_COLS)

    def _on_color_release(self, r: int, g: int, b: int):
        wheel_apply.on_wheel_color_release_ui(self, r, g, b, num_rows=hardware.NUM_ROWS, num_cols=hardware.NUM_COLS)

    def _set_backdrop(self):
        backdrop.set_backdrop_ui(self)

    def _reset_backdrop(self):
        backdrop.reset_backdrop_ui(self)

    def _fill_all(self):
        bulk_color.fill_all_ui(self, num_rows=hardware.NUM_ROWS, num_cols=hardware.NUM_COLS)

    def _ensure_full_map(self):
        full_map.ensure_full_map_ui(self, num_rows=hardware.NUM_ROWS, num_cols=hardware.NUM_COLS)

    def _clear_all(self):
        bulk_color.clear_all_ui(self, num_rows=hardware.NUM_ROWS, num_cols=hardware.NUM_COLS)

    _load_layout_tweaks = editor_layout.load_layout_tweaks
    _load_per_key_layout_tweaks = editor_layout.load_per_key_layout_tweaks
    _on_layout_changed = editor_layout.on_layout_changed
    _on_layout_legend_pack_changed = editor_layout.on_layout_legend_pack_changed
    _hide_setup_panel = editor_layout.hide_setup_panel
    _show_setup_panel = editor_layout.show_setup_panel
    _toggle_overlay = editor_layout.toggle_overlay
    _toggle_layout_setup = editor_layout.toggle_layout_setup

    def _new_profile(self):
        profile_actions.new_profile_ui(self)

    def _activate_profile(self):
        profile_actions.activate_profile_ui(self)

    def _save_profile(self):
        profile_actions.save_profile_ui(self)

    def _delete_profile(self):
        profile_actions.delete_profile_ui(self)

    def _set_default_profile(self):
        profile_actions.set_default_profile_ui(self)

    def _reset_layout_defaults(self):
        profile_actions.reset_layout_defaults_ui(self)

    def _load_keymap(self) -> dict[str, tuple[tuple[int, int], ...]]:
        return editor_runtime.load_keymap(
            self,
            profiles=profiles,
            profile_management=profile_management,
            hardware=hardware,
        )

    def run(self):
        self.root.mainloop()


def main():
    PerKeyEditor().run()


if __name__ == "__main__":
    main()
