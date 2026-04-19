from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol, TypeAlias, cast

from src.core.backends.registry import select_backend
from src.core.secondary_device_routes import SecondaryDeviceRoute, route_for_backend_name, route_for_device_type


class _ColorCapabilitiesProtocol(Protocol):
    color: object


class _UniformColorDeviceProtocol(Protocol):
    def set_color(self, color: object, *, brightness: int) -> object: ...


class _UniformColorBackendProtocol(Protocol):
    def capabilities(self) -> object | None: ...

    def get_device(self) -> _UniformColorDeviceProtocol: ...


SelectBackendFn: TypeAlias = Callable[..., _UniformColorBackendProtocol | None]
IsDeviceBusyFn: TypeAlias = Callable[[BaseException], bool]

_BACKEND_CAPABILITY_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_BACKEND_SELECTION_ERRORS = (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError)
_DEVICE_ACQUISITION_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)

__all__ = [
    "SecondaryDeviceRoute",
    "acquire_device_best_effort",
    "probe_color_support",
    "resolve_secondary_route",
    "route_for_backend_name",
    "route_for_device_type",
    "select_backend",
    "select_backend_best_effort",
]


def resolve_secondary_route(
    *,
    target_context: str,
    requested_backend: str | None,
    route_for_backend_name_fn: Callable[[str | None], SecondaryDeviceRoute | None],
    route_for_device_type_fn: Callable[[str], SecondaryDeviceRoute | None],
) -> SecondaryDeviceRoute | None:
    route = route_for_backend_name_fn(requested_backend)
    if route is not None:
        return route

    device_type = target_context.split(":", 1)[0].strip().lower()
    if not device_type or device_type == "keyboard":
        return None
    return route_for_device_type_fn(device_type)


def select_backend_best_effort(
    secondary_route: SecondaryDeviceRoute | None,
    *,
    requested_backend: str | None,
    select_backend_fn: SelectBackendFn,
    logger: logging.Logger,
) -> _UniformColorBackendProtocol | None:
    try:
        if secondary_route is not None:
            return cast(_UniformColorBackendProtocol, secondary_route.get_backend())
        return select_backend_fn(requested=requested_backend)
    except _BACKEND_SELECTION_ERRORS:
        logger.debug(
            "Failed to select backend for the uniform color window; falling back to config-only mode",
            exc_info=True,
        )
        return None


def probe_color_support(backend: _UniformColorBackendProtocol | None, *, logger: logging.Logger) -> bool:
    if backend is None:
        return True

    try:
        caps = backend.capabilities()
        if caps is None:
            return True
        if hasattr(caps, "color"):
            return bool(cast(_ColorCapabilitiesProtocol, caps).color)
        return True
    except _BACKEND_CAPABILITY_ERRORS:
        logger.debug(
            "Failed to probe backend capabilities for the uniform color window; assuming RGB support",
            exc_info=True,
        )
        return True


def acquire_device_best_effort(
    backend: _UniformColorBackendProtocol | None,
    *,
    is_device_busy_fn: IsDeviceBusyFn,
    logger: logging.Logger,
) -> _UniformColorDeviceProtocol | None:
    if backend is None:
        return None

    try:
        return backend.get_device()
    except OSError as exc:
        if is_device_busy_fn(exc):
            logger.debug("Uniform color window is deferring to the tray-owned device handle", exc_info=True)
            return None
        logger.debug(
            "Failed to acquire a device for the uniform color window; falling back to config-only mode",
            exc_info=True,
        )
        return None
    except _DEVICE_ACQUISITION_ERRORS:
        logger.debug(
            "Failed to acquire a device for the uniform color window; falling back to config-only mode",
            exc_info=True,
        )
        return None
