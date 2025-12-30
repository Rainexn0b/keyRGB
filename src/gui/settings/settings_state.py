from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def clamp_brightness(value: int) -> int:
    return max(0, min(50, int(value)))


def _safe_bool(obj: Any, name: str, default: bool) -> bool:
    try:
        return bool(getattr(obj, name, default))
    except Exception:
        return bool(default)


def _safe_int(obj: Any, name: str, default: int) -> int:
    try:
        return int(getattr(obj, name, default) or 0)
    except Exception:
        return int(default)


def _safe_optional_int(obj: Any, name: str) -> int | None:
    try:
        value = getattr(obj, name, None)
    except Exception:
        return None
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class SettingsValues:
    power_management_enabled: bool
    power_off_on_suspend: bool
    power_off_on_lid_close: bool
    power_restore_on_resume: bool
    power_restore_on_lid_open: bool

    autostart: bool

    ac_lighting_enabled: bool
    battery_lighting_enabled: bool
    ac_lighting_brightness: int
    battery_lighting_brightness: int

    os_autostart_enabled: bool


def load_settings_values(*, config: Any, os_autostart_enabled: bool) -> SettingsValues:
    """Best-effort load of GUI settings from a Config-like object.

    This is intentionally pure (no Tk, no filesystem) and defensive.
    """

    base_brightness = _safe_int(config, "brightness", 25)

    bs_enabled = _safe_bool(config, "battery_saver_enabled", False)
    bs_brightness = _safe_int(config, "battery_saver_brightness", 25)

    ac_override = _safe_optional_int(config, "ac_lighting_brightness")
    batt_override = _safe_optional_int(config, "battery_lighting_brightness")

    ac_brightness = ac_override if ac_override is not None else base_brightness

    if batt_override is not None:
        batt_brightness = batt_override
    else:
        batt_brightness = bs_brightness if bs_enabled else base_brightness

    return SettingsValues(
        power_management_enabled=_safe_bool(config, "power_management_enabled", True),
        power_off_on_suspend=_safe_bool(config, "power_off_on_suspend", True),
        power_off_on_lid_close=_safe_bool(config, "power_off_on_lid_close", True),
        power_restore_on_resume=_safe_bool(config, "power_restore_on_resume", True),
        power_restore_on_lid_open=_safe_bool(config, "power_restore_on_lid_open", True),
        autostart=_safe_bool(config, "autostart", True),
        ac_lighting_enabled=_safe_bool(config, "ac_lighting_enabled", True),
        battery_lighting_enabled=_safe_bool(config, "battery_lighting_enabled", True),
        ac_lighting_brightness=clamp_brightness(ac_brightness),
        battery_lighting_brightness=clamp_brightness(batt_brightness),
        os_autostart_enabled=bool(os_autostart_enabled),
    )


def apply_settings_values_to_config(*, config: Any, values: SettingsValues) -> None:
    """Apply GUI settings back onto a Config-like object."""

    config.power_management_enabled = bool(values.power_management_enabled)
    config.power_off_on_suspend = bool(values.power_off_on_suspend)
    config.power_off_on_lid_close = bool(values.power_off_on_lid_close)
    config.power_restore_on_resume = bool(values.power_restore_on_resume)
    config.power_restore_on_lid_open = bool(values.power_restore_on_lid_open)

    config.autostart = bool(values.autostart)

    config.ac_lighting_enabled = bool(values.ac_lighting_enabled)
    config.battery_lighting_enabled = bool(values.battery_lighting_enabled)
    config.ac_lighting_brightness = clamp_brightness(values.ac_lighting_brightness)
    config.battery_lighting_brightness = clamp_brightness(values.battery_lighting_brightness)
