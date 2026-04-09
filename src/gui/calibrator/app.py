from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import tkinter as tk
from tkinter import filedialog
from tkinter import ttk

from PIL import Image, ImageTk

from src.core.config import Config
from src.core.profile import profiles
from src.core.resources.defaults import get_default_keymap
from src.core.resources import layout as layout_resources, layout_legends, layouts as layout_catalog
from src.gui.theme import apply_clam_theme
from src.gui.perkey import hardware as perkey_hardware, profile_management
from src.gui.reference import overlay_geometry
from src.gui.utils import deck_render_cache, profile_backdrop_storage
from src.gui.utils.window_icon import apply_keyrgb_window_icon

from . import _app_bootstrap, _app_logic
from .helpers import canvas_render, geometry, keyboard_preview, probe, profile_storage


get_active_profile_name = profile_storage.get_active_profile_name
keymap_path = profile_storage.keymap_path
load_keymap = profile_storage.load_keymap
load_layout_global = profile_storage.load_layout_global
load_layout_per_key = profile_storage.load_layout_per_key
load_layout_slots = profile_storage.load_layout_slots
save_keymap = profile_storage.save_keymap

load_backdrop_image = profile_backdrop_storage.load_backdrop_image
reset_backdrop_image = profile_backdrop_storage.reset_backdrop_image
save_backdrop_image = profile_backdrop_storage.save_backdrop_image
KeyboardPreviewSession = keyboard_preview.KeyboardPreviewSession
get_layout_keys = layout_resources.get_layout_keys
hit_test = geometry.hit_test
redraw_calibration_canvas = canvas_render.redraw_calibration_canvas


MATRIX_ROWS = perkey_hardware.NUM_ROWS
MATRIX_COLS = perkey_hardware.NUM_COLS
KeyCell = Tuple[int, int]
KeyCells = Tuple[KeyCell, ...]
Keymap = Dict[str, KeyCells]
_LAYOUT_LABELS = {layout.layout_id: layout.label for layout in layout_catalog.LAYOUT_CATALOG}
_BACKDROP_MODE_LABELS = {
    "none": "No backdrop",
    "builtin": "Built-in seed",
    "custom": "Custom image",
}
_TK_RUNTIME_ERRORS = (tk.TclError, RuntimeError)
_WRAP_SYNC_ERRORS = _TK_RUNTIME_ERRORS + (TypeError, ValueError)
_BACKDROP_UPDATE_ERRORS = _TK_RUNTIME_ERRORS + (OSError, TypeError, ValueError)


def _keymap_path() -> Path:
    return _app_logic.keymap_path_for_active_profile(
        get_active_profile_name=get_active_profile_name,
        keymap_path=keymap_path,
    )


def _save_keymap(keymap: Keymap, *, physical_layout: str | None = None) -> None:
    _app_logic.save_keymap_for_active_profile(
        keymap,
        physical_layout=physical_layout,
        get_active_profile_name=get_active_profile_name,
        save_keymap=save_keymap,
    )


def _parse_default_keymap(layout_id: str) -> Keymap:
    return _app_logic.parse_default_keymap(
        layout_id,
        profiles=profiles,
        get_default_keymap=get_default_keymap,
        sanitize_keymap_cells=profile_management.sanitize_keymap_cells,
        num_rows=MATRIX_ROWS,
        num_cols=MATRIX_COLS,
    )


def _resolved_layout_label(layout_id: str) -> str:
    return _app_logic.resolved_layout_label(
        layout_id,
        resolve_layout_id=layout_catalog.resolve_layout_id,
        layout_labels=_LAYOUT_LABELS,
    )


def _load_profile_state(
    profile_name: str,
    *,
    physical_layout: str,
) -> tuple[
    Keymap,
    Dict[str, float],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, object]],
]:
    return _app_logic.load_profile_state(
        profile_name,
        physical_layout=physical_layout,
        load_keymap=load_keymap,
        load_layout_global=load_layout_global,
        load_layout_per_key=load_layout_per_key,
        load_layout_slots=load_layout_slots,
        sanitize_keymap_cells=profile_management.sanitize_keymap_cells,
        num_rows=MATRIX_ROWS,
        num_cols=MATRIX_COLS,
    )


def _selected_layout_legend_pack(cfg: object, *, physical_layout: str) -> str | None:
    return _app_logic.selected_layout_legend_pack(
        cfg,
        physical_layout=physical_layout,
        load_layout_legend_pack=layout_legends.load_layout_legend_pack,
    )


def _physical_layout_id(app: Any) -> str:
    return _app_logic.physical_layout_id(app)


def _visible_layout_keys(app: Any) -> list[layout_resources.KeyDef]:
    return _app_logic.visible_layout_keys(
        app,
        get_layout_keys=get_layout_keys,
        selected_layout_legend_pack_fn=_selected_layout_legend_pack,
        physical_layout_id_fn=_physical_layout_id,
    )


def _visible_key_for_slot_id(app: Any, slot_id: str | None) -> layout_resources.KeyDef | None:
    return _app_logic.visible_key_for_slot_id(app, slot_id, visible_layout_keys_fn=_visible_layout_keys)


def _probe_selected_slot_id(app: Any) -> str | None:
    return _app_logic.probe_selected_slot_id(app, visible_layout_keys_fn=_visible_layout_keys)


def _probe_selected_key_id(app: Any) -> str | None:
    return _app_logic.probe_selected_key_id(
        app,
        probe_selected_slot_id_fn=_probe_selected_slot_id,
        visible_key_for_slot_id_fn=_visible_key_for_slot_id,
    )


