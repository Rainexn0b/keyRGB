"""Direct unit coverage for per-key editor_support.selection helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.gui.perkey.editor_support import selection as sel


def _key(key_id: str, slot_id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(key_id=key_id, slot_id=slot_id or key_id)


def test_visible_key_maps_and_lookups() -> None:
    keys = [_key("esc", "slot_esc"), _key("a", "slot_a"), SimpleNamespace(key_id="space", slot_id=None)]
    app = SimpleNamespace(_get_visible_layout_keys=lambda: keys)

    by_key, by_slot = sel.visible_key_maps(app)
    assert set(by_key) == {"esc", "a", "space"}
    assert set(by_slot) == {"slot_esc", "slot_a"}

    lookup = SimpleNamespace(_visible_key_maps=lambda: (by_key, by_slot))
    assert sel.visible_key_for_key_id(lookup, None) is None
    assert sel.visible_key_for_key_id(lookup, "esc") is keys[0]
    assert sel.visible_key_for_slot_id(lookup, None) is None
    assert sel.visible_key_for_slot_id(lookup, "slot_a") is keys[1]

    id_lookup = SimpleNamespace(_visible_key_for_key_id=lambda kid: by_key.get(str(kid)))
    assert sel.slot_id_for_key_id(id_lookup, "esc") == "slot_esc"
    assert sel.slot_id_for_key_id(id_lookup, "space") is None
    assert sel.slot_id_for_key_id(id_lookup, "missing") is None

    slot_lookup = SimpleNamespace(_visible_key_for_slot_id=lambda sid: by_slot.get(str(sid)))
    assert sel.key_id_for_slot_id(slot_lookup, "slot_a") == "a"
    assert sel.key_id_for_slot_id(slot_lookup, "missing") is None


def test_clear_and_apply_selection() -> None:
    app = SimpleNamespace(
        selected_key_id="x",
        selected_slot_id="y",
        selected_cells=((1, 1),),
        selected_cell=(1, 1),
        keymap={"esc": ((0, 0), (0, 1))},
        _physical_layout="ansi",
    )
    sel.clear_selection(app)
    assert app.selected_key_id is None
    assert app.selected_slot_id is None
    assert app.selected_cells == ()
    assert app.selected_cell is None

    sel.apply_selection_for_visible_key(app, _key("esc", "slot_esc"))
    assert app.selected_key_id == "esc"
    assert app.selected_slot_id == "slot_esc"
    assert app.selected_cells == ((0, 0), (0, 1))
    assert app.selected_cell is None


def test_selected_display_key_id_and_refresh() -> None:
    app = SimpleNamespace(
        selected_key_id="esc",
        selected_slot_id="slot_esc",
        selected_cells=(),
        selected_cell=None,
        keymap={"esc": ((2, 3),)},
        colors={(2, 3): (9, 8, 7)},
        _physical_layout="ansi",
        _key_id_for_slot_id=lambda sid: "esc" if sid == "slot_esc" else None,
        _selected_display_key_id=lambda: "esc",
    )
    assert sel.selected_display_key_id(app) == "esc"
    app.selected_key_id = None
    assert sel.selected_display_key_id(app) == "esc"
    app.selected_slot_id = None
    assert sel.selected_display_key_id(app) is None

    app.selected_key_id = "esc"
    app.selected_slot_id = "slot_esc"
    sel.refresh_selected_cells(app)
    assert app.selected_cells == ((2, 3),)
    assert app.selected_cell == (2, 3)


def test_finalize_selection_unmapped_and_mapped(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses: list[str] = []
    monkeypatch.setattr(sel, "set_status", lambda _app, msg: statuses.append(msg))
    monkeypatch.setattr(sel, "selected_unmapped", lambda key: f"unmapped:{key}")
    monkeypatch.setattr(sel, "selected_mapped", lambda key, row, col, n: f"mapped:{key}:{row},{col}:{n}")

    wheel = SimpleNamespace(set_color=MagicMock())
    canvas = SimpleNamespace(redraw=MagicMock())
    overlay = SimpleNamespace(sync_vars_from_scope=MagicMock())

    app = SimpleNamespace(
        selected_key_id="esc",
        selected_slot_id="slot_esc",
        selected_cells=(),
        selected_cell=None,
        overlay_scope=SimpleNamespace(get=lambda: "key"),
        overlay_controls=overlay,
        canvas=canvas,
        colors={},
        color_wheel=wheel,
        _last_non_black_color=(10, 20, 30),
        _selected_display_key_id=lambda: "esc",
    )
    sel.finalize_selection(app, "slot_esc")
    overlay.sync_vars_from_scope.assert_called_once()
    assert statuses[-1] == "unmapped:esc"
    canvas.redraw.assert_called()

    # mapped black color uses last non-black
    app.selected_cells = ((0, 0), (0, 1))
    app.colors = {(0, 0): (0, 0, 0), (0, 1): (0, 0, 0)}
    statuses.clear()
    wheel.set_color.reset_mock()
    sel.finalize_selection(app, "slot_esc")
    wheel.set_color.assert_called_with(10, 20, 30)
    assert statuses[-1].startswith("mapped:esc:0,0:2")

    # mapped colored key updates last non-black
    app.colors = {(0, 0): (1, 2, 3)}
    sel.finalize_selection(app, "slot_esc")
    assert app._last_non_black_color == (1, 2, 3)
    wheel.set_color.assert_called_with(1, 2, 3)


def test_select_slot_id_paths() -> None:
    cleared: list[str] = []
    applied: list[object] = []
    finalized: list[str] = []
    canvas = SimpleNamespace(redraw=MagicMock())
    key = _key("esc", "slot_esc")

    app = SimpleNamespace(
        canvas=canvas,
        _visible_key_for_slot_id=lambda sid: key if sid == "slot_esc" else None,
        _clear_selection=lambda: cleared.append("clear"),
        _apply_selection_for_visible_key=lambda k: applied.append(k),
        _finalize_selection=lambda identity: finalized.append(identity),
    )

    sel.select_slot_id(app, "missing")
    assert cleared == ["clear"]
    canvas.redraw.assert_called_once()

    sel.select_slot_id(app, "slot_esc")
    assert applied == [key]
    assert finalized == ["slot_esc"]


def test_get_visible_layout_keys_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = [_key("esc")]
    monkeypatch.setattr(
        sel,
        "get_layout_keys",
        lambda layout, *, legend_pack_id, slot_overrides: (
            sentinel if layout == "ansi" and legend_pack_id == "pack" and slot_overrides == {"esc": {}} else []
        ),
    )
    app = SimpleNamespace(
        _physical_layout="ansi",
        layout_slot_overrides={"esc": {}},
        _resolved_layout_legend_pack_id=lambda: "pack",
    )
    assert sel.get_visible_layout_keys(app) is sentinel
