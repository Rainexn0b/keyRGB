"""Tray-owned presentation snapshots for read-only menu rendering."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from src.core.power.system import get_status as observe_system_power_status
from src.core.secondary_device_runtime import iter_effective_secondary_routes

_RECOVERABLE_VIEW_SNAPSHOT_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

SYSTEM_POWER_STATUS_ATTR = "system_power_status"
EFFECTIVE_SECONDARY_ROUTES_ATTR = "effective_secondary_routes"

_CollectSystemPowerStatus = Callable[[], object | None]
_CollectEffectiveSecondaryRoutes = Callable[[], Sequence[object]]


def refresh_system_power_snapshot(
    tray: object,
    *,
    get_status: _CollectSystemPowerStatus | None = None,
) -> object | None:
    """Observe OS power mode once and store the result on ``tray``."""

    observer = observe_system_power_status if get_status is None else get_status
    try:
        status = observer()
    except _RECOVERABLE_VIEW_SNAPSHOT_ERRORS:
        status = None
    setattr(tray, SYSTEM_POWER_STATUS_ATTR, status)
    return status


def read_system_power_status(tray: object) -> object | None:
    """Return the tray-owned power-mode snapshot without querying the OS."""

    status = getattr(tray, SYSTEM_POWER_STATUS_ATTR, None)
    if status is None or not hasattr(status, "supported") or not hasattr(status, "mode"):
        return None
    return status


def refresh_effective_secondary_routes_snapshot(
    tray: object,
    *,
    collect: _CollectEffectiveSecondaryRoutes | None = None,
) -> tuple[object, ...]:
    """Probe secondary-route availability once and store the result on ``tray``."""

    collector = iter_effective_secondary_routes if collect is None else collect
    try:
        routes = tuple(collector())
    except _RECOVERABLE_VIEW_SNAPSHOT_ERRORS:
        routes = ()
    setattr(tray, EFFECTIVE_SECONDARY_ROUTES_ATTR, routes)
    return routes


def read_effective_secondary_routes(tray: object) -> tuple[object, ...]:
    """Return the tray-owned secondary-route snapshot without probing hardware."""

    payload = getattr(tray, EFFECTIVE_SECONDARY_ROUTES_ATTR, None)
    if payload is None:
        return ()
    try:
        return tuple(payload)
    except TypeError:
        return ()


def secondary_profile_routes_available(tray: object) -> bool:
    """Return whether the stored snapshot has a profile-capable secondary route."""

    for effective in read_effective_secondary_routes(tray):
        if not bool(getattr(effective, "available", False)):
            continue
        if bool(getattr(getattr(effective, "route", None), "supports_profile_state", False)):
            return True
    return False


def refresh_tray_view_snapshots(tray: object) -> None:
    """Refresh every presentation snapshot the tray menu is allowed to read."""

    refresh_system_power_snapshot(tray)
    refresh_effective_secondary_routes_snapshot(tray)
