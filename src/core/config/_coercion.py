from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def normalize_brightness_value(value: Any) -> int:
    """Normalize brightness to the persisted 0..50, 5-step grid."""

    try:
        normalized = int(value)
    except Exception:
        return 0

    normalized = max(0, min(50, normalized))
    if normalized == 0:
        return 0

    snapped = int(round(normalized / 5.0)) * 5
    snapped = max(0, min(50, snapped))
    if snapped == 0:
        snapped = 5
    return snapped


def normalize_rgb_triplet(
    value: Any,
    *,
    default: tuple[int, int, int] = (255, 255, 255),
) -> tuple[int, int, int]:
    """Best-effort coerce an RGB-like value to a clamped 3-tuple."""

    try:
        red, green, blue = value  # type: ignore[misc]
    except Exception:
        red, green, blue = default

    return (_clamp_rgb_channel(red), _clamp_rgb_channel(green), _clamp_rgb_channel(blue))


def coerce_loaded_settings(
    *,
    settings: dict[str, Any],
    config_file: Path,
    save_fn: Callable[[], None],
) -> None:
    """Mutate loaded settings into a consistent persisted shape."""

    try:
        changed = False

        perkey_present_on_disk = False
        try:
            with open(config_file, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict) and "perkey_brightness" in raw:
                perkey_present_on_disk = True
        except Exception:
            perkey_present_on_disk = False

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

        for key in ("ac_lighting_brightness", "battery_lighting_brightness"):
            raw_value = settings.get(key, None)
            if raw_value is None:
                continue
            normalized = normalize_brightness_value(raw_value)
            if raw_value != normalized:
                settings[key] = int(normalized)
                changed = True

        if changed:
            save_fn()
    except Exception:
        return


def _clamp_rgb_channel(value: Any) -> int:
    try:
        if isinstance(value, bool):
            normalized = int(value)
        elif isinstance(value, int):
            normalized = value
        elif isinstance(value, float):
            normalized = int(value)
        elif isinstance(value, str):
            try:
                normalized = int(value)
            except Exception:
                normalized = int(float(value))
        else:
            return 0
    except Exception:
        return 0

    return max(0, min(255, int(normalized)))