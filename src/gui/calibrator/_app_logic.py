from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping, Protocol, TypeAlias

from PIL import Image

from ._internal import _app_canvas_interactions, _app_profile_layout
from ._internal._app_profile_layout import (
    KeyCell,
    KeyCells,
    Keymap,
    PhysicalLayoutIdFn,
    _CalibratorAppLike,
    _ProbeSelectedIdentityFn,
    _SanitizeKeymapCellsFn,
)


_CalibratorConfigLike = _app_profile_layout._CalibratorConfigLike
keymap_path_for_active_profile = _app_profile_layout.keymap_path_for_active_profile
save_keymap_for_active_profile = _app_profile_layout.save_keymap_for_active_profile
parse_default_keymap = _app_profile_layout.parse_default_keymap
resolved_layout_label = _app_profile_layout.resolved_layout_label
load_profile_state = _app_profile_layout.load_profile_state
selected_layout_legend_pack = _app_profile_layout.selected_layout_legend_pack
physical_layout_id = _app_profile_layout.physical_layout_id
visible_layout_keys = _app_profile_layout.visible_layout_keys
visible_key_for_slot_id = _app_profile_layout.visible_key_for_slot_id
probe_selected_slot_id = _app_profile_layout.probe_selected_slot_id
probe_selected_key_id = _app_profile_layout.probe_selected_key_id


class _LoadBackdropImageFn(Protocol):
    def __call__(self, profile_name: str, *, backdrop_mode: str | None = None) -> Image.Image | None: ...


class _ParseDefaultKeymapFn(Protocol):
    def __call__(self, layout_id: str) -> Keymap: ...


class _KeymapCellsForFn(Protocol):
    def __call__(
        self,
        keymap: Mapping[str, object],
        key_id: str | None,
        *,
        slot_id: str | None = None,
        physical_layout: str | None = None,
    ) -> KeyCells: ...


class _SaveCurrentKeymapFn(Protocol):
    def __call__(self, keymap: Keymap, *, physical_layout: str | None = None) -> None: ...


LoadBackdropModeFn: TypeAlias = Callable[[str], str]
ResolvedLayoutLabelFn: TypeAlias = Callable[[str], str]
DefaultKeymapForLayoutFn: TypeAlias = Callable[[str], Keymap]
KeymapPathGetter: TypeAlias = Callable[[], Path]


def load_deck_image_for_calibrator(
    app: _CalibratorAppLike,
    *,
    load_backdrop_image: _LoadBackdropImageFn,
    load_backdrop_mode: LoadBackdropModeFn,
) -> None:
    """Load backdrop for calibrator display, treating 'none' mode as 'builtin'."""
    mode = load_backdrop_mode(app.profile_name)
    effective_mode = "builtin" if mode == "none" else mode
    img = load_backdrop_image(app.profile_name, backdrop_mode=effective_mode)
    if img is None and effective_mode not in ("none", "builtin"):
        img = load_backdrop_image(app.profile_name, backdrop_mode="builtin")
    app._deck_pil = img
    app._deck_render_cache.clear()


def on_show_backdrop_changed(
    app: _CalibratorAppLike,
    *,
    load_backdrop_image: _LoadBackdropImageFn,
    load_backdrop_mode: LoadBackdropModeFn,
) -> None:
    """Toggle backdrop display in the calibrator without saving the profile's backdrop mode."""
    if app._show_backdrop_var.get():
        load_deck_image_for_calibrator(
            app,
            load_backdrop_image=load_backdrop_image,
            load_backdrop_mode=load_backdrop_mode,
        )
    else:
        app._deck_pil = None
        app._deck_render_cache.clear()
    app._redraw()


def reset_keymap_defaults(
    app: _CalibratorAppLike,
    *,
    parse_default_keymap_fn: _ParseDefaultKeymapFn,
    sanitize_keymap_cells: _SanitizeKeymapCellsFn,
    num_rows: int,
    num_cols: int,
    physical_layout_id_fn: PhysicalLayoutIdFn,
    resolved_layout_label_fn: ResolvedLayoutLabelFn,
) -> None:
    physical_layout = physical_layout_id_fn(app)
    app.keymap = sanitize_keymap_cells(parse_default_keymap_fn(physical_layout), num_rows=num_rows, num_cols=num_cols)
    app._redraw()
    app.lbl_status.configure(text=f"Reset keymap to {resolved_layout_label_fn(physical_layout)} defaults")


def restore_original_config(app: _CalibratorAppLike) -> None:
    app.preview.restore()


def on_close(app: _CalibratorAppLike) -> None:
    app._restore_original_config()
    app.destroy()


def apply_current_probe(app: _CalibratorAppLike) -> None:
    row, col = app.probe.current_cell
    app.lbl_cell.configure(text=f"Probing matrix cell: ({row}, {col})")
    app.preview.apply_probe_cell(row, col)
    app.after(50, lambda: None)


def prev_cell(app: _CalibratorAppLike) -> None:
    app.probe.prev_cell()
    app._apply_current_probe()


def next_cell(app: _CalibratorAppLike) -> None:
    app.probe.next_cell()
    app._apply_current_probe()


def skip_cell(app: _CalibratorAppLike) -> None:
    app.probe.clear_selection()
    app.lbl_status.configure(text="Skipped. Move to next cell.")
    app._next()


