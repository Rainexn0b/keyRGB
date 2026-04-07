from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from src.core.backends.ite8233.backend import Ite8233Backend
from src.core.backends.sysfs_mouse.backend import SysfsMouseBackend


@dataclass(frozen=True)
class SecondaryDeviceRoute:
    device_type: str
    backend_name: str
    display_name: str
    state_key: str
    get_backend: Callable[[], Any]
    get_device: Callable[[], Any]
    config_brightness_attr: str | None = None
    config_color_attr: str | None = None
    supports_uniform_color: bool = False
    supports_software_target: bool = False


def _acquire_ite8233_lightbar() -> object:
    return Ite8233Backend().get_device()


def _get_ite8233_lightbar_backend() -> object:
    return Ite8233Backend()


def _acquire_sysfs_mouse() -> object:
    return SysfsMouseBackend().get_device()


def _get_sysfs_mouse_backend() -> object:
    return SysfsMouseBackend()


_ROUTES: tuple[SecondaryDeviceRoute, ...] = (
    SecondaryDeviceRoute(
        device_type="lightbar",
        backend_name="ite8233",
        display_name="Lightbar",
        state_key="lightbar",
        get_backend=_get_ite8233_lightbar_backend,
        get_device=_acquire_ite8233_lightbar,
        config_brightness_attr="lightbar_brightness",
        config_color_attr="lightbar_color",
        supports_uniform_color=True,
        supports_software_target=True,
    ),
    SecondaryDeviceRoute(
        device_type="mouse",
        backend_name="sysfs-mouse",
        display_name="Mouse",
        state_key="mouse",
        get_backend=_get_sysfs_mouse_backend,
        get_device=_acquire_sysfs_mouse,
        supports_uniform_color=True,
        supports_software_target=True,
    ),
)

_ROUTES_BY_DEVICE_TYPE = {route.device_type: route for route in _ROUTES}
_ROUTES_BY_BACKEND_NAME = {route.backend_name: route for route in _ROUTES}


def route_for_device_type(device_type: object) -> SecondaryDeviceRoute | None:
    normalized = str(device_type or "").strip().lower()
    if not normalized:
        return None
    return _ROUTES_BY_DEVICE_TYPE.get(normalized)


def route_for_backend_name(backend_name: object) -> SecondaryDeviceRoute | None:
    normalized = str(backend_name or "").strip().lower()
    if not normalized:
        return None
    return _ROUTES_BY_BACKEND_NAME.get(normalized)


def route_for_context_entry(context_entry: Mapping[str, object] | None) -> SecondaryDeviceRoute | None:
    if not isinstance(context_entry, Mapping):
        return None

    route = route_for_backend_name(context_entry.get("backend_name"))
    if route is not None:
        return route
    return route_for_device_type(context_entry.get("device_type"))


__all__ = [
    "SecondaryDeviceRoute",
    "route_for_backend_name",
    "route_for_context_entry",
    "route_for_device_type",
]