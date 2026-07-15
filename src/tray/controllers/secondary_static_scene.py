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
from src.core.secondary_device_routes import SecondaryDeviceRoute, iter_secondary_routes
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


def registered_profile_state_keys() -> frozenset[str]:
    """Return every registered profile-capable route key (catalog, not inventory).

    Authority for config mirrors uses this catalog.  Device availability must
    not change whether a mirror is complete or authoritative.
    """

    return frozenset(route.state_key for route in iter_secondary_routes() if route.supports_profile_state)


def is_authoritative_secondary_state(state: object) -> bool:
    """True when a config-mirror mapping is a complete, explicit profile scene.

    A mirror is authoritative only when every registered profile-capable route
    is present as a mapping with an explicit ``enabled`` field.  Empty, partial,
    or pre-enabled v0.28.x maps are compatibility sources, not all-off scenes.
    Unknown route keys may be present and are ignored for completeness.
    """

    if not isinstance(state, Mapping) or not state:
        return False
    known_state_keys = registered_profile_state_keys()
    if not known_state_keys.issubset(state):
        return False
    for state_key in known_state_keys:
        entry = state[state_key]
        if not isinstance(entry, Mapping) or "enabled" not in entry:
            return False
    return True


def authoritative_payload_from_config(config: object) -> dict[str, object] | None:
    """Return an authoritative profile payload from the config mirror, or None.

    None means the poller should build a non-persistent legacy snapshot via
    ``secondary_lighting_state.legacy_snapshot_from_config``.
    """

    getter = vars(config).get("_secondary_device_state")
    if callable(getter):
        try:
            state = getter()
        except _SCENE_RUNTIME_EXCEPTIONS:
            state = None
    else:
        settings = vars(config).get("_settings")
        state = settings.get("secondary_device_state") if isinstance(settings, Mapping) else None
    if not is_authoritative_secondary_state(state):
        return None
    areas = dict(cast(Mapping[object, object], state))
    return {"version": 1, "areas": areas}


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
        profile = secondary_lighting_state.legacy_snapshot_from_config(
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
        profile = secondary_lighting_state.legacy_snapshot_from_config(getattr(tray, "config", None), (route,))
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
    effective_routes_fn: Callable[..., tuple[EffectiveSecondaryRoute, ...]] = iter_effective_secondary_routes,
    acquire_device_fn: Callable[[SecondaryDeviceRoute], object] = acquire_secondary_device,
) -> None:
    """Turn off independent profile-owned routes for global power-off.

    Composite virtual zones whose primary owns global output are skipped: the
    keyboard path already suspended the shared controller, and child turn_off
    would be misinterpreted as a desired-scene edit if applied after that.
    """

    for effective in effective_routes_fn():
        route = effective.route
        if not effective.available or not route.supports_profile_state:
            continue
        if bool(getattr(route, "primary_owns_global_off", False)):
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
    "authoritative_payload_from_config",
    "is_authoritative_secondary_state",
    "registered_profile_state_keys",
    "turn_off_secondary_profile_areas",
]
