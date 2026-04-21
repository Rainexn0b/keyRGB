from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from src.core.config._settings_view import ConfigSettingsView
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


@dataclass(frozen=True, slots=True)
class _SettingsReader:
    config: _SettingsConfigLike
    settings_view: ConfigSettingsView | None

    def read_bool(self, key: str, *, default: bool, fallback_attr: str | None = None) -> bool:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return _read_view_bool(
                self.settings_view,
                key,
                default=default,
                fallback_obj=self.config,
                fallback_attr=attr,
            )
        return _safe_bool(self.config, attr, default)

    def read_int(self, key: str, *, default: int, fallback_attr: str | None = None) -> int:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return _read_view_int(
                self.settings_view,
                key,
                default=default,
                fallback_obj=self.config,
                fallback_attr=attr,
            )
        return _safe_int(self.config, attr, default)

    def read_optional_int(self, key: str, *, fallback_attr: str | None = None) -> int | None:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return _read_view_optional_int(
                self.settings_view,
                key,
                fallback_obj=self.config,
                fallback_attr=attr,
            )
        return _safe_optional_int(self.config, attr)

    def read_normalized_str(self, key: str, *, default: str, fallback_attr: str | None = None) -> str:
        attr = fallback_attr or key
        if self.settings_view is not None:
            return _read_view_normalized_str(
                self.settings_view,
                key,
                default=default,
                fallback_obj=self.config,
                fallback_attr=attr,
            )
        return _safe_normalized_str(self.config, attr, default)


def _settings_view_from_config(config: _SettingsConfigLike) -> ConfigSettingsView | None:
    if hasattr(config, "settings_view"):
        try:
            view_getter = getattr(config, "settings_view")
            if callable(view_getter):
                view = view_getter()
                if isinstance(view, ConfigSettingsView):
                    return view
        except _SETTINGS_ATTR_READ_ERRORS:
            logger.exception("Failed reading typed settings view from config")

    if hasattr(config, "settings"):
        try:
            raw_settings = getattr(config, "settings")
        except _SETTINGS_ATTR_READ_ERRORS:
            logger.exception("Failed reading settings mapping from config")
            return None
        if isinstance(raw_settings, ConfigSettingsView):
            return raw_settings
        if isinstance(raw_settings, Mapping):
            return ConfigSettingsView.from_mapping(raw_settings)
    return None


def _read_view_bool(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    default: bool,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> bool:
    if key in settings_view:
        return settings_view.read_bool(key, default)
    if fallback_obj is not None and fallback_attr is not None:
        return _safe_bool(fallback_obj, fallback_attr, default)
    return default


def _read_view_int(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    default: int,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> int:
    if key in settings_view:
        return settings_view.read_int(key, default)
    if fallback_obj is not None and fallback_attr is not None:
        return _safe_int(fallback_obj, fallback_attr, default)
    return default


def _read_view_optional_int(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> int | None:
    if key in settings_view:
        return settings_view.read_optional_int(key)
    if fallback_obj is not None and fallback_attr is not None:
        return _safe_optional_int(fallback_obj, fallback_attr)
    return None


def _read_view_normalized_str(
    settings_view: ConfigSettingsView,
    key: str,
    *,
    default: str,
    fallback_obj: object | None = None,
    fallback_attr: str | None = None,
) -> str:
    if key in settings_view:
        return settings_view.read_normalized_str(key, default)
    if fallback_obj is not None and fallback_attr is not None:
        return _safe_normalized_str(fallback_obj, fallback_attr, default)
    return str(default).strip().lower()


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


def _safe_normalized_str(obj: object, name: str, default: str) -> str:
    value = _safe_getattr_or_default(obj, name, default)
    try:
        normalized = str(value or default).strip().lower()
    except _SETTINGS_ATTR_READ_ERRORS:
        logger.exception("Failed coercing settings attribute '%s' to normalized string", name)
        return str(default).strip().lower()
    return normalized or str(default).strip().lower()


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

    settings_view = _settings_view_from_config(config)
    reader = _SettingsReader(config=config, settings_view=settings_view)

    base_brightness = reader.read_int("brightness", default=25)
    bs_enabled = reader.read_bool("battery_saver_enabled", default=False)
    bs_brightness = reader.read_int("battery_saver_brightness", default=25)

    ac_override = reader.read_optional_int("ac_lighting_brightness")
    batt_override = reader.read_optional_int("battery_lighting_brightness")

    power_management_enabled = reader.read_bool(
        "power_management_enabled",
        default=reader.read_bool("management_enabled", default=True),
    )
    autostart = reader.read_bool("autostart", default=True)
    experimental_backends_enabled = reader.read_bool("experimental_backends_enabled", default=False)
    ac_lighting_enabled = reader.read_bool("ac_lighting_enabled", default=True)
    battery_lighting_enabled = reader.read_bool("battery_lighting_enabled", default=True)
    screen_dim_sync_enabled = reader.read_bool("screen_dim_sync_enabled", default=True)
    screen_dim_sync_mode = reader.read_normalized_str("screen_dim_sync_mode", default="off")
    screen_dim_temp_brightness = clamp_nonzero_brightness(
        reader.read_int("screen_dim_temp_brightness", default=5),
        default=5,
    )
    physical_layout = reader.read_normalized_str("physical_layout", default="auto")

    ac_brightness = ac_override if ac_override is not None else base_brightness

    if batt_override is not None:
        batt_brightness = batt_override
    else:
        batt_brightness = bs_brightness if bs_enabled else base_brightness

    return SettingsValues(
        power_management_enabled=power_management_enabled,
        power_off_on_suspend=reader.read_bool("power_off_on_suspend", default=True),
        power_off_on_lid_close=reader.read_bool("power_off_on_lid_close", default=True),
        power_restore_on_resume=reader.read_bool("power_restore_on_resume", default=True),
        power_restore_on_lid_open=reader.read_bool("power_restore_on_lid_open", default=True),
        autostart=autostart,
        experimental_backends_enabled=experimental_backends_enabled,
        ac_lighting_enabled=ac_lighting_enabled,
        battery_lighting_enabled=battery_lighting_enabled,
        ac_lighting_brightness=clamp_brightness(ac_brightness),
        battery_lighting_brightness=clamp_brightness(batt_brightness),
        screen_dim_sync_enabled=screen_dim_sync_enabled,
        screen_dim_sync_mode=screen_dim_sync_mode,
        screen_dim_temp_brightness=screen_dim_temp_brightness,
        os_autostart_enabled=bool(os_autostart_enabled),
        physical_layout=physical_layout,
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
