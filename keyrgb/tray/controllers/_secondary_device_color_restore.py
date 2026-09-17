"""Color-preserving restore helpers for one-shot secondary devices."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from keyrgb.core import secondary_lighting_state
from keyrgb.core.secondary_device_routes import BRIGHTNESS_POLICY_INDEPENDENT, SecondaryDeviceRoute
from keyrgb.tray.protocols import LightingTrayProtocol


class SecondaryColorDevice(Protocol):
    def set_color(self, color: tuple[int, int, int], *, brightness: int) -> None: ...

    def set_brightness(self, brightness: int) -> None: ...

    def turn_off(self) -> None: ...


def active_profile_route_entry(
    tray: LightingTrayProtocol, route: SecondaryDeviceRoute
) -> secondary_lighting_state.AreaEntry | None:
    return secondary_lighting_state.area_entry(vars(tray).get("_active_secondary_lighting"), route.state_key)


def active_profile_route_brightness(tray: LightingTrayProtocol, route: SecondaryDeviceRoute) -> int | None:
    entry = active_profile_route_entry(tray, route)
    if entry is None or not isinstance(entry.get("brightness"), (int, float)):
        return None
    brightness = secondary_lighting_state.normalize_brightness(entry.get("brightness"), default=0)
    return brightness if brightness > 0 else None


def secondary_route_color(tray: LightingTrayProtocol, route: SecondaryDeviceRoute) -> secondary_lighting_state.RGB:
    entry = active_profile_route_entry(tray, route)
    if not hasattr(route, "config_color_attr"):
        return secondary_lighting_state.normalize_color(entry.get("color") if entry is not None else None)
    return secondary_lighting_state.route_color(getattr(tray, "config", None), route, entry or {})


def set_color_and_brightness(
    device: SecondaryColorDevice,
    color: secondary_lighting_state.RGB,
    brightness: int,
) -> None:
    setter = getattr(device, "set_color", None)
    if callable(setter):
        setter(color, brightness=int(brightness))
        return
    # Compatibility for older duck-typed third-party routes. Registered colour
    # routes expose set_color, which is required for fresh one-shot devices.
    device.set_brightness(int(brightness))


class TurnOnProfileTrayView:
    """Read-through tray view with an enabled route for pre-commit device I/O."""

    def __init__(self, tray: LightingTrayProtocol, payload: Mapping[str, object]) -> None:
        self._tray = tray
        self.config = getattr(tray, "config", None)
        self._active_secondary_lighting = payload

    def __getattr__(self, name: str) -> object:
        return getattr(self._tray, name)


def turn_on_profile_payload(
    tray: LightingTrayProtocol,
    route: SecondaryDeviceRoute,
    restore_brightness: int,
) -> dict[str, object]:
    current = vars(tray).get("_active_secondary_lighting")
    payload: dict[str, object] = (
        {str(key): value for key, value in current.items()} if isinstance(current, Mapping) else {"version": 1}
    )
    areas = dict(secondary_lighting_state.areas(current))
    existing = areas.get(route.state_key)
    entry = dict(existing) if isinstance(existing, Mapping) else {}
    entry["enabled"] = True
    if getattr(route, "brightness_policy", None) == BRIGHTNESS_POLICY_INDEPENDENT:
        entry["brightness"] = int(restore_brightness)
    areas[route.state_key] = entry
    payload["areas"] = areas
    return payload


__all__ = [
    "SecondaryColorDevice",
    "TurnOnProfileTrayView",
    "active_profile_route_brightness",
    "active_profile_route_entry",
    "secondary_route_color",
    "set_color_and_brightness",
    "turn_on_profile_payload",
]
