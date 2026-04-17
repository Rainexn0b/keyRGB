from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, TypeVar

from src.core.resources.layouts.catalog import VALID_LAYOUT_IDS
from src.core.utils.safe_attrs import safe_int_attr


logger = logging.getLogger(__name__)

_SETTINGS_ATTR_READ_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_SETTINGS_INT_COERCE_ERRORS = (RuntimeError,)
_SETTINGS_BOOL_COERCE_ERRORS = (RuntimeError, TypeError, ValueError)
_SETTINGS_SAFE_INT_ERRORS = (AttributeError, OverflowError, RuntimeError, TypeError, ValueError)

_DefaultT = TypeVar("_DefaultT")


class _SettingsConfigLike(Protocol):
    def __getattribute__(self, name: str) -> object: ...

    def __setattr__(self, name: str, value: object) -> None: ...


def clamp_brightness(value: int) -> int:
    return max(0, min(50, int(value)))


def _safe_getattr_or_default(obj: object, name: str, default: _DefaultT) -> object | _DefaultT:
    try:
        return getattr(obj, name, default)
    except _SETTINGS_ATTR_READ_ERRORS:
        logger.exception("Failed reading settings attribute '%s'", name)
        return default


def _coerce_int_or_fallback(value: object, *, fallback: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    except _SETTINGS_INT_COERCE_ERRORS:
        logger.exception("Failed coercing settings value to int")
        return fallback


def clamp_nonzero_brightness(value: int, *, default: int = 5) -> int:
    v = _coerce_int_or_fallback(value, fallback=None)
    if v is None:
        fallback_value = _coerce_int_or_fallback(default, fallback=5)
        v = 5 if fallback_value is None else fallback_value
    return max(1, min(50, v))


def _safe_bool(obj: object, name: str, default: bool) -> bool:
    value = _safe_getattr_or_default(obj, name, default)
    try:
        return bool(value)
    except _SETTINGS_BOOL_COERCE_ERRORS:
        logger.exception("Failed coercing settings attribute '%s' to bool", name)
        return bool(default)


def _safe_int(obj: object, name: str, default: int) -> int:
    default_value = _coerce_int_or_fallback(default, fallback=0)
    safe_default = 0 if default_value is None else default_value
    try:
        return safe_int_attr(obj, name, default=safe_default)
    except _SETTINGS_SAFE_INT_ERRORS:
        logger.exception("Failed reading settings integer attribute '%s'", name)
        return safe_default


def _safe_optional_int(obj: object, name: str) -> int | None:
    value = _safe_getattr_or_default(obj, name, None)
    if value is None:
        return None
    return _coerce_int_or_fallback(value, fallback=None)


@dataclass(frozen=True, slots=True)
class SettingsValues:
    power_management_enabled: bool
    power_off_on_suspend: bool
    power_off_on_lid_close: bool
    power_restore_on_resume: bool
    power_restore_on_lid_open: bool

    autostart: bool
    experimental_backends_enabled: bool

    ac_lighting_enabled: bool
    battery_lighting_enabled: bool
    ac_lighting_brightness: int
    battery_lighting_brightness: int

    screen_dim_sync_enabled: bool
    # 'off' | 'temp'
    screen_dim_sync_mode: str
    # 1-50 (same brightness scale as `brightness`). Only used when mode == 'temp'.
    screen_dim_temp_brightness: int

    os_autostart_enabled: bool

    # Physical keyboard layout for per-key editor / calibrator overlay.
    # Canonical values come from src.core.resources.layouts.catalog.
    physical_layout: str = "auto"


def load_settings_values(*, config: _SettingsConfigLike, os_autostart_enabled: bool) -> SettingsValues:
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

    power_management_enabled = _safe_bool(
        config,
        "power_management_enabled",
        _safe_bool(config, "management_enabled", True),
    )

    return SettingsValues(
        power_management_enabled=power_management_enabled,
        power_off_on_suspend=_safe_bool(config, "power_off_on_suspend", True),
        power_off_on_lid_close=_safe_bool(config, "power_off_on_lid_close", True),
        power_restore_on_resume=_safe_bool(config, "power_restore_on_resume", True),
        power_restore_on_lid_open=_safe_bool(config, "power_restore_on_lid_open", True),
        autostart=_safe_bool(config, "autostart", True),
        experimental_backends_enabled=_safe_bool(config, "experimental_backends_enabled", False),
        ac_lighting_enabled=_safe_bool(config, "ac_lighting_enabled", True),
        battery_lighting_enabled=_safe_bool(config, "battery_lighting_enabled", True),
        ac_lighting_brightness=clamp_brightness(ac_brightness),
        battery_lighting_brightness=clamp_brightness(batt_brightness),
        screen_dim_sync_enabled=_safe_bool(config, "screen_dim_sync_enabled", True),
        screen_dim_sync_mode=str(getattr(config, "screen_dim_sync_mode", "off") or "off").strip().lower(),
        screen_dim_temp_brightness=clamp_nonzero_brightness(
            _safe_int(config, "screen_dim_temp_brightness", 5),
            default=5,
        ),
        os_autostart_enabled=bool(os_autostart_enabled),
        physical_layout=str(getattr(config, "physical_layout", "auto") or "auto").strip().lower(),
    )


def apply_settings_values_to_config(*, config: _SettingsConfigLike, values: SettingsValues) -> None:
    """Apply GUI settings back onto a Config-like object."""

    config.power_management_enabled = bool(values.power_management_enabled)
    config.management_enabled = bool(values.power_management_enabled)
    config.power_off_on_suspend = bool(values.power_off_on_suspend)
    config.power_off_on_lid_close = bool(values.power_off_on_lid_close)
    config.power_restore_on_resume = bool(values.power_restore_on_resume)
    config.power_restore_on_lid_open = bool(values.power_restore_on_lid_open)

    config.autostart = bool(values.autostart)
    config.experimental_backends_enabled = bool(values.experimental_backends_enabled)

    config.ac_lighting_enabled = bool(values.ac_lighting_enabled)
    config.battery_lighting_enabled = bool(values.battery_lighting_enabled)
    config.ac_lighting_brightness = clamp_brightness(values.ac_lighting_brightness)
    config.battery_lighting_brightness = clamp_brightness(values.battery_lighting_brightness)

    config.screen_dim_sync_enabled = bool(values.screen_dim_sync_enabled)

    mode = str(values.screen_dim_sync_mode or "off").strip().lower()
    config.screen_dim_sync_mode = mode if mode in {"off", "temp"} else "off"

    config.screen_dim_temp_brightness = clamp_nonzero_brightness(values.screen_dim_temp_brightness, default=5)

    layout = str(values.physical_layout or "auto").strip().lower()
    config.physical_layout = layout if layout in VALID_LAYOUT_IDS else "auto"
