"""Central availability and acquisition seam for secondary lighting routes.

The route table describes production backends.  This module is the only place
where callers should turn those descriptions into effective routes or devices.
It also owns the opt-in, hardware-free secondary-device simulation used by
tests and manual UX validation.
"""

from __future__ import annotations

# @quality-exception file-size-analysis: secondary route availability + simulation runtime; cohesive subsystem for one ownership area

import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from src.core.backends.base import BackendCapabilities
from src.core.secondary_device_routes import SecondaryDeviceRoute, iter_secondary_routes


logger = logging.getLogger(__name__)

SIMULATION_ENVIRONMENT_VARIABLE = "KEYRGB_SIMULATE_SECONDARY_DEVICES"
_SIMULATION_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_SIMULATION_FALSE_VALUES = frozenset({"", "0", "false", "no", "off"})
_ROUTE_RUNTIME_ERRORS = (AttributeError, ImportError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _simulation_flag_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        normalized = str(value).strip().lower()
    except (AttributeError, TypeError, ValueError):
        return False
    if normalized in _SIMULATION_TRUE_VALUES:
        return True
    if normalized in _SIMULATION_FALSE_VALUES:
        return False
    return False


def secondary_device_simulation_enabled() -> bool:
    """Return whether secondary-device simulation is explicitly enabled."""
    return _simulation_flag_value(os.environ.get(SIMULATION_ENVIRONMENT_VARIABLE))


@dataclass(frozen=True)
class EffectiveSecondaryRoute:
    """A registered route after availability policy has been applied."""

    route: SecondaryDeviceRoute
    available: bool
    simulated: bool
    availability_source: str
    availability_reason: str = ""

    @property
    def backend_name(self) -> str:
        return self.route.backend_name

    @property
    def device_type(self) -> str:
        return self.route.device_type

    @property
    def display_name(self) -> str:
        return self.route.display_name

    @property
    def state_key(self) -> str:
        return self.route.state_key

    @property
    def supports_profile_state(self) -> bool:
        return bool(self.route.supports_profile_state)

    @property
    def brightness_policy(self) -> str:
        return self.route.brightness_policy


@dataclass
class _SimulatedRouteState:
    color: tuple[int, int, int] = (0, 0, 0)
    brightness: int = 0
    off: bool = True


def _clamp_channel(value: object) -> int:
    try:
        return max(0, min(255, int(cast(Any, value))))
    except (TypeError, ValueError, OverflowError):
        return 0


def _normalize_color(color: object) -> tuple[int, int, int]:
    try:
        values: tuple[object, ...] = tuple(cast(Iterable[object], color))
    except (TypeError, ValueError):
        values = ()
    if len(values) != 3:
        return (0, 0, 0)
    return tuple(_clamp_channel(value) for value in values)  # type: ignore[return-value]


def _clamp_brightness(value: object) -> int:
    try:
        return max(0, min(100, int(cast(Any, value))))
    except (TypeError, ValueError, OverflowError):
        return 0


class SimulatedUniformDevice:
    """In-memory uniform device implementing the production device surface."""

    supports_per_key = False

    def __init__(self, *, route: SecondaryDeviceRoute, state: _SimulatedRouteState) -> None:
        self.route = route
        self.device_type = route.device_type
        self._state = state
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError(f"Simulated secondary device is closed: {self.route.state_key}")

    def _log_state_change(self, action: str, **fields: object) -> None:
        if _simulation_flag_value(os.environ.get("KEYRGB_DEBUG")):
            logger.debug(
                "Simulated secondary route state changed: route=%s action=%s fields=%s",
                self.route.state_key,
                action,
                fields,
            )

    def set_color(self, color: object, *, brightness: int) -> None:
        self._ensure_open()
        normalized_color = _normalize_color(color)
        normalized_brightness = _clamp_brightness(brightness)
        self._state.color = normalized_color
        self._state.brightness = normalized_brightness
        self._state.off = normalized_brightness <= 0 or normalized_color == (0, 0, 0)
        self._log_state_change(
            "set_color",
            color=normalized_color,
            brightness=normalized_brightness,
            off=self._state.off,
        )

    def turn_off(self) -> None:
        self._ensure_open()
        self._state.brightness = 0
        self._state.off = True
        self._log_state_change("turn_off")

    def is_off(self) -> bool:
        self._ensure_open()
        return bool(self._state.off)

    def get_brightness(self) -> int:
        self._ensure_open()
        return int(self._state.brightness)

    def set_brightness(self, brightness: int) -> None:
        self._ensure_open()
        normalized_brightness = _clamp_brightness(brightness)
        self._state.brightness = normalized_brightness
        self._state.off = normalized_brightness <= 0 or self._state.color == (0, 0, 0)
        self._log_state_change("set_brightness", brightness=normalized_brightness, off=self._state.off)

    def get_color(self) -> tuple[int, int, int]:
        self._ensure_open()
        return (self._state.color[0], self._state.color[1], self._state.color[2])

    def set_key_colors(self, *_args: object, **_kwargs: object) -> None:
        self._ensure_open()
        raise NotImplementedError("Simulated secondary devices support uniform colour only")

    def set_effect(self, *_args: object, **_kwargs: object) -> None:
        self._ensure_open()
        raise NotImplementedError("Simulated secondary devices do not support hardware effects")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._log_state_change("close")


_SIMULATED_STATES: dict[str, _SimulatedRouteState] = {}


def _simulated_device_for_route(route: SecondaryDeviceRoute) -> SimulatedUniformDevice:
    state = _SIMULATED_STATES.setdefault(route.state_key, _SimulatedRouteState())
    return SimulatedUniformDevice(route=route, state=state)


class _SimulatedSecondaryBackend:
    """Backend-shaped facade for code that needs a backend before a device."""

    def __init__(self, route: SecondaryDeviceRoute) -> None:
        self.route = route
        self.name = f"simulated:{route.backend_name}"
        self.priority = 0
        self.stability = "validated"
        self.experimental_evidence = None

    def is_available(self) -> bool:
        return True

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=False, color=True, hardware_effects=False, palette=False)

    def get_device(self) -> SimulatedUniformDevice:
        return _simulated_device_for_route(self.route)

    def dimensions(self) -> tuple[int, int]:
        return (1, 1)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}


