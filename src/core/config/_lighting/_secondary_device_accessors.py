#!/usr/bin/env python3
"""Secondary-device and lightbar config access helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, cast

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


@dataclass
class _SecondaryDeviceEntry:
    """Typed boundary over a secondary-device state entry map."""

    values: dict[str, object]

    def brightness(self) -> object:
        return self.values.get("brightness", _MISSING)

    def color(self) -> object:
        return self.values.get("color", _MISSING)

    def set_brightness(self, value: int) -> None:
        self.values["brightness"] = value

    def set_color(self, value: list[int]) -> None:
        self.values["color"] = value


@dataclass
class _SecondaryDeviceStateBoundary:
    """Typed boundary for the per-device secondary state map in settings."""

    values: dict[str, object]

    @classmethod
    def from_config(cls, config: SecondaryDeviceAccessorConfig) -> _SecondaryDeviceStateBoundary:
        raw = config._settings.get("secondary_device_state", None)
        if isinstance(raw, dict):
            return cls(values=cast(dict[str, object], raw))
        state: dict[str, object] = {}
        config._settings["secondary_device_state"] = state
        return cls(values=state)

    def entry(self, key: str) -> _SecondaryDeviceEntry:
        raw = self.values.get(key, None)
        if isinstance(raw, dict):
            return _SecondaryDeviceEntry(values=cast(dict[str, object], raw))
        created: dict[str, object] = {}
        self.values[key] = created
        return _SecondaryDeviceEntry(values=created)

    def existing_entry(self, key: str) -> _SecondaryDeviceEntry | None:
        raw = self.values.get(key, None)
        if not isinstance(raw, dict):
            return None
        return _SecondaryDeviceEntry(values=cast(dict[str, object], raw))


def secondary_device_state(config: SecondaryDeviceAccessorConfig) -> dict[str, object]:
    return _SecondaryDeviceStateBoundary.from_config(config).values


def normalize_secondary_state_key(value: object, *, default: str = "device") -> str:
    normalized = str(value or default).strip().lower()
    return normalized or default


def _resolve_fallback_value(
    config: SecondaryDeviceAccessorConfig,
    normalized_key: str,
    *,
    fallback_keys: tuple[str, ...],
    default: object,
    default_setting_fn: DefaultSettingFn,
) -> object:
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
            return compatibility_value
    return fallback_value


def _entry_value_or_fallback(
    config: SecondaryDeviceAccessorConfig,
    state_key: str,
    *,
    fallback_keys: tuple[str, ...],
    default: object,
    default_setting_fn: DefaultSettingFn,
    getter: Callable[[_SecondaryDeviceEntry], object],
) -> object:
    normalized_key = normalize_secondary_state_key(state_key)
    state = _SecondaryDeviceStateBoundary.from_config(config)
    entry = state.existing_entry(normalized_key)
    if entry is not None:
        value = getter(entry)
        if value is not _MISSING:
            return value
    return _resolve_fallback_value(
        config,
        normalized_key,
        fallback_keys=fallback_keys,
        default=default,
        default_setting_fn=default_setting_fn,
    )


def get_secondary_device_brightness(
    config: SecondaryDeviceAccessorConfig,
    state_key: str,
    *,
    fallback_keys: tuple[str, ...] = (),
    default: int = 25,
    default_setting_fn: DefaultSettingFn,
    coerce_int_setting_fn: CoerceIntSettingFn,
) -> int:
    raw_value = _entry_value_or_fallback(
        config,
        state_key,
        fallback_keys=fallback_keys,
        default=default,
        default_setting_fn=default_setting_fn,
        getter=_SecondaryDeviceEntry.brightness,
    )
    return config._normalize_brightness_value(coerce_int_setting_fn(raw_value, default=default))


def set_secondary_device_brightness(
    config: SecondaryDeviceAccessorConfig,
    state_key: str,
    value: int,
    *,
    compatibility_key: str | None = None,
) -> None:
    normalized_key = normalize_secondary_state_key(state_key)
    brightness = config._normalize_brightness_value(value)
    state = _SecondaryDeviceStateBoundary.from_config(config)
    entry = state.entry(normalized_key)
    entry.set_brightness(brightness)
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
    raw_value = _entry_value_or_fallback(
        config,
        state_key,
        fallback_keys=fallback_keys,
        default=list(default),
        default_setting_fn=default_setting_fn,
        getter=_SecondaryDeviceEntry.color,
    )
    return normalize_rgb_triplet(raw_value, default=default)


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
    state = _SecondaryDeviceStateBoundary.from_config(config)
    entry = state.entry(normalized_key)
    entry.set_color(color)
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
