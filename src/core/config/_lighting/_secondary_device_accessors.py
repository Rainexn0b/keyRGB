#!/usr/bin/env python3
"""Secondary-device and lightbar config access helpers."""

from __future__ import annotations

from typing import Protocol, cast

from ._coercion import normalize_rgb_triplet


RgbTriplet = tuple[int, int, int]
_MISSING = object()


class DefaultSettingFn(Protocol):
    def __call__(
        self,
        defaults: object,
        key: str,
        *,
        fallback_keys: tuple[str, ...] = (),
        default: object,
    ) -> object: ...


class CoerceIntSettingFn(Protocol):
    def __call__(self, value: object, *, default: int = 0) -> int: ...


class SecondaryDeviceAccessorConfig(Protocol):
    _settings: dict[str, object]
    DEFAULTS: object

    def _save(self) -> None: ...

    @staticmethod
    def _normalize_brightness_value(value: int) -> int: ...


def secondary_device_state(config: SecondaryDeviceAccessorConfig) -> dict[str, object]:
    raw = config._settings.get("secondary_device_state", None)
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    state: dict[str, object] = {}
    config._settings["secondary_device_state"] = state
    return state


def normalize_secondary_state_key(value: object, *, default: str = "device") -> str:
    normalized = str(value or default).strip().lower()
    return normalized or default


def get_secondary_device_brightness(
    config: SecondaryDeviceAccessorConfig,
    state_key: str,
    *,
    fallback_keys: tuple[str, ...] = (),
    default: int = 25,
    default_setting_fn: DefaultSettingFn,
    coerce_int_setting_fn: CoerceIntSettingFn,
) -> int:
    normalized_key = normalize_secondary_state_key(state_key)
    state = secondary_device_state(config).get(normalized_key, None)
    if isinstance(state, dict):
        value = state.get("brightness", _MISSING)
        if value is not _MISSING:
            return config._normalize_brightness_value(coerce_int_setting_fn(value, default=default))

    default_lookup_key = fallback_keys[0] if fallback_keys else normalized_key
    default_fallback_keys = fallback_keys[1:] if fallback_keys else ()
    fallback_value = default_setting_fn(
        config.DEFAULTS,
        default_lookup_key,
        fallback_keys=default_fallback_keys,
        default=default,
    )
    for key in fallback_keys:
        compatibility_value = config._settings.get(key, _MISSING)
        if compatibility_value is not _MISSING:
            fallback_value = compatibility_value
            break
    return config._normalize_brightness_value(coerce_int_setting_fn(fallback_value, default=default))


def set_secondary_device_brightness(
    config: SecondaryDeviceAccessorConfig,
    state_key: str,
    value: int,
    *,
    compatibility_key: str | None = None,
) -> None:
    normalized_key = normalize_secondary_state_key(state_key)
    brightness = config._normalize_brightness_value(value)
    state = secondary_device_state(config)
    entry = state.get(normalized_key, None)
    if not isinstance(entry, dict):
        entry = {}
    entry["brightness"] = brightness
    state[normalized_key] = entry
    if compatibility_key:
        config._settings[str(compatibility_key)] = brightness
    config._save()


def get_secondary_device_color(
    config: SecondaryDeviceAccessorConfig,
    state_key: str,
    *,
    fallback_keys: tuple[str, ...] = (),
    default: RgbTriplet = (255, 0, 0),
    default_setting_fn: DefaultSettingFn,
) -> RgbTriplet:
    normalized_key = normalize_secondary_state_key(state_key)
    state = secondary_device_state(config).get(normalized_key, None)
    if isinstance(state, dict):
        value = state.get("color", _MISSING)
        if value is not _MISSING:
            return normalize_rgb_triplet(value, default=default)

    default_lookup_key = fallback_keys[0] if fallback_keys else normalized_key
    default_fallback_keys = fallback_keys[1:] if fallback_keys else ()
    fallback_value = default_setting_fn(
        config.DEFAULTS,
        default_lookup_key,
        fallback_keys=default_fallback_keys,
        default=list(default),
    )
    for key in fallback_keys:
        compatibility_value = config._settings.get(key, _MISSING)
        if compatibility_value is not _MISSING:
            fallback_value = compatibility_value
            break
    return normalize_rgb_triplet(fallback_value, default=default)


def set_secondary_device_color(
    config: SecondaryDeviceAccessorConfig,
    state_key: str,
    value: RgbTriplet | tuple,
    *,
    compatibility_key: str | None = None,
    default: RgbTriplet = (255, 0, 0),
) -> None:
    normalized_key = normalize_secondary_state_key(state_key)
    color = list(normalize_rgb_triplet(value, default=default))
    state = secondary_device_state(config)
    entry = state.get(normalized_key, None)
    if not isinstance(entry, dict):
        entry = {}
    entry["color"] = color
    state[normalized_key] = entry
    if compatibility_key:
        config._settings[str(compatibility_key)] = list(color)
    config._save()


def get_lightbar_brightness(
    config: SecondaryDeviceAccessorConfig,
    *,
    default_setting_fn: DefaultSettingFn,
    coerce_int_setting_fn: CoerceIntSettingFn,
) -> int:
    return get_secondary_device_brightness(
        config,
        "lightbar",
        fallback_keys=("lightbar_brightness", "brightness"),
        default=coerce_int_setting_fn(config._settings.get("brightness", 0), default=0),
        default_setting_fn=default_setting_fn,
        coerce_int_setting_fn=coerce_int_setting_fn,
    )


def set_lightbar_brightness(config: SecondaryDeviceAccessorConfig, value: int) -> None:
    set_secondary_device_brightness(config, "lightbar", value, compatibility_key="lightbar_brightness")


def get_lightbar_color(
    config: SecondaryDeviceAccessorConfig,
    *,
    default_setting_fn: DefaultSettingFn,
) -> RgbTriplet:
    return get_secondary_device_color(
        config,
        "lightbar",
        fallback_keys=("lightbar_color", "color"),
        default=(255, 0, 0),
        default_setting_fn=default_setting_fn,
    )


def set_lightbar_color(
    config: SecondaryDeviceAccessorConfig,
    value: RgbTriplet | tuple,
) -> None:
    set_secondary_device_color(config, "lightbar", value, compatibility_key="lightbar_color", default=(255, 0, 0))