def _deduplicated_routes(routes: Iterable[SecondaryDeviceRoute]) -> tuple[SecondaryDeviceRoute, ...]:
    seen: set[str] = set()
    result: list[SecondaryDeviceRoute] = []
    for route in routes:
        state_key = str(route.state_key).strip()
        if not state_key or state_key in seen:
            continue
        seen.add(state_key)
        result.append(route)
    return tuple(result)


def _probe_backend_available(route: SecondaryDeviceRoute) -> tuple[bool, str]:
    backend = route.get_backend()
    probe = getattr(backend, "probe", None)
    if callable(probe):
        result = probe()
        return bool(getattr(result, "available", False)), str(getattr(result, "reason", "") or "")
    is_available = getattr(backend, "is_available", None)
    if not callable(is_available):
        return False, "backend has no availability probe"
    return bool(is_available()), ""


def _route_availability(
    route: SecondaryDeviceRoute,
    *,
    parent_availability: dict[str, tuple[bool, str]],
) -> tuple[bool, str, str]:
    parent_name = getattr(route, "parent_backend_name", None)
    if parent_name:
        if parent_name not in parent_availability:
            try:
                parent_availability[parent_name] = _probe_backend_available(route)
            except _ROUTE_RUNTIME_ERRORS:
                parent_availability[parent_name] = (False, "parent probe failed")
        available, reason = parent_availability[parent_name]
        return available, "parent_probe", reason

    try:
        available, reason = _probe_backend_available(route)
        return available, "backend_probe", reason
    except _ROUTE_RUNTIME_ERRORS as exc:
        return False, "backend_probe_error", str(exc)


def iter_effective_secondary_routes(
    routes: Iterable[SecondaryDeviceRoute] | None = None,
    *,
    include_unavailable: bool = False,
) -> tuple[EffectiveSecondaryRoute, ...]:
    """Return the stable effective secondary-route snapshot.

    Simulation deliberately bypasses every production backend probe and exposes
    all registered routes as available. In real mode, each parent backend is
    probed once per snapshot and unavailable routes are omitted by default.
    """
    registered = _deduplicated_routes(iter_secondary_routes() if routes is None else routes)
    if secondary_device_simulation_enabled():
        return tuple(
            EffectiveSecondaryRoute(
                route=route,
                available=True,
                simulated=True,
                availability_source="simulation",
                availability_reason="secondary-device simulation enabled",
            )
            for route in registered
        )

    parent_availability: dict[str, tuple[bool, str]] = {}
    effective: list[EffectiveSecondaryRoute] = []
    for route in registered:
        available, source, reason = _route_availability(route, parent_availability=parent_availability)
        if available or include_unavailable:
            effective.append(
                EffectiveSecondaryRoute(
                    route=route,
                    available=available,
                    simulated=False,
                    availability_source=source,
                    availability_reason=reason,
                )
            )
    return tuple(effective)


def route_is_available(route: SecondaryDeviceRoute) -> bool:
    """Return effective availability for one route without acquiring a device."""
    if secondary_device_simulation_enabled():
        return True
    available, _source, _reason = _route_availability(route, parent_availability={})
    return available


def has_available_secondary_profile_routes(
    routes: Iterable[SecondaryDeviceRoute] | None = None,
) -> bool:
    """Return whether the Lighting Profile Editor has a secondary route to show."""

    return any(
        effective.available and effective.route.supports_profile_state
        for effective in iter_effective_secondary_routes(routes)
    )


def acquire_secondary_device(route: SecondaryDeviceRoute) -> object:
    """Acquire one effective uniform device, honoring simulation precedence."""
    if secondary_device_simulation_enabled():
        return _simulated_device_for_route(route)
    return route.get_device()


def backend_for_secondary_route(route: SecondaryDeviceRoute) -> object:
    """Return the effective backend facade for one route."""
    if secondary_device_simulation_enabled():
        return _SimulatedSecondaryBackend(route)
    return route.get_backend()


def reset_simulated_secondary_devices() -> None:
    """Clear in-memory simulation state (primarily useful between test cases)."""
    _SIMULATED_STATES.clear()


__all__ = [
    "EffectiveSecondaryRoute",
    "SIMULATION_ENVIRONMENT_VARIABLE",
    "SimulatedUniformDevice",
    "acquire_secondary_device",
    "backend_for_secondary_route",
    "has_available_secondary_profile_routes",
    "iter_effective_secondary_routes",
    "reset_simulated_secondary_devices",
    "route_is_available",
    "secondary_device_simulation_enabled",
]
