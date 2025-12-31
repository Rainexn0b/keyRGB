from __future__ import annotations

"""Status label helpers for the per-key editor.

Keeps message formatting consistent and keeps UI modules from sprinkling direct
`status_label.config(...)` calls everywhere.
"""

from typing import Any


def set_status(editor: Any, text: str) -> None:
    try:
        editor.status_label.config(text=str(text))
    except Exception:
        return


def _next_steps_for_exception(exc: Exception | None) -> str:
    """Return a short, user-facing next step hint for common failure modes."""

    if exc is None:
        return "Try: open Settings → Diagnostics"

    # Permissions (sysfs, USB, etc.).
    if isinstance(exc, PermissionError):
        return "Try: run KeyRGB with elevated permissions or install udev rules"

    # Generic OS errors.
    if isinstance(exc, OSError):
        errno = getattr(exc, "errno", None)
        if errno in (1, 13):
            return "Try: run KeyRGB with elevated permissions or install udev rules"
        # 16 is commonly "Device or resource busy".
        if errno == 16:
            return "Try: close other RGB apps and unplug/replug the keyboard"

    if isinstance(exc, FileNotFoundError):
        return "Try: check the file/path exists"

    return "Try: open Settings → Diagnostics"


def action_failed(action: str, exc: Exception | None = None, *, extra_hint: str | None = None) -> str:
    hint = _next_steps_for_exception(exc)
    if extra_hint:
        hint = f"{hint}; {extra_hint}"
    return f"Failed to {action} — {hint}"


def no_keymap_found_initial() -> str:
    return "No keymap found — click 'Keymap Calibrator'"


def selected_unmapped(key_id: str) -> str:
    return f"Selected {key_id} (unmapped) — run Keymap Calibrator"


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


def calibrator_failed(exc: Exception | None = None) -> str:
    return action_failed(
        "start calibrator",
        exc,
        extra_hint="run keyrgb-calibrate in a terminal to see the error",
    )


def keymap_reloaded() -> str:
    return "Keymap reloaded"


def no_keymap_found() -> str:
    return "No keymap found — run Keymap Calibrator"


def saved_all_keys_rgb(r: int, g: int, b: int) -> str:
    return f"Saved all keys = RGB({r},{g},{b})"


def saved_key_rgb(key_id: str, r: int, g: int, b: int) -> str:
    return f"Saved {key_id} = RGB({r},{g},{b})"


def backdrop_updated() -> str:
    return "Backdrop updated"


def backdrop_update_failed(exc: Exception | None = None) -> str:
    return action_failed("set backdrop", exc, extra_hint="choose a readable image file")


def backdrop_reset() -> str:
    return "Backdrop reset"


def backdrop_reset_failed(exc: Exception | None = None) -> str:
    return action_failed("reset backdrop", exc)


def hardware_write_paused() -> str:
    return "Keyboard busy/unavailable — Try: close other RGB apps and unplug/replug"


def filled_all_keys_rgb(r: int, g: int, b: int) -> str:
    return f"Filled all keys = RGB({r},{g},{b})"


def cleared_all_keys() -> str:
    return "Cleared all keys"


def active_profile(name: str) -> str:
    return f"Active profile: {name}"


def saved_profile(name: str) -> str:
    return f"Saved profile: {name}"


def sample_tool_pick_a_key() -> str:
    return "Sample tool: click a key to pick its color"


def sample_tool_sampled_color(key_id: str, r: int, g: int, b: int) -> str:
    return f"Sampled {key_id} = RGB({r},{g},{b}) — click keys to apply"


def sample_tool_unmapped_key(key_id: str) -> str:
    return f"{key_id} is unmapped — cannot sample/apply"
