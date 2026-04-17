"""Runtime dependency aliases for the calibrator app facade."""

from __future__ import annotations

import sys
import tkinter as tk
from functools import partial
from typing import cast

from src.core.config import Config
from src.core.profile import profiles
from src.core.resources import layout as layout_resources, layout_legends, layouts as layout_catalog
from src.core.resources.defaults import get_default_keymap
from src.gui.perkey import hardware as perkey_hardware, profile_management
from src.gui.reference import overlay_geometry
from src.gui.theme import apply_clam_theme
from src.gui.utils import deck_render_cache, profile_backdrop_storage
from src.gui.utils.window_icon import apply_keyrgb_window_icon

from . import _app_profile_layout, _app_profile_layout_bindings
from ..helpers import canvas_render, geometry, keyboard_preview, probe, profile_storage


__all__ = (
    "Config",
    "KeyboardPreviewSession",
    "KeyCell",
    "KeyCells",
    "Keymap",
    "LayoutSlotOverrides",
    "LayoutTweaks",
    "MATRIX_COLS",
    "MATRIX_ROWS",
    "PerKeyLayoutTweaks",
    "_CalibratorAppLike",
    "_CalibratorConfigLike",
    "_LAYOUT_LABELS",
    "_TK_RUNTIME_ERRORS",
    "_WRAP_SYNC_ERRORS",
    "apply_clam_theme",
    "apply_keyrgb_window_icon",
    "bind_profile_layout_wrappers",
    "deck_render_cache",
    "get_active_profile_name",
    "get_default_keymap",
    "get_layout_keys",
    "hit_test",
    "keymap_path",
    "layout_catalog",
    "layout_legends",
    "layout_resources",
    "load_backdrop_image",
    "load_keymap",
    "load_layout_global",
    "load_layout_per_key",
    "load_layout_slots",
    "overlay_geometry",
    "probe",
    "profile_management",
    "profiles",
    "redraw_calibration_canvas",
    "save_keymap",
)


get_active_profile_name = profile_storage.get_active_profile_name
keymap_path = profile_storage.keymap_path
load_keymap = profile_storage.load_keymap
load_layout_global = profile_storage.load_layout_global
load_layout_per_key = profile_storage.load_layout_per_key
load_layout_slots = profile_storage.load_layout_slots
save_keymap = profile_storage.save_keymap

load_backdrop_image = profile_backdrop_storage.load_backdrop_image
KeyboardPreviewSession = keyboard_preview.KeyboardPreviewSession
get_layout_keys = layout_resources.get_layout_keys
hit_test = geometry.hit_test
redraw_calibration_canvas = canvas_render.redraw_calibration_canvas


MATRIX_ROWS = perkey_hardware.NUM_ROWS
MATRIX_COLS = perkey_hardware.NUM_COLS
KeyCell = _app_profile_layout.KeyCell
KeyCells = _app_profile_layout.KeyCells
Keymap = _app_profile_layout.Keymap
LayoutTweaks = _app_profile_layout.LayoutTweaks
PerKeyLayoutTweaks = _app_profile_layout.PerKeyLayoutTweaks
LayoutSlotOverrides = _app_profile_layout.LayoutSlotOverrides
_CalibratorConfigLike = _app_profile_layout._CalibratorConfigLike
_CalibratorAppLike = _app_profile_layout._CalibratorAppLike

_LAYOUT_LABELS = {layout.layout_id: layout.label for layout in layout_catalog.LAYOUT_CATALOG}
_TK_RUNTIME_ERRORS = (tk.TclError, RuntimeError)
_WRAP_SYNC_ERRORS = _TK_RUNTIME_ERRORS + (TypeError, ValueError)


def bind_profile_layout_wrappers(module_name: str):
    """Bind profile-layout wrappers to the live app module for test monkeypatch seams."""

    deps = cast(_app_profile_layout_bindings._AppProfileLayoutDeps, sys.modules[module_name])
    return (
        partial(_app_profile_layout_bindings._keymap_path, deps),
        partial(_app_profile_layout_bindings._save_keymap, deps),
        partial(_app_profile_layout_bindings._parse_default_keymap, deps),
        partial(_app_profile_layout_bindings._resolved_layout_label, deps),
        partial(_app_profile_layout_bindings._load_profile_state, deps),
        partial(_app_profile_layout_bindings._selected_layout_legend_pack, deps),
        partial(_app_profile_layout_bindings._physical_layout_id, deps),
        partial(_app_profile_layout_bindings._visible_layout_keys, deps),
        partial(_app_profile_layout_bindings._visible_key_for_slot_id, deps),
        partial(_app_profile_layout_bindings._probe_selected_slot_id, deps),
        partial(_app_profile_layout_bindings._probe_selected_key_id, deps),
    )
