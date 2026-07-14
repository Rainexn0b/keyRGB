"""Shared interpretation of profile and config state for secondary lighting.

Storage, tray rendering, diagnostics, and editor code all consume the same
``enabled`` / ``color`` / optional ``brightness`` contract.  Keeping those
coercion and legacy-fallback rules here prevents each runtime path from
quietly developing different semantics.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TypeAlias, cast

from src.core.secondary_device_routes import (
    BRIGHTNESS_POLICY_INDEPENDENT,
    BRIGHTNESS_POLICY_PRIMARY_SHARED,
    SecondaryDeviceRoute,
)


RGB: TypeAlias = tuple[int, int, int]
AreaEntry: TypeAlias = Mapping[object, object]
_STATE_READ_ERRORS = (AttributeError, OSError, OverflowError, RuntimeError, TypeError, ValueError)


def normalize_color(value: object, default: RGB = (255, 0, 0)) -> RGB:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return default
    try:
        return cast(RGB, tuple(max(0, min(255, int(channel))) for channel in value))
    except (TypeError, ValueError, OverflowError):
        return default


def normalize_brightness(value: object, default: int = 25) -> int:
    try:
        return max(0, min(100, int(cast(int, value))))
    except (TypeError, ValueError, OverflowError):
        return max(0, min(100, int(default)))


def normalize_enabled(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return bool(default)


def areas(payload: object) -> Mapping[object, object]:
    raw = payload.get("areas") if isinstance(payload, Mapping) else None
    return cast(Mapping[object, object], raw) if isinstance(raw, Mapping) else {}


def area_entry(payload: object, state_key: object) -> AreaEntry | None:
    raw = areas(payload).get(str(state_key or "").strip().lower())
    return cast(AreaEntry, raw) if isinstance(raw, Mapping) else None


def entry_enabled(entry: object, *, default: bool = True) -> bool:
    if not isinstance(entry, Mapping):
        return bool(default)
    if "enabled" in entry:
        return normalize_enabled(entry.get("enabled"), default)
    brightness = entry.get("brightness")
    if isinstance(brightness, (int, float)):
        return brightness > 0
    return bool(default)


def enabled_state_keys(payload: object) -> set[str]:
    return {
        str(raw_key).strip().lower()
        for raw_key, raw_entry in areas(payload).items()
        if isinstance(raw_entry, Mapping) and entry_enabled(raw_entry)
    }


def config_color(config: object | None, route: SecondaryDeviceRoute, *, default: RGB = (255, 0, 0)) -> RGB:
    getter = getattr(config, "get_secondary_device_color", None)
    if callable(getter):
        try:
            return normalize_color(
                getter(
                    route.state_key,
                    fallback_keys=tuple(filter(None, (route.config_color_attr,))),
                    default=default,
                ),
                default,
            )
        except _STATE_READ_ERRORS:
            pass
    attr = str(route.config_color_attr or "").strip()
    return normalize_color(getattr(config, attr, default) if config is not None and attr else default, default)


def config_brightness(config: object | None, route: SecondaryDeviceRoute, *, default: int = 25) -> int:
    if route.brightness_policy == BRIGHTNESS_POLICY_PRIMARY_SHARED:
        return normalize_brightness(getattr(config, "brightness", default), default)
    getter = getattr(config, "get_secondary_device_brightness", None)
    if callable(getter):
        try:
            return normalize_brightness(
                getter(
                    route.state_key,
                    fallback_keys=tuple(filter(None, (route.config_brightness_attr,))),
                    default=default,
                ),
                default,
            )
        except _STATE_READ_ERRORS:
            pass
    attr = str(route.config_brightness_attr or "").strip()
    return normalize_brightness(getattr(config, attr, default) if config is not None and attr else default, default)


def config_enabled(config: object | None, route: SecondaryDeviceRoute, *, default: bool = False) -> bool:
    getter = getattr(config, "get_secondary_device_enabled", None)
    if callable(getter):
        try:
            return bool(
                getter(
                    route.state_key,
                    fallback_keys=tuple(filter(None, (route.config_brightness_attr,))),
                    default=default,
                )
            )
        except _STATE_READ_ERRORS:
            pass
    return config_brightness(config, route, default=1 if default else 0) > 0


def route_color(config: object | None, route: SecondaryDeviceRoute, entry: AreaEntry) -> RGB:
    return normalize_color(entry.get("color"), config_color(config, route))


def route_brightness(config: object | None, route: SecondaryDeviceRoute, entry: AreaEntry) -> int:
    if route.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT and isinstance(entry.get("brightness"), (int, float)):
        return normalize_brightness(entry.get("brightness"))
    return config_brightness(config, route)


def payload_from_config(
    config: object | None,
    routes: Iterable[SecondaryDeviceRoute],
) -> dict[str, object]:
    """Build a non-persistent profile-shaped snapshot for legacy profiles.

    This lets upgraded installations receive static secondary output immediately
    without silently materializing or rewriting their profile on read.
    """

    route_areas: dict[str, object] = {}
    for route in routes:
        if not route.supports_profile_state:
            continue
        entry: dict[str, object] = {
            "enabled": config_enabled(config, route),
            "color": list(config_color(config, route)),
        }
        if route.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT:
            entry["brightness"] = config_brightness(config, route)
        route_areas[route.state_key] = entry
    return {"version": 1, "areas": route_areas}


__all__ = [
    "AreaEntry",
    "RGB",
    "area_entry",
    "areas",
    "config_brightness",
    "config_color",
    "config_enabled",
    "enabled_state_keys",
    "entry_enabled",
    "normalize_brightness",
    "normalize_color",
    "normalize_enabled",
    "payload_from_config",
    "route_brightness",
    "route_color",
]