def assign_current_cell(
    app: _CalibratorAppLike,
    *,
    probe_selected_slot_id_fn: _ProbeSelectedIdentityFn,
    probe_selected_key_id_fn: _ProbeSelectedIdentityFn,
    keymap_cells_for: _KeymapCellsForFn,
    physical_layout_id_fn: PhysicalLayoutIdFn,
    default_keymap_for_layout_fn: DefaultKeymapForLayoutFn,
) -> None:
    slot_id = probe_selected_slot_id_fn(app)
    key_id = probe_selected_key_id_fn(app)
    if not slot_id and not key_id:
        app.lbl_status.configure(text="Select a key on the image first")
        return

    current_cell = app.probe.current_cell
    physical_layout = physical_layout_id_fn(app)
    key_identity = str(slot_id or key_id)
    display_key_id = str(key_id or key_identity)
    selected_identities = tuple(
        dict.fromkeys(identity for identity in (key_identity, str(key_id or "").strip()) if identity)
    )
    default_keymap = default_keymap_for_layout_fn(physical_layout)
    default_owner_by_cell = {cell: str(identity) for identity, cells in default_keymap.items() for cell in cells}

    other_owners_by_cell: dict[KeyCell, set[str]] = {}
    for existing_identity, existing_cells in app.keymap.items():
        if existing_identity in selected_identities:
            continue
        for cell in existing_cells:
            other_owners_by_cell.setdefault(cell, set()).add(str(existing_identity))

    selected_cells: list[KeyCell] = []
    seen_selected_cells: set[KeyCell] = set()
    for identity in selected_identities:
        for cell in app.keymap.get(identity, ()):
            if cell == current_cell or cell in seen_selected_cells:
                continue
            other_owners = other_owners_by_cell.get(cell, set())
            if other_owners and default_owner_by_cell.get(cell) not in {None, key_identity}:
                continue
            seen_selected_cells.add(cell)
            selected_cells.append(cell)

    selected_cell_set = set(selected_cells)
    new_keymap: Keymap = {}
    for existing_identity, existing_cells in app.keymap.items():
        if existing_identity in selected_identities:
            continue
        filtered_cells = tuple(
            cell
            for cell in existing_cells
            if cell != current_cell
            and not (cell in selected_cell_set and default_owner_by_cell.get(cell) in {None, key_identity})
        )
        if filtered_cells:
            new_keymap[str(existing_identity)] = filtered_cells

    cells = list(
        keymap_cells_for(
            {key_identity: tuple(selected_cells)},
            display_key_id,
            slot_id=slot_id,
            physical_layout=physical_layout,
        )
    )
    if current_cell not in cells:
        cells.append(current_cell)

    new_keymap[key_identity] = tuple(cells)
    app.keymap = new_keymap
    app.lbl_status.configure(text=f"Assigned {display_key_id} -> {current_cell} ({len(cells)} cell(s))")
    app._redraw()
    app._next()


def save_current_keymap(
    app: _CalibratorAppLike,
    *,
    save_keymap_fn: _SaveCurrentKeymapFn,
    keymap_path_fn: KeymapPathGetter,
    physical_layout_id_fn: PhysicalLayoutIdFn,
) -> None:
    save_keymap_fn(app.keymap, physical_layout=physical_layout_id_fn(app))
    app.lbl_status.configure(text=f"Saved to {str(keymap_path_fn())}")


def save_and_close(app: _CalibratorAppLike) -> None:
    app._save()
    app._restore_original_config()
    app.destroy()


def redraw(
    app: _CalibratorAppLike,
    *,
    redraw_calibration_canvas: _app_canvas_interactions._RedrawCalibrationCanvasFn,
    probe_selected_slot_id_fn: _ProbeSelectedIdentityFn,
    probe_selected_key_id_fn: _ProbeSelectedIdentityFn,
    physical_layout_id_fn: PhysicalLayoutIdFn,
    selected_layout_legend_pack_fn: _app_profile_layout._SelectedLayoutLegendPackFn,
) -> None:
    _app_canvas_interactions.redraw(
        app,
        redraw_calibration_canvas=redraw_calibration_canvas,
        probe_selected_slot_id_fn=probe_selected_slot_id_fn,
        probe_selected_key_id_fn=probe_selected_key_id_fn,
        physical_layout_id_fn=physical_layout_id_fn,
        selected_layout_legend_pack_fn=selected_layout_legend_pack_fn,
    )


def on_click(
    app: _CalibratorAppLike,
    event: _app_canvas_interactions._ClickEvent,
    *,
    hit_test_fn: _app_canvas_interactions._HitTestByPointFn,
    keymap_cells_for: _KeymapCellsForFn,
    physical_layout_id_fn: PhysicalLayoutIdFn,
) -> None:
    _app_canvas_interactions.on_click(
        app,
        event,
        hit_test_fn=hit_test_fn,
        keymap_cells_for=keymap_cells_for,
        physical_layout_id_fn=physical_layout_id_fn,
    )


def hit_test_point(
    app: _CalibratorAppLike,
    x: int,
    y: int,
    *,
    hit_test: _app_canvas_interactions._CanvasHitTestFn,
    visible_layout_keys_fn: _app_profile_layout._VisibleLayoutKeysFn,
    image_size: _app_canvas_interactions.ImageSize,
) -> _app_profile_layout.KeyDef | None:
    return _app_canvas_interactions.hit_test_point(
        app,
        x,
        y,
        hit_test=hit_test,
        visible_layout_keys_fn=visible_layout_keys_fn,
        image_size=image_size,
    )
