from __future__ import annotations

from types import SimpleNamespace

from src.gui.perkey.editor_support.dirty_state import confirm_destructive_action, is_dirty, mark_saved, saved_snapshot


def _editor() -> SimpleNamespace:
    return SimpleNamespace(
        colors={(0, 0): (1, 2, 3)},
        keymap={"A": ((0, 0),)},
        layout_tweaks={"dx": 0.0},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        lightbar_overlay={"visible": True},
        secondary_lighting={"areas": {"mouse": {"enabled": True}}},
        _physical_layout="us",
        _layout_legend_pack="default",
        root=object(),
    )


def test_snapshot_includes_keyboard_layout_overlay_and_secondary_state() -> None:
    editor = _editor()
    mark_saved(editor)
    assert is_dirty(editor) is False

    editor.secondary_lighting["areas"]["mouse"]["enabled"] = False
    assert is_dirty(editor) is True


def test_snapshot_is_order_independent() -> None:
    first = _editor()
    second = _editor()
    second.colors = {(0, 0): (1, 2, 3)}
    second.keymap = {"A": ((0, 0),)}
    assert saved_snapshot(first) == saved_snapshot(second)


def test_confirm_destructive_action_saves_on_yes_and_cancels_on_cancel() -> None:
    editor = _editor()
    mark_saved(editor)
    editor.colors[(0, 0)] = (9, 9, 9)
    saved: list[bool] = []

    assert confirm_destructive_action(
        editor,
        action="switching profiles",
        save_fn=lambda: (saved.append(True), mark_saved(editor)),
        ask_fn=lambda *_args, **_kwargs: True,
    ) is True
    assert saved == [True]
    assert is_dirty(editor) is False

    editor.colors[(0, 0)] = (4, 5, 6)
    assert confirm_destructive_action(
        editor,
        action="closing the editor",
        save_fn=lambda: saved.append(False),
        ask_fn=lambda *_args, **_kwargs: None,
    ) is False
