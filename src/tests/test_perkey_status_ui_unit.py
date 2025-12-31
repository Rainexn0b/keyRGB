from __future__ import annotations

from src.gui.perkey.ui.status import (
    active_profile,
    action_failed,
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
    reset_overlay_tweaks_for_key,
    reset_overlay_tweaks_global,
    saved_all_keys_rgb,
    saved_key_rgb,
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


class DummyEditor:
    def __init__(self):
        self.status_label = DummyLabel()


def test_set_status_sets_label_text() -> None:
    ed = DummyEditor()
    set_status(ed, "hello")
    assert ed.status_label.text == "hello"


def test_messages_match_existing_strings() -> None:
    assert no_keymap_found_initial() == "No keymap found — click 'Keymap Calibrator'"
    assert no_keymap_found() == "No keymap found — run Keymap Calibrator"
    assert keymap_reloaded() == "Keymap reloaded"

    assert selected_unmapped("K") == "Selected K (unmapped) — run Keymap Calibrator"
    assert selected_mapped("K", 1, 2) == "Selected K -> 1,2"

    assert saved_overlay_tweaks_for_key("K") == "Saved overlay tweaks for K"
    assert saved_overlay_tweaks_global() == "Saved global overlay alignment tweaks"
    assert reset_overlay_tweaks_for_key("K") == "Reset overlay tweaks for K"
    assert reset_overlay_tweaks_global() == "Reset global overlay alignment tweaks"

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

    assert active_profile("p") == "Active profile: p"
    assert saved_profile("p") == "Saved profile: p"


def test_action_failed_includes_next_steps() -> None:
    msg = action_failed("do something")
    assert msg.startswith("Failed to do something — ")
    assert "Try:" in msg


def test_hardware_write_paused_is_actionable() -> None:
    msg = hardware_write_paused()
    assert "Keyboard" in msg
    assert "Try:" in msg
