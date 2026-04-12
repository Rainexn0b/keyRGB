from __future__ import annotations

import json
from collections.abc import Iterable, MutableMapping
from pathlib import Path
from typing import Callable, SupportsIndex, SupportsInt, cast


_BRIGHTNESS_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_RGB_TRIPLET_UNPACK_ERRORS = (TypeError, ValueError)
_CONFIG_LOAD_ERRORS = (OSError, UnicodeDecodeError, json.JSONDecodeError)
_RGB_CHANNEL_FLOAT_ERRORS = (ValueError, OverflowError)
_RGB_CHANNEL_PARSE_ERRORS = (ValueError, OverflowError)
_SAVE_CALLBACK_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)

RgbTriplet = tuple[int, int, int]
IntCoercible = SupportsInt | SupportsIndex | str | bytes | bytearray


def _coerce_int(value: object) -> int:
    return int(cast(IntCoercible, value))


def normalize_brightness_value(value: object) -> int:
    """Normalize brightness to the persisted 0..50, 5-step grid."""

    try:
        normalized = _coerce_int(value)
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0

    normalized = max(0, min(50, normalized))
    if normalized == 0:
        return 0

    snapped = int(round(normalized / 5.0)) * 5
    snapped = max(0, min(50, snapped))
    if snapped == 0:
        snapped = 5
    return snapped


def normalize_precise_brightness_value(value: object) -> int:
    """Clamp brightness to the persisted 0..50 range without 5-step snapping."""

    try:
        normalized = _coerce_int(value)
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0

    return max(0, min(50, normalized))


def normalize_trail_percent_value(value: object) -> int:
    """Clamp reactive trail length to the persisted 1..100 range."""

    try:
        normalized = _coerce_int(value)
    except _BRIGHTNESS_COERCION_ERRORS:
        return 50

    return max(1, min(100, normalized))


def normalize_rgb_triplet(
    value: object,
    *,
    default: RgbTriplet = (255, 255, 255),
) -> RgbTriplet:
    """Best-effort coerce an RGB-like value to a clamped 3-tuple."""

    try:
        red, green, blue = cast(Iterable[object], value)
    except _RGB_TRIPLET_UNPACK_ERRORS:
        red, green, blue = default

    return (_clamp_rgb_channel(red), _clamp_rgb_channel(green), _clamp_rgb_channel(blue))


def coerce_loaded_settings(
    *,
    settings: MutableMapping[str, object],
    config_file: Path,
    save_fn: Callable[[], None],
) -> None:
    """Mutate loaded settings into a consistent persisted shape."""

    changed = False

    perkey_present_on_disk = False
    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except _CONFIG_LOAD_ERRORS:
        raw = None

    if isinstance(raw, dict) and "perkey_brightness" in raw:
        perkey_present_on_disk = True

    before = settings.get("brightness", None)
    after = normalize_brightness_value(before if before is not None else 0)
    if before != after:
        settings["brightness"] = after
        changed = True

    perkey_before = settings.get("perkey_brightness", None)
    if perkey_before is None or not perkey_present_on_disk:
        settings["perkey_brightness"] = int(after)
        changed = True
    else:
        perkey_after = normalize_brightness_value(perkey_before)
        if perkey_before != perkey_after:
            settings["perkey_brightness"] = int(perkey_after)
            changed = True

    reactive_before = settings.get("reactive_brightness", None)
    if reactive_before is not None:
        reactive_after = normalize_precise_brightness_value(reactive_before)
        if reactive_before != reactive_after:
            settings["reactive_brightness"] = int(reactive_after)
            changed = True

    trail_before = settings.get("reactive_trail_percent", None)
    if trail_before is not None:
        trail_after = normalize_trail_percent_value(trail_before)
        if trail_before != trail_after:
            settings["reactive_trail_percent"] = int(trail_after)
            changed = True

    for key in ("ac_lighting_brightness", "battery_lighting_brightness"):
        raw_value = settings.get(key, None)
        if raw_value is None:
            continue
        normalized = normalize_brightness_value(raw_value)
        if raw_value != normalized:
            settings[key] = int(normalized)
            changed = True

    if not changed:
        return

    try:
        save_fn()
    except _SAVE_CALLBACK_ERRORS:
        return


def _clamp_rgb_channel(value: object) -> int:
    if isinstance(value, bool):
        normalized = int(value)
    elif isinstance(value, int):
        normalized = value
    elif isinstance(value, float):
        try:
            normalized = int(value)
        except _RGB_CHANNEL_FLOAT_ERRORS:
            return 0
    elif isinstance(value, str):
        try:
            normalized = int(value)
        except ValueError:
            try:
                normalized = int(float(value))
            except _RGB_CHANNEL_PARSE_ERRORS:
                return 0
    else:
        return 0

    return max(0, min(255, int(normalized)))
