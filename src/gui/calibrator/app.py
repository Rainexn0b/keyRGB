from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from . import _app_bootstrap, _app_logic
from ._internal import _app_runtime_deps


Config = _app_runtime_deps.Config
profiles = _app_runtime_deps.profiles
get_default_keymap = _app_runtime_deps.get_default_keymap
layout_resources = _app_runtime_deps.layout_resources
layout_legends = _app_runtime_deps.layout_legends
layout_catalog = _app_runtime_deps.layout_catalog
apply_clam_theme = _app_runtime_deps.apply_clam_theme
profile_management = _app_runtime_deps.profile_management
overlay_geometry = _app_runtime_deps.overlay_geometry
deck_render_cache = _app_runtime_deps.deck_render_cache
apply_keyrgb_window_icon = _app_runtime_deps.apply_keyrgb_window_icon
probe = _app_runtime_deps.probe

get_active_profile_name = _app_runtime_deps.get_active_profile_name
keymap_path = _app_runtime_deps.keymap_path
load_keymap = _app_runtime_deps.load_keymap
load_layout_global = _app_runtime_deps.load_layout_global
load_layout_per_key = _app_runtime_deps.load_layout_per_key
load_layout_slots = _app_runtime_deps.load_layout_slots
save_keymap = _app_runtime_deps.save_keymap

load_backdrop_image = _app_runtime_deps.load_backdrop_image
KeyboardPreviewSession = _app_runtime_deps.KeyboardPreviewSession
get_layout_keys = _app_runtime_deps.get_layout_keys
hit_test = _app_runtime_deps.hit_test
redraw_calibration_canvas = _app_runtime_deps.redraw_calibration_canvas


MATRIX_ROWS = _app_runtime_deps.MATRIX_ROWS
MATRIX_COLS = _app_runtime_deps.MATRIX_COLS
KeyCell = _app_runtime_deps.KeyCell
KeyCells = _app_runtime_deps.KeyCells
Keymap = _app_runtime_deps.Keymap
LayoutTweaks = _app_runtime_deps.LayoutTweaks
PerKeyLayoutTweaks = _app_runtime_deps.PerKeyLayoutTweaks
LayoutSlotOverrides = _app_runtime_deps.LayoutSlotOverrides
_LAYOUT_LABELS = _app_runtime_deps._LAYOUT_LABELS
_TK_RUNTIME_ERRORS = _app_runtime_deps._TK_RUNTIME_ERRORS
_WRAP_SYNC_ERRORS = _app_runtime_deps._WRAP_SYNC_ERRORS
_CalibratorConfigLike = _app_runtime_deps._CalibratorConfigLike
_CalibratorAppLike = _app_runtime_deps._CalibratorAppLike

# Keep module-level dependency names explicit so tests can monkeypatch app.py
# and the bound profile-layout wrappers still resolve through this module.
(
    _keymap_path,
    _save_keymap,
    _parse_default_keymap,
    _resolved_layout_label,
    _load_profile_state,
    _selected_layout_legend_pack,
    _physical_layout_id,
    _visible_layout_keys,
    _visible_key_for_slot_id,
    _probe_selected_slot_id,
    _probe_selected_key_id,
) = _app_runtime_deps.bind_profile_layout_wrappers(__name__)


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

        self.bg_color, self.fg_color = apply_clam_theme(
            self,
            include_checkbuttons=True,
            map_checkbutton_state=True,
        )

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

        self._deck_pil: Image.Image | None = None
        self._deck_tk: ImageTk.PhotoImage | None = None
        self._deck_render_cache: deck_render_cache.DeckRenderCache[ImageTk.PhotoImage] = (
            deck_render_cache.DeckRenderCache()
        )
        self._transform: overlay_geometry.CanvasTransform | None = None

        _app_bootstrap.build_widgets(
            self,
            tk=tk,
            ttk=ttk,
            tk_runtime_errors=_TK_RUNTIME_ERRORS,
            wrap_sync_errors=_WRAP_SYNC_ERRORS,
        )
        _app_bootstrap.apply_window_geometry(self)
        _app_bootstrap.finish_init(self, tk_runtime_errors=_TK_RUNTIME_ERRORS)

    def _on_show_backdrop_changed(self) -> None:
        _app_logic.on_show_backdrop_changed(
            self,
            load_backdrop_image=load_backdrop_image,
            load_backdrop_mode=profiles.load_backdrop_mode,
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
        _app_logic.load_deck_image_for_calibrator(
            self,
            load_backdrop_image=load_backdrop_image,
            load_backdrop_mode=profiles.load_backdrop_mode,
        )

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

    def _hit_test(self, x: int, y: int) -> layout_resources.KeyDef | None:
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
