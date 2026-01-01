from __future__ import annotations

from typing import Any, Optional


def compute_power_source_policy(
    *,
    on_ac: bool,
    ac_enabled: bool,
    battery_enabled: bool,
    ac_brightness_override: Any,
    battery_brightness_override: Any,
) -> tuple[bool, Optional[int]]:
    """Compute desired on/off + optional brightness override for current power source.

    Returns:
        (desired_enabled, desired_brightness_override)

    Notes:
        - If no brightness override is configured (or parsing fails), returns None for brightness.
        - Brightness is clamped to [0, 50].
    """

    desired_enabled = bool(ac_enabled) if bool(on_ac) else bool(battery_enabled)

    raw = ac_brightness_override if bool(on_ac) else battery_brightness_override
    if raw is None:
        return desired_enabled, None

    try:
        val = int(raw)
    except Exception:
        try:
            val = int(float(raw))
        except Exception:
            return desired_enabled, None

    return desired_enabled, max(0, min(50, int(val)))
