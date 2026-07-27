"""Unit coverage for per-key ui.selection identity helpers."""

from __future__ import annotations

from types import SimpleNamespace

from src.gui.perkey.ui import selection as ui_sel


def test_lookup_helpers_handle_missing_attrs() -> None:
    assert ui_sel._key_id_for_slot_id_or_none(object(), None) is None
    assert ui_sel._key_id_for_slot_id_or_none(object(), "slot") is None
    assert ui_sel._slot_id_for_key_id_or_none(object(), None) is None
    assert ui_sel._slot_id_for_key_id_or_none(object(), "key") is None

    editor = SimpleNamespace(
        _key_id_for_slot_id=lambda sid: "esc" if sid == "slot_esc" else None,
        _slot_id_for_key_id=lambda kid: "slot_esc" if kid == "esc" else None,
    )
    assert ui_sel._key_id_for_slot_id_or_none(editor, "slot_esc") == "esc"
    assert ui_sel._slot_id_for_key_id_or_none(editor, "esc") == "slot_esc"

    # non-callable attrs
    assert ui_sel._key_id_for_slot_id_or_none(SimpleNamespace(_key_id_for_slot_id="x"), "s") is None
    assert ui_sel._slot_id_for_key_id_or_none(SimpleNamespace(_slot_id_for_key_id="x"), "k") is None


def test_select_helpers_and_visible_identity() -> None:
    selected_slots: list[str] = []
    selected_keys: list[str] = []

    editor = SimpleNamespace(
        select_slot_id=lambda sid: selected_slots.append(sid),
        select_key_id=lambda kid: selected_keys.append(kid),
        _key_id_for_slot_id=lambda sid: "esc" if sid == "slot_esc" else None,
        _slot_id_for_key_id=lambda kid: "slot_esc" if kid == "esc" else None,
    )

    assert ui_sel._select_slot_id_if_present(object(), "x") is False
    assert ui_sel._select_key_id_if_present(object(), "x") is False
    assert ui_sel._select_slot_id_if_present(SimpleNamespace(select_slot_id="no"), "x") is False
    assert ui_sel._select_key_id_if_present(SimpleNamespace(select_key_id="no"), "x") is False

    assert ui_sel.select_visible_identity(editor, slot_id="slot_esc") is True
    assert selected_slots == ["slot_esc"]

    selected_slots.clear()
    # key only -> resolve slot then select slot
    assert ui_sel.select_visible_identity(editor, key_id="esc") is True
    assert selected_slots == ["slot_esc"]

    # no slot selector: fall back to key selector after resolving key from slot
    key_only = SimpleNamespace(
        select_key_id=lambda kid: selected_keys.append(kid),
        _key_id_for_slot_id=lambda sid: "a" if sid == "slot_a" else None,
        _slot_id_for_key_id=lambda _kid: None,
    )
    selected_keys.clear()
    assert ui_sel.select_visible_identity(key_only, slot_id="slot_a") is True
    assert selected_keys == ["a"]

    assert ui_sel.select_visible_identity(object(), slot_id=None, key_id=None) is False
