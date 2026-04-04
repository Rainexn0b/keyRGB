from __future__ import annotations
from typing import Any

from src.core.resources.layout import get_layout_keys

from ..profile_management import keymap_cells_for, representative_cell
from ..ui.status import selected_mapped, selected_unmapped, set_status


def get_visible_layout_keys(app: Any):
    return get_layout_keys(
        app._physical_layout,
        legend_pack_id=app._resolved_layout_legend_pack_id(),
        slot_overrides=app.layout_slot_overrides,
    )


def visible_key_maps(app: Any) -> tuple[dict[str, object], dict[str, object]]:
    visible_keys = app._get_visible_layout_keys()
    by_key_id = {str(key.key_id): key for key in visible_keys}
    by_slot_id = {str(key.slot_id): key for key in visible_keys if key.slot_id}
    return by_key_id, by_slot_id


def visible_key_for_key_id(app: Any, key_id: str | None):
    if not key_id:
        return None
    by_key_id, _by_slot_id = app._visible_key_maps()
    return by_key_id.get(str(key_id))


def visible_key_for_slot_id(app: Any, slot_id: str | None):
    if not slot_id:
        return None
    _by_key_id, by_slot_id = app._visible_key_maps()
    return by_slot_id.get(str(slot_id))


def slot_id_for_key_id(app: Any, key_id: str | None) -> str | None:
    key = app._visible_key_for_key_id(key_id)
    if key is None or not key.slot_id:
        return None
    return str(key.slot_id)


def key_id_for_slot_id(app: Any, slot_id: str | None) -> str | None:
    key = app._visible_key_for_slot_id(slot_id)
    if key is None:
        return None
    return str(key.key_id)


def clear_selection(app: Any) -> None:
    app.selected_key_id = None
    app.selected_slot_id = None
    app.selected_cells = ()
    app.selected_cell = None


def apply_selection_for_visible_key(app: Any, key: Any) -> None:
    app.selected_key_id = str(key.key_id)
    app.selected_slot_id = str(key.slot_id or key.key_id)
    app.selected_cells = keymap_cells_for(
        app.keymap,
        app.selected_key_id,
        slot_id=app.selected_slot_id,
        physical_layout=app._physical_layout,
    )
    app.selected_cell = None


def selected_display_key_id(app: Any) -> str | None:
    if app.selected_key_id:
        return str(app.selected_key_id)
    if app.selected_slot_id:
        return app._key_id_for_slot_id(app.selected_slot_id)
    return None


def refresh_selected_cells(app: Any) -> None:
    app.selected_cells = keymap_cells_for(
        app.keymap,
        app._selected_display_key_id(),
        slot_id=app.selected_slot_id,
        physical_layout=app._physical_layout,
    )
    app.selected_cell = representative_cell(app.selected_cells, colors=app.colors)


def finalize_selection(app: Any, requested_identity: str) -> None:
    display_key_id = app._selected_display_key_id() or str(requested_identity)

    if app.overlay_scope.get() == "key":
        app.overlay_controls.sync_vars_from_scope()

    if not app.selected_cells:
        set_status(app, selected_unmapped(display_key_id))
        app.canvas.redraw()
        return

    row, col = app.selected_cells[0]
    display_cell = representative_cell(app.selected_cells, colors=app.colors)
    color = app.colors.get(display_cell, (0, 0, 0)) if display_cell is not None else (0, 0, 0)

    if tuple(color) == (0, 0, 0):
        app.color_wheel.set_color(*app._last_non_black_color)
    else:
        app._last_non_black_color = (int(color[0]), int(color[1]), int(color[2]))
        app.color_wheel.set_color(*color)

    set_status(app, selected_mapped(display_key_id, row, col, len(app.selected_cells)))
    app.canvas.redraw()


def select_slot_id(app: Any, slot_id: str) -> None:
    key = app._visible_key_for_slot_id(slot_id)
    if key is None:
        app._clear_selection()
        app.canvas.redraw()
        return

    app._apply_selection_for_visible_key(key)
    app._finalize_selection(str(slot_id))
