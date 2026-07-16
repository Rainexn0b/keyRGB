from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.backends.ite8258_perkey_chassis.backend import Ite8258ChassisBackend

from src.core.backends.ite8233_none_chassis_lightbar_clevo.backend import Ite8233Backend
from src.core.backends.sysfs_mouse.backend import SysfsMouseBackend


# Brightness policies for secondary routes.
#
# ``independent``     the route owns its own brightness (e.g. a separate USB
#                     controller or sysfs LED with its own brightness file);
# ``primary_shared``  the route shares the primary keyboard/controller brightness
#                     (composite-controller zones such as Logo/Neon/Vents);
# ``unsupported``     the route has no brightness control at all (on/off + colour).
#
# See docs/I-implementation-plans/secondary-lighting-profile-editor-and-simulation-plan.md
# (Phase 1, "Route description" / "Brightness policy").
BRIGHTNESS_POLICY_INDEPENDENT = "independent"
BRIGHTNESS_POLICY_PRIMARY_SHARED = "primary_shared"
BRIGHTNESS_POLICY_UNSUPPORTED = "unsupported"
BRIGHTNESS_POLICIES = frozenset(
    {
        BRIGHTNESS_POLICY_INDEPENDENT,
        BRIGHTNESS_POLICY_PRIMARY_SHARED,
        BRIGHTNESS_POLICY_UNSUPPORTED,
    }
)


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
    # Whether this route's enabled + static-colour state is part of a lighting
    # profile (``secondary_lighting.json``). All uniform-capable routes are
    # profile-compatible by default; the Lighting areas editor and profile/static
    # scene application gate on this.
    supports_profile_state: bool = False
    # Runtime brightness behaviour. See the ``BRIGHTNESS_POLICY_*`` constants.
    brightness_policy: str = BRIGHTNESS_POLICY_UNSUPPORTED
    # Virtual zone routes share a parent backend's transport (e.g., logo/neon/vent
    # on a single composite controller). ``parent_backend_name`` names the parent
    # backend; ``zone_key`` is the sub-device identifier passed to the parent's
    # zone-device factory.
    parent_backend_name: str | None = None
    zone_key: str | None = None
    # When True, global power-off is owned by the primary keyboard path for this
    # composite controller.  Secondary global-off cleanup skips these routes so
    # child turn_off is not misused as transient shutdown after the primary has
    # already suspended output.
    primary_owns_global_off: bool = False


def _acquire_ite8233_lightbar() -> object:
    return Ite8233Backend().get_device()


def _get_ite8233_lightbar_backend() -> object:
    return Ite8233Backend()


def _acquire_sysfs_mouse() -> object:
    return SysfsMouseBackend().get_device()


def _get_sysfs_mouse_backend() -> object:
    return SysfsMouseBackend()


def _get_ite8258_chassis_backend() -> Ite8258ChassisBackend:
    from src.core.backends.ite8258_perkey_chassis.backend import Ite8258ChassisBackend

    return Ite8258ChassisBackend()


def _acquire_ite8258_chassis_zone(zone_key: str) -> Callable[[], object]:
    def _acquire() -> object:
        return _get_ite8258_chassis_backend().get_zone_device(zone_key)

    return _acquire


_ROUTES: tuple[SecondaryDeviceRoute, ...] = (
    SecondaryDeviceRoute(
        device_type="lightbar",
        backend_name="ite8233_none_chassis_lightbar_clevo",
        display_name="Lightbar",
        state_key="lightbar",
        get_backend=_get_ite8233_lightbar_backend,
        get_device=_acquire_ite8233_lightbar,
        config_brightness_attr="lightbar_brightness",
        config_color_attr="lightbar_color",
        supports_uniform_color=True,
        supports_software_target=True,
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
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
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
    ),
    # Virtual zone routes for the Lenovo Gen10 composite ITE 8258 chassis
    # controller (0x048d:0xc197). These share the keyboard's hidraw transport
    # and are surfaced as independent tray device contexts.
    SecondaryDeviceRoute(
        device_type="logo",
        backend_name="ite8258-chassis-logo",
        display_name="Logo",
        state_key="ite8258_chassis_logo",
        get_backend=_get_ite8258_chassis_backend,
        get_device=_acquire_ite8258_chassis_zone("logo"),
        config_brightness_attr="ite8258_chassis_logo_brightness",
        config_color_attr="ite8258_chassis_logo_color",
        supports_uniform_color=True,
        supports_software_target=True,
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
        parent_backend_name="ite8258_perkey_chassis",
        zone_key="logo",
        primary_owns_global_off=True,
    ),
    SecondaryDeviceRoute(
        device_type="neon",
        backend_name="ite8258-chassis-neon",
        display_name="Neon Strip",
        state_key="ite8258_chassis_neon",
        get_backend=_get_ite8258_chassis_backend,
        get_device=_acquire_ite8258_chassis_zone("neon"),
        config_brightness_attr="ite8258_chassis_neon_brightness",
        config_color_attr="ite8258_chassis_neon_color",
        supports_uniform_color=True,
        supports_software_target=True,
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
        parent_backend_name="ite8258_perkey_chassis",
        zone_key="neon",
        primary_owns_global_off=True,
    ),
    SecondaryDeviceRoute(
        device_type="vent",
        backend_name="ite8258-chassis-vent",
        display_name="Vents",
        state_key="ite8258_chassis_vent",
        get_backend=_get_ite8258_chassis_backend,
        get_device=_acquire_ite8258_chassis_zone("vent"),
        config_brightness_attr="ite8258_chassis_vent_brightness",
        config_color_attr="ite8258_chassis_vent_color",
        supports_uniform_color=True,
        supports_software_target=True,
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
        parent_backend_name="ite8258_perkey_chassis",
        zone_key="vent",
        primary_owns_global_off=True,
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


def iter_virtual_routes() -> tuple[SecondaryDeviceRoute, ...]:
    """Yield routes that are virtual zones of a composite parent backend."""
    return tuple(route for route in _ROUTES if route.parent_backend_name is not None)


def iter_secondary_routes() -> tuple[SecondaryDeviceRoute, ...]:
    """Return every registered secondary route, not only virtual-zone routes.

    Consumers that need the full effective-route catalogue (the central
    secondary-device runtime/provider, simulation, diagnostics, and the Lighting
    areas editor) must use this rather than ``iter_virtual_routes()`` so that
    standalone routes such as the Lightbar and Mouse are not silently dropped.
    """
    return _ROUTES


def iter_parent_backend_names() -> frozenset[str]:
    """Return the set of parent backend names that have virtual zone routes."""
    return frozenset(route.parent_backend_name for route in _ROUTES if route.parent_backend_name is not None)


__all__ = [
    "BRIGHTNESS_POLICIES",
    "BRIGHTNESS_POLICY_INDEPENDENT",
    "BRIGHTNESS_POLICY_PRIMARY_SHARED",
    "BRIGHTNESS_POLICY_UNSUPPORTED",
    "SecondaryDeviceRoute",
    "iter_parent_backend_names",
    "iter_secondary_routes",
    "iter_virtual_routes",
    "route_for_backend_name",
    "route_for_context_entry",
    "route_for_device_type",
]
