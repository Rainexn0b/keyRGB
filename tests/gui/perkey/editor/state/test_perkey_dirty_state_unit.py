from __future__ import annotations

from types import SimpleNamespace

from keyrgb.gui.perkey.editor_support.dirty_state import (
    SAVED_TEXT,
    UNSAVED_TEXT,
    confirm_destructive_action,
    is_dirty,
    mark_saved,
    refresh_unsaved_indicator,
    saved_snapshot,
)


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


class _FakeUnsavedLabel:
    def __init__(self, *, fail: bool = False):
        self.text: str | None = None
        self._fail = fail

    def config(self, *, text: str) -> None:
        if self._fail:
            raise RuntimeError("widget destroyed")
        self.text = text


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

    assert (
        confirm_destructive_action(
            editor,
            action="switching profiles",
            save_fn=lambda: (saved.append(True), mark_saved(editor)),
            ask_fn=lambda *_args, **_kwargs: True,
        )
        is True
    )
    assert saved == [True]
    assert is_dirty(editor) is False

    editor.colors[(0, 0)] = (4, 5, 6)
    assert (
        confirm_destructive_action(
            editor,
            action="closing the editor",
            save_fn=lambda: saved.append(False),
            ask_fn=lambda *_args, **_kwargs: None,
        )
        is False
    )


def test_mark_saved_shows_saved_initially() -> None:
    editor = _editor()
    editor._unsaved_label = _FakeUnsavedLabel()
    mark_saved(editor)
    assert is_dirty(editor) is False
    assert editor._unsaved_label.text == SAVED_TEXT
    assert editor._unsaved_label.text == "Saved"


def test_refresh_shows_unsaved_when_dirty() -> None:
    editor = _editor()
    editor._unsaved_label = _FakeUnsavedLabel()
    mark_saved(editor)
    editor.colors[(0, 0)] = (9, 9, 9)
    refresh_unsaved_indicator(editor)
    assert is_dirty(editor) is True
    assert editor._unsaved_label.text == UNSAVED_TEXT
    assert editor._unsaved_label.text == "\u25cf Unsaved"


def test_mark_saved_refreshes_back_to_saved() -> None:
    editor = _editor()
    editor._unsaved_label = _FakeUnsavedLabel()
    mark_saved(editor)
    editor.colors[(0, 0)] = (9, 9, 9)
    refresh_unsaved_indicator(editor)
    assert editor._unsaved_label.text == UNSAVED_TEXT
    mark_saved(editor)
    assert editor._unsaved_label.text == SAVED_TEXT


def test_refresh_tolerates_missing_label() -> None:
    editor = _editor()
    mark_saved(editor)
    refresh_unsaved_indicator(editor)
    refresh_unsaved_indicator(object())


def test_refresh_tolerates_failing_label() -> None:
    editor = _editor()
    editor._unsaved_label = _FakeUnsavedLabel(fail=True)
    mark_saved(editor)
    editor.colors[(0, 0)] = (9, 9, 9)
    refresh_unsaved_indicator(editor)


def test_backdrop_and_power_policy_stay_outside_dirty_snapshot() -> None:
    editor = _editor()
    editor._unsaved_label = _FakeUnsavedLabel()
    mark_saved(editor)
    # Immediate-persistence backdrop state and AC/battery policy are not
    # part of the saved snapshot, so they must never flip the pill.
    editor.backdrop_transparency = 90
    editor._backdrop_mode_var = "custom"
    editor._ac_power_source_profile_var = "gaming"
    editor._battery_power_source_profile_var = "movie"
    assert is_dirty(editor) is False
    refresh_unsaved_indicator(editor)
    assert editor._unsaved_label.text == SAVED_TEXT
