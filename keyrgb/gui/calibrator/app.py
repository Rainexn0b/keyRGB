from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Sequence
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

from PIL import Image, ImageTk

from . import _app_bootstrap, _app_logic, guided as _guided
from ._internal import _app_runtime_deps

_SAVE_AND_CLOSE_BUTTON_TEXT = _guided._SAVE_AND_CLOSE_BUTTON_TEXT
_SAVE_BUTTON_TEXT = _guided._SAVE_BUTTON_TEXT
GuidedConfigView = _guided.GuidedConfigView
GuidedSession = _guided.GuidedSession
GuidedSessionError = _guided.GuidedSessionError
GuidedSessionHelpRequested = _guided.GuidedSessionHelpRequested
guided_session_path_of = _guided.guided_session_path_of
load_guided_session = _guided.load_guided_session
parse_guided_session_argv = _guided.parse_guided_session_argv
write_guided_result = _guided.write_guided_result
recover_stale_preview_journal = _guided.recover_stale_preview_journal

if TYPE_CHECKING:
    from keyrgb.core.resources.layout import KeyDef
    from keyrgb.gui.calibrator._app_bootstrap import (
        _BindableWidgetProtocol,
        _BoolVarProtocol,
        _ConfigurableWidgetProtocol,
    )
    from keyrgb.gui.reference import overlay_geometry
    from keyrgb.gui.utils import deck_render_cache

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
    # Set by _app_bootstrap.build_widgets() during __init__
    canvas: _BindableWidgetProtocol
    lbl_cell: _ConfigurableWidgetProtocol
    lbl_status: _ConfigurableWidgetProtocol
    _show_backdrop_var: _BoolVarProtocol

    def __init__(
        self,
        guided_session_path: str | Path | None = None,
        guided_session: GuidedSession | None = None,
    ) -> None:
        super().__init__()
        self.title("KeyRGB - Keymap Calibrator")
        apply_keyrgb_window_icon(self)

        # Avoid flashing a tiny default-sized window while widgets/images load.
        try:
            self.withdraw()
        except _TK_RUNTIME_ERRORS:
            pass

        self.bg_color, self.fg_color = apply_clam_theme(self)

        self.guided_session_path = Path(guided_session_path).expanduser() if guided_session_path is not None else None
        base_cfg = Config()
        # Deterministic automatic crash recovery: a stale preview journal is
        # restored before the new preview session snapshots its originals.
        recover_stale_preview_journal(base_cfg)
        if self.guided_session_path is not None:
            # Direct construction compatibility: main() already validated and
            # passes the session in, so no second file read happens there.
            session = guided_session
            if session is None:
                session = load_guided_session(
                    self.guided_session_path,
                    num_rows=MATRIX_ROWS,
                    num_cols=MATRIX_COLS,
                )
            self.cfg: Config | GuidedConfigView = GuidedConfigView(
                base_cfg,
                physical_layout=session.physical_layout,
                legend_pack=session.legend_pack,
            )
            self.profile_name = get_active_profile_name()
            self.keymap = dict(session.keymap)
            self.layout_tweaks = dict(session.layout_tweaks)
            self.per_key_layout_tweaks = {
                str(slot): dict(tweaks) for slot, tweaks in session.per_key_layout_tweaks.items()
            }
            self.layout_slot_overrides = {
                str(slot): dict(overrides) for slot, overrides in session.slot_overrides.items()
            }
            self.matrix_rows = int(session.num_rows or MATRIX_ROWS)
            self.matrix_cols = int(session.num_cols or MATRIX_COLS)
        else:
            self.cfg = base_cfg
            self.matrix_rows = MATRIX_ROWS
            self.matrix_cols = MATRIX_COLS
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

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # The preview session owns the real Config (it mutates persisted
        # lighting state); app.cfg may be the guided layout view, which only
        # overrides layout reads and forwards everything else to base_cfg.
        self.preview = KeyboardPreviewSession(base_cfg, rows=self.matrix_rows, cols=self.matrix_cols)

        self.probe = probe.CalibrationProbeState(rows=self.matrix_rows, cols=self.matrix_cols)

        self._deck_pil: Image.Image | None = None
        self._deck_tk: ImageTk.PhotoImage | None = None
        self._deck_render_cache: deck_render_cache.DeckRenderCache[ImageTk.PhotoImage] = (
            deck_render_cache.DeckRenderCache()
        )
        self._transform: overlay_geometry.CanvasTransform | None = None

        if self.guided_session_path is not None:
            _app_bootstrap.build_widgets(
                self,
                tk=tk,
                ttk=ttk,
                tk_runtime_errors=_TK_RUNTIME_ERRORS,
                wrap_sync_errors=_WRAP_SYNC_ERRORS,
                save_text=_SAVE_BUTTON_TEXT,
                save_and_close_text=_SAVE_AND_CLOSE_BUTTON_TEXT,
            )
        else:
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
            num_rows=int(getattr(self, "matrix_rows", MATRIX_ROWS)),
            num_cols=int(getattr(self, "matrix_cols", MATRIX_COLS)),
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
        # Guided mode writes the normalized keymap back to the session file
        # ("Use Result") and never touches profile data.  Ctrl+S maps here
        # via install_window_bindings, same as standalone Save.
        session_path = guided_session_path_of(self)
        if session_path is not None:
            _app_logic.save_guided_result(
                self,
                session_path=session_path,
                physical_layout=_physical_layout_id(self),
                write_result_fn=write_guided_result,
            )
            return
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

    def _hit_test(self, x: int, y: int) -> KeyDef | None:
        return _app_logic.hit_test_point(
            self,
            x,
            y,
            hit_test=hit_test,
            visible_layout_keys_fn=_visible_layout_keys,
            image_size=layout_resources.BASE_IMAGE_SIZE,
        )


def main(argv: Sequence[str] = ()) -> None:
    """Run the standalone calibrator, or a guided session with ``--guided-session PATH``.

    With no flags, behavior is exactly the historical standalone flow
    (profile Save / Save && Close).  Guided mode validates the session file
    once, before acquiring the singleton lock or touching any profile data,
    and passes the validated session into the app (no second file read).
    Malformed input exits with status 2; ``-h``/``--help`` prints usage and
    exits 0.
    """
    from keyrgb.gui import single_instance

    try:
        guided_path = parse_guided_session_argv(argv)
        guided_session: GuidedSession | None = None
        if guided_path is not None:
            guided_session = load_guided_session(guided_path, num_rows=MATRIX_ROWS, num_cols=MATRIX_COLS)
    except GuidedSessionHelpRequested as help_request:
        print(str(help_request), file=sys.stdout)
        return
    except GuidedSessionError as exc:
        print(f"keyrgb-calibrate: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    single_instance.acquire_gui_instance_or_exit("calibrator")
    # Ensure config dir exists early (for saving)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    app = KeymapCalibrator(guided_session_path=guided_path, guided_session=guided_session)
    app.mainloop()


if __name__ == "__main__":
    main()
