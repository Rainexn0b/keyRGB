"""Apply the active profile's saved static colours to secondary routes.

Static/profile output deliberately does not use the animated software-target
selection.  This keeps profile-owned areas authoritative when the keyboard is
in a hardware effect, Static mode, or a keyboard-only software animation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import cast

from src.core import secondary_lighting_state
from src.core.secondary_device_routes import SecondaryDeviceRoute
from src.core.secondary_device_runtime import (
    EffectiveSecondaryRoute,
    acquire_secondary_device,
    iter_effective_secondary_routes,
)

logger = logging.getLogger(__name__)

_SCENE_RUNTIME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def _profile_payload(tray: object) -> Mapping[str, object] | None:
    payload = vars(tray).get("_active_secondary_lighting")
    return cast(Mapping[str, object], payload) if isinstance(payload, Mapping) else None


def payload_from_config(config: object) -> dict[str, object] | None:
    """Build the poller's profile-state payload from the mirrored config state."""
    getter = vars(config).get("_secondary_device_state")
    if callable(getter):
        try:
            state = getter()
        except _SCENE_RUNTIME_EXCEPTIONS:
            state = None
    else:
        settings = vars(config).get("_settings")
        state = settings.get("secondary_device_state") if isinstance(settings, Mapping) else None
    if not isinstance(state, Mapping):
        return None
    return {"version": 1, "areas": dict(state)}


def _forced_off(tray: object) -> bool:
    return any(
        bool(getattr(tray, attr, False)) for attr in ("_user_forced_off", "_idle_forced_off", "_power_forced_off")
    )


def _log_route_failure(tray: object, route: SecondaryDeviceRoute, exc: Exception) -> None:
    logger.warning("Failed to apply static secondary route %s: %s", route.state_key, exc, exc_info=True)


def apply_secondary_static_scene(
    tray: object,
    *,
    payload: Mapping[str, object] | None = None,
    effective_routes_fn: Callable[..., tuple[EffectiveSecondaryRoute, ...]] = iter_effective_secondary_routes,
    acquire_device_fn: Callable[[SecondaryDeviceRoute], object] = acquire_secondary_device,
) -> bool:
    """Apply profile-owned static state, isolating failures per route."""

    if _forced_off(tray):
        return False
    effective_routes = tuple(effective_routes_fn())
    profile = _profile_payload(tray) if payload is None else payload
    if profile is None:
        profile = secondary_lighting_state.payload_from_config(
            getattr(tray, "config", None),
            (effective.route for effective in effective_routes if effective.available),
        )
    applied = False
    for effective in effective_routes:
        route = effective.route
        if not effective.available or not route.supports_profile_state:
            continue
        entry = secondary_lighting_state.area_entry(profile, route.state_key)
        device: object | None = None
        try:
            device = acquire_device_fn(route)
            # A present secondary profile component is authoritative. Missing
            # registered routes are disabled, not inherited from the last scene.
            if entry is not None and secondary_lighting_state.entry_enabled(entry):
                setter = getattr(device, "set_color")
                config = getattr(tray, "config", None)
                setter(
                    secondary_lighting_state.route_color(config, route, entry),
                    brightness=secondary_lighting_state.route_brightness(config, route, entry),
                )
            else:
                getattr(device, "turn_off")()
            applied = True
        except _SCENE_RUNTIME_EXCEPTIONS as exc:
            _log_route_failure(tray, route, exc)
        finally:
            close = getattr(device, "close", None)
            if callable(close):
                try:
                    close()
                except _SCENE_RUNTIME_EXCEPTIONS as exc:
                    _log_route_failure(tray, route, exc)
    return applied


def apply_secondary_static_route(
    tray: object,
    route: SecondaryDeviceRoute,
    *,
    payload: Mapping[str, object] | None = None,
    acquire_device_fn: Callable[[SecondaryDeviceRoute], object] = acquire_secondary_device,
) -> bool:
    """Apply one selected route from the active profile scene."""

    if _forced_off(tray) or not route.supports_profile_state:
        return False
    profile = _profile_payload(tray) if payload is None else payload
    if profile is None:
        profile = secondary_lighting_state.payload_from_config(getattr(tray, "config", None), (route,))
    entry = secondary_lighting_state.area_entry(profile, route.state_key)
    device: object | None = None
    try:
        device = acquire_device_fn(route)
        if entry is not None and secondary_lighting_state.entry_enabled(entry):
            config = getattr(tray, "config", None)
            getattr(device, "set_color")(
                secondary_lighting_state.route_color(config, route, entry),
                brightness=secondary_lighting_state.route_brightness(config, route, entry),
            )
        else:
            getattr(device, "turn_off")()
        return True
    except _SCENE_RUNTIME_EXCEPTIONS as exc:
        _log_route_failure(tray, route, exc)
        return False
    finally:
        close = getattr(device, "close", None)
        if callable(close):
            try:
                close()
            except _SCENE_RUNTIME_EXCEPTIONS as exc:
                _log_route_failure(tray, route, exc)


def turn_off_secondary_profile_areas(
    tray: object,
    *,
    payload: Mapping[str, object] | None = None,
    effective_routes_fn: Callable[..., tuple[EffectiveSecondaryRoute, ...]] = iter_effective_secondary_routes,
    acquire_device_fn: Callable[[SecondaryDeviceRoute], object] = acquire_secondary_device,
) -> None:
    """Turn off profile-owned routes for global power-off, independent of effect output."""

    profile = _profile_payload(tray) if payload is None else payload
    if profile is None:
        return
    for effective in effective_routes_fn():
        route = effective.route
        if not effective.available or not route.supports_profile_state:
            continue
        device: object | None = None
        try:
            device = acquire_device_fn(route)
            getattr(device, "turn_off")()
        except _SCENE_RUNTIME_EXCEPTIONS as exc:
            _log_route_failure(tray, route, exc)
        finally:
            close = getattr(device, "close", None)
            if callable(close):
                try:
                    close()
                except _SCENE_RUNTIME_EXCEPTIONS as exc:
                    _log_route_failure(tray, route, exc)


__all__ = [
    "apply_secondary_static_route",
    "apply_secondary_static_scene",
    "payload_from_config",
    "turn_off_secondary_profile_areas",
]
