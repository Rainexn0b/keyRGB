from __future__ import annotations

from keyrgb.gui.perkey.ui.status import (
    action_failed,
    active_profile,
    backdrop_reset,
    backdrop_reset_failed,
    backdrop_update_failed,
    backdrop_updated,
    calibrator_failed,
    calibrator_started,
    cleared_all_keys,
    filled_all_keys_rgb,
    hardware_write_paused,
    keymap_reloaded,
    no_keymap_found,
    no_keymap_found_initial,
    reset_lightbar_overlay,
    reset_overlay_tweaks_for_key,
    reset_overlay_tweaks_global,
    saved_all_keys_rgb,
    saved_key_rgb,
    saved_lightbar_overlay,
    saved_overlay_tweaks_for_key,
    saved_overlay_tweaks_global,
    saved_profile,
    selected_mapped,
    selected_unmapped,
    set_status,
)


class DummyLabel:
    def __init__(self):
        self.text = None

    def config(self, *, text: str) -> None:
        self.text = text


class DummyUnsavedLabel(DummyLabel):
    pass


class DummyEditor:
    def __init__(self):
        self.status_label = DummyLabel()


def _dirty_capable_editor() -> DummyEditor:
    from types import SimpleNamespace

    editor = SimpleNamespace(
        status_label=DummyLabel(),
        _unsaved_label=DummyUnsavedLabel(),
        colors={(0, 0): (1, 2, 3)},
        keymap={},
        layout_tweaks={},
        per_key_layout_tweaks={},
        layout_slot_overrides={},
        lightbar_overlay={},
        secondary_lighting=None,
        _physical_layout="us",
        _layout_legend_pack="default",
    )
    return editor  # type: ignore[return-value]


def test_set_status_sets_label_text() -> None:
    ed = DummyEditor()
    set_status(ed, "hello")
    assert ed.status_label.text == "hello"


def test_set_status_refreshes_unsaved_indicator_saved() -> None:
    from keyrgb.gui.perkey.editor_support import dirty_state

    ed = _dirty_capable_editor()
    dirty_state.mark_saved(ed)
    assert ed._unsaved_label.text == "Saved"
    set_status(ed, "hello")
    assert ed.status_label.text == "hello"
    assert ed._unsaved_label.text == "Saved"


def test_set_status_refreshes_unsaved_indicator_dirty() -> None:
    from keyrgb.gui.perkey.editor_support import dirty_state

    ed = _dirty_capable_editor()
    dirty_state.mark_saved(ed)
    ed.colors[(0, 0)] = (9, 9, 9)
    set_status(ed, "Filled all keys = RGB(9,9,9)")
    assert ed.status_label.text == "Filled all keys = RGB(9,9,9)"
    assert ed._unsaved_label.text == "\u25cf Unsaved"


def test_set_status_tolerates_missing_unsaved_label() -> None:
    ed = DummyEditor()
    set_status(ed, "hello")
    assert ed.status_label.text == "hello"
    set_status(object(), "hello")


def test_set_status_tolerates_missing_status_label_but_refreshes_unsaved() -> None:
    from types import SimpleNamespace

    from keyrgb.gui.perkey.editor_support import dirty_state

    label = DummyUnsavedLabel()
    ed = SimpleNamespace(_unsaved_label=label)
    dirty_state.mark_saved(ed)
    set_status(ed, "hello")
    assert label.text == "Saved"


def test_messages_match_existing_strings() -> None:
    assert no_keymap_found_initial() == "No keymap found — click '2. Keymap Calibrator'"
    assert no_keymap_found() == "No keymap found — run Keymap Calibrator"
    assert keymap_reloaded() == "Saved keymap reloaded"

    assert selected_unmapped("K") == "Selected K (unmapped) — run Keymap Calibrator"
    assert selected_mapped("K", 1, 2) == "Selected K -> 1,2"
    assert selected_mapped("K", 1, 2, 3) == "Selected K -> 1,2 (+2 more)"

    assert saved_overlay_tweaks_for_key("K") == "Saved overlay tweaks for K"
    assert saved_overlay_tweaks_global() == "Saved global overlay alignment tweaks"
    assert saved_lightbar_overlay() == "Saved lightbar placement"
    assert reset_overlay_tweaks_for_key("K") == "Reset overlay tweaks for K"
    assert reset_overlay_tweaks_global() == "Reset global overlay alignment tweaks"
    assert reset_lightbar_overlay() == "Reset lightbar placement"

    assert calibrator_started() == "Calibrator started — map keys then Save"
    assert "Failed to start calibrator" in calibrator_failed()
    assert "Try:" in calibrator_failed()

    assert saved_all_keys_rgb(1, 2, 3) == "Saved all keys = RGB(1,2,3)"
    assert saved_key_rgb("K", 1, 2, 3) == "Saved K = RGB(1,2,3)"

    assert backdrop_updated() == "Backdrop updated"
    assert "Failed to set backdrop" in backdrop_update_failed()
    assert "Try:" in backdrop_update_failed()
    assert backdrop_reset() == "Backdrop reset"
    assert "Failed to reset backdrop" in backdrop_reset_failed()
    assert "Try:" in backdrop_reset_failed()

    assert filled_all_keys_rgb(1, 2, 3) == "Filled all keys = RGB(1,2,3)"
    assert cleared_all_keys() == "Cleared all keys"

    assert active_profile("p") == "Active lighting profile: p"
    assert saved_profile("p") == "Saved lighting profile: p"


def test_action_failed_includes_next_steps() -> None:
    msg = action_failed("do something")
    assert msg.startswith("Failed to do something — ")
    assert "Try:" in msg


def test_hardware_write_paused_is_actionable() -> None:
    msg = hardware_write_paused()
    assert "Keyboard" in msg
    assert "Try:" in msg
