from __future__ import annotations

from types import SimpleNamespace

import src.gui.perkey.editor as perkey_editor
from src.gui.perkey.editor import PerKeyEditor


def test_select_slot_id_applies_visible_key_and_finalizes_selection() -> None:
    applied: list[object] = []
    finalized: list[str] = []
    key = SimpleNamespace(key_id="K1", slot_id="slot_k1")
    editor = SimpleNamespace(
        _visible_key_for_slot_id=lambda slot_id: key if slot_id == "slot_k1" else None,
        _apply_selection_for_visible_key=lambda resolved_key: applied.append(resolved_key),
        _finalize_selection=lambda identity: finalized.append(str(identity)),
    )

    PerKeyEditor.select_slot_id(editor, "slot_k1")

    assert applied == [key]
    assert finalized == ["slot_k1"]


def test_select_slot_id_clears_selection_and_redraws_when_slot_is_unknown() -> None:
    cleared: list[bool] = []
    redraws: list[bool] = []
    editor = SimpleNamespace(
        _visible_key_for_slot_id=lambda _slot_id: None,
        _clear_selection=lambda: cleared.append(True),
        canvas=SimpleNamespace(redraw=lambda: redraws.append(True)),
    )

    PerKeyEditor.select_slot_id(editor, "missing")

    assert cleared == [True]
    assert redraws == [True]


def test_on_slot_clicked_delegates_to_slot_click_helper(monkeypatch) -> None:
    helper_calls: list[tuple[str, int, int]] = []

    def fake_on_slot_clicked_ui(editor, slot_id: str, *, num_rows: int, num_cols: int) -> None:
        helper_calls.append((str(slot_id), int(num_rows), int(num_cols)))

    monkeypatch.setattr(perkey_editor, "on_slot_clicked_ui", fake_on_slot_clicked_ui)

    editor = SimpleNamespace()

    PerKeyEditor.on_slot_clicked(editor, "slot_k1")

    assert helper_calls == [("slot_k1", perkey_editor.NUM_ROWS, perkey_editor.NUM_COLS)]


def test_editor_exposes_slot_first_click_and_selection_api_only() -> None:
    assert hasattr(PerKeyEditor, "select_slot_id")
    assert hasattr(PerKeyEditor, "on_slot_clicked")
    assert not hasattr(PerKeyEditor, "select_key_id")
    assert not hasattr(PerKeyEditor, "on_key_clicked")
