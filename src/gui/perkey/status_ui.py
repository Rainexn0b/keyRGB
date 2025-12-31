from __future__ import annotations

"""Status label helpers for the per-key editor.

Keeps message formatting consistent and keeps UI modules from sprinkling direct
`status_label.config(...)` calls everywhere.

No UX change: messages are identical to the previous inline strings.
"""

from typing import Any


def set_status(editor: Any, text: str) -> None:
    try:
        editor.status_label.config(text=str(text))
    except Exception:
        return


def no_keymap_found_initial() -> str:
    return "No keymap found — click 'Run Keymap Calibrator'"


def selected_unmapped(key_id: str) -> str:
    return f"Selected {key_id} (unmapped) — run keymap calibrator"


def selected_mapped(key_id: str, row: int, col: int) -> str:
    return f"Selected {key_id} -> {row},{col}"


def saved_overlay_tweaks_for_key(key_id: str) -> str:
    return f"Saved overlay tweaks for {key_id}"


def saved_overlay_tweaks_global() -> str:
    return "Saved global overlay alignment tweaks"


def reset_overlay_tweaks_for_key(key_id: str) -> str:
    return f"Reset overlay tweaks for {key_id}"


def reset_overlay_tweaks_global() -> str:
    return "Reset global overlay alignment tweaks"


def auto_synced_overlay_tweaks() -> str:
    return "Auto-synced overlay tweaks"


def calibrator_started() -> str:
    return "Calibrator started — map keys then Save"


def calibrator_failed() -> str:
    return "Failed to start calibrator"


def keymap_reloaded() -> str:
    return "Keymap reloaded"


def no_keymap_found() -> str:
    return "No keymap found — run keymap calibrator"


def saved_all_keys_rgb(r: int, g: int, b: int) -> str:
    return f"Saved all keys = RGB({r},{g},{b})"


def saved_key_rgb(key_id: str, r: int, g: int, b: int) -> str:
    return f"Saved {key_id} = RGB({r},{g},{b})"


def backdrop_updated() -> str:
    return "Backdrop updated"


def backdrop_update_failed() -> str:
    return "Failed to set backdrop"


def backdrop_reset() -> str:
    return "Backdrop reset"


def backdrop_reset_failed() -> str:
    return "Failed to reset backdrop"


def filled_all_keys_rgb(r: int, g: int, b: int) -> str:
    return f"Filled all keys = RGB({r},{g},{b})"


def cleared_all_keys() -> str:
    return "Cleared all keys"


def active_profile(name: str) -> str:
    return f"Active profile: {name}"


def saved_profile(name: str) -> str:
    return f"Saved profile: {name}"