class KeymapCalibrator(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KeyRGB - Keymap Calibrator")
        apply_keyrgb_window_icon(self)

        # Avoid flashing a tiny default-sized window while widgets/images load.
        try:
            self.withdraw()
        except _TK_RUNTIME_ERRORS:
            pass

        self.bg_color, self.fg_color = apply_clam_theme(self)

        self.cfg = Config()
        self.preview = KeyboardPreviewSession(self.cfg, rows=MATRIX_ROWS, cols=MATRIX_COLS)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.profile_name = get_active_profile_name()
        (
            self.keymap,
            self.layout_tweaks,
            self.per_key_layout_tweaks,
            self.layout_slot_overrides,
        ) = _load_profile_state(
            self.profile_name,
            physical_layout=str(self.cfg.physical_layout or "auto"),
        )

        self.probe = probe.CalibrationProbeState(rows=MATRIX_ROWS, cols=MATRIX_COLS)

        self._deck_pil: Optional[Image.Image] = None
        self._deck_tk: Optional[ImageTk.PhotoImage] = None
        self._deck_render_cache: deck_render_cache.DeckRenderCache[ImageTk.PhotoImage] = (
            deck_render_cache.DeckRenderCache()
        )
        self._transform: Optional[overlay_geometry.CanvasTransform] = None

        _app_bootstrap.build_widgets(
            self,
            tk=tk,
            ttk=ttk,
            profiles=profiles,
            backdrop_mode_labels=_BACKDROP_MODE_LABELS,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
            wrap_sync_errors=_WRAP_SYNC_ERRORS,
        )
        _app_bootstrap.apply_window_geometry(self)
        _app_bootstrap.finish_init(self, tk_runtime_errors=_TK_RUNTIME_ERRORS)

    def _set_backdrop(self) -> None:
        _app_logic.set_backdrop(
            self,
            askopenfilename=filedialog.askopenfilename,
            save_backdrop_image=save_backdrop_image,
            save_backdrop_mode=profiles.save_backdrop_mode,
            update_errors=_BACKDROP_UPDATE_ERRORS,
        )

    def _reset_backdrop(self) -> None:
        _app_logic.reset_backdrop(
            self,
            reset_backdrop_image=reset_backdrop_image,
            save_backdrop_mode=profiles.save_backdrop_mode,
            update_errors=_BACKDROP_UPDATE_ERRORS,
        )

    def _on_backdrop_mode_changed(self, _event=None) -> None:
        _app_logic.on_backdrop_mode_changed(
            self,
            backdrop_mode_labels=_BACKDROP_MODE_LABELS,
            save_backdrop_mode=profiles.save_backdrop_mode,
            update_errors=_BACKDROP_UPDATE_ERRORS,
        )

    def _reset_keymap_defaults(self) -> None:
        _app_logic.reset_keymap_defaults(
            self,
            parse_default_keymap_fn=_parse_default_keymap,
            sanitize_keymap_cells=profile_management.sanitize_keymap_cells,
            num_rows=MATRIX_ROWS,
            num_cols=MATRIX_COLS,
            physical_layout_id_fn=_physical_layout_id,
            resolved_layout_label_fn=_resolved_layout_label,
        )

    def _restore_original_config(self) -> None:
        _app_logic.restore_original_config(self)

    def _on_close(self) -> None:
        _app_logic.on_close(self)

    def _load_deck_image(self) -> None:
        _app_logic.load_deck_image(self, load_backdrop_image=load_backdrop_image)

    def _apply_current_probe(self) -> None:
        _app_logic.apply_current_probe(self)

    def _prev(self) -> None:
        _app_logic.prev_cell(self)

    def _next(self) -> None:
        _app_logic.next_cell(self)

    def _skip(self) -> None:
        _app_logic.skip_cell(self)

    def _assign(self) -> None:
        _app_logic.assign_current_cell(
            self,
            probe_selected_slot_id_fn=_probe_selected_slot_id,
            probe_selected_key_id_fn=_probe_selected_key_id,
            keymap_cells_for=profile_management.keymap_cells_for,
            physical_layout_id_fn=_physical_layout_id,
            default_keymap_for_layout_fn=_parse_default_keymap,
        )

    def _save(self) -> None:
        _app_logic.save_current_keymap(
            self,
            save_keymap_fn=_save_keymap,
            keymap_path_fn=_keymap_path,
            physical_layout_id_fn=_physical_layout_id,
        )

    def _save_and_close(self) -> None:
        _app_logic.save_and_close(self)

    def _redraw(self) -> None:
        _app_logic.redraw(
            self,
            redraw_calibration_canvas=redraw_calibration_canvas,
            probe_selected_slot_id_fn=_probe_selected_slot_id,
            probe_selected_key_id_fn=_probe_selected_key_id,
            physical_layout_id_fn=_physical_layout_id,
            selected_layout_legend_pack_fn=_selected_layout_legend_pack,
        )

    def _on_click(self, e: tk.Event) -> None:
        _app_logic.on_click(
            self,
            e,
            hit_test_fn=self._hit_test,
            keymap_cells_for=profile_management.keymap_cells_for,
            physical_layout_id_fn=_physical_layout_id,
        )

    def _hit_test(self, x: int, y: int) -> Optional[layout_resources.KeyDef]:
        return _app_logic.hit_test_point(
            self,
            x,
            y,
            hit_test=hit_test,
            visible_layout_keys_fn=_visible_layout_keys,
            image_size=layout_resources.BASE_IMAGE_SIZE,
        )


def main() -> None:
    # Ensure config dir exists early (for saving)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    app = KeymapCalibrator()
    app.mainloop()


if __name__ == "__main__":
    main()
