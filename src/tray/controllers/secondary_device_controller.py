from __future__ import annotations

import logging
from typing import Callable, Protocol

from src.core.utils.exceptions import is_permission_denied
from src.tray.secondary_device_routes import SecondaryDeviceRoute, route_for_context_entry
from src.tray.protocols import LightingTrayProtocol
from src.tray.ui.menu_status import selected_device_context_entry

from ._lighting_controller_helpers import parse_menu_int, try_log_event


logger = logging.getLogger(__name__)
_RECOVERABLE_CONFIG_ATTR_WRITE_EXCEPTIONS = (OSError, OverflowError, RuntimeError, TypeError, ValueError)


class _LightbarDeviceProtocol(Protocol):
    def set_brightness(self, brightness: int) -> None: ...

    def turn_off(self) -> None: ...


def selected_secondary_context_entry(tray: LightingTrayProtocol) -> dict[str, str] | None:
    entry = selected_device_context_entry(tray)
    if str(entry.get("device_type") or "").strip().lower() == "keyboard":
        return None
    return entry


def selected_secondary_backend_name(tray: LightingTrayProtocol) -> str | None:
    entry = selected_secondary_context_entry(tray)
    if entry is None:
        return None
    route = route_for_context_entry(entry)
    if route is not None:
        return str(route.backend_name)
    backend_name = str(entry.get("backend_name") or "").strip().lower()
    return backend_name or None


def _selected_secondary_route(tray: LightingTrayProtocol) -> tuple[dict[str, str], SecondaryDeviceRoute] | None:
    entry = selected_secondary_context_entry(tray)
    if entry is None:
        return None
    route = route_for_context_entry(entry)
    if route is None:
        return None
    return entry, route


def apply_selected_secondary_brightness(tray: LightingTrayProtocol, item: object) -> bool:
    resolved = _selected_secondary_route(tray)
    if resolved is None:
        return False
    entry, route = resolved

    level = parse_menu_int(item)
    if level is None:
        return False

    brightness_hw = int(level) * 5
    _set_secondary_brightness_best_effort(
        tray,
        route,
        brightness_hw if brightness_hw > 0 else 0,
        error_msg=f"Failed to store {route.display_name.lower()} brightness: %s",
    )

    try_log_event(tray, "menu", f"set_{route.device_type}_brightness", new=int(brightness_hw))

    def _apply(device: _LightbarDeviceProtocol) -> None:
        if brightness_hw <= 0:
            device.turn_off()
            return
        device.set_brightness(int(brightness_hw))

    ok = _with_secondary_device(
        tray,
        route,
        _apply,
        error_msg=f"Error applying {route.display_name.lower()} brightness: %s",
    )
    if ok:
        _refresh_menu_best_effort(tray)
    return ok


def turn_off_selected_secondary_device(tray: LightingTrayProtocol) -> bool:
    resolved = _selected_secondary_route(tray)
    if resolved is None:
        return False
    _entry, route = resolved

    _set_secondary_brightness_best_effort(
        tray,
        route,
        0,
        error_msg=f"Failed to store {route.display_name.lower()} brightness: %s",
    )

    try_log_event(tray, "menu", f"turn_off_{route.device_type}")

    ok = _with_secondary_device(
        tray,
        route,
        lambda device: device.turn_off(),
        error_msg=f"Error turning off {route.display_name.lower()}: %s",
    )
    if ok:
        _refresh_menu_best_effort(tray)
    return ok


def _with_secondary_device(
    tray: LightingTrayProtocol,
    route: SecondaryDeviceRoute,
    operation: Callable[[_LightbarDeviceProtocol], None],
    *,
    error_msg: str,
) -> bool:
    try:
        device = route.get_device()
        operation(device)
        return True
    except Exception as exc:  # @quality-exception exception-transparency: runtime backend boundary; must remain non-fatal for tray actions
        if is_permission_denied(exc):
            try:
                tray._notify_permission_issue(exc)
                return False
            except Exception as notify_exc:  # @quality-exception exception-transparency: notification callback is a best-effort UI boundary; fall through to traceback logging
                _log_boundary_exception(tray, "Failed to notify lightbar permission issue: %s", notify_exc)

        _log_boundary_exception(tray, error_msg, exc)
        return False


def _refresh_menu_best_effort(tray: LightingTrayProtocol) -> None:
    try:
        tray._update_menu()
    except Exception as exc:  # @quality-exception exception-transparency: tray menu refresh is a best-effort UI boundary after a successful lightbar action
        _log_boundary_exception(tray, "Failed to refresh tray menu after lightbar action: %s", exc)


def _set_secondary_brightness_best_effort(
    tray: LightingTrayProtocol,
    route: SecondaryDeviceRoute,
    brightness: int,
    *,
    error_msg: str,
) -> None:
    config = getattr(tray, "config", None)
    if config is None:
        return

    try:
        setter = getattr(config, "set_secondary_device_brightness", None)
        if callable(setter):
            setter(str(route.state_key), int(brightness), legacy_key=route.config_brightness_attr)
            return

        attr_name = str(route.config_brightness_attr or "").strip()
        if not attr_name:
            return
        setattr(config, attr_name, int(brightness))
    except AttributeError:
        return
    except _RECOVERABLE_CONFIG_ATTR_WRITE_EXCEPTIONS as exc:
        _log_boundary_exception(tray, error_msg, exc)


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _log_boundary_exception(tray: LightingTrayProtocol, msg: str, exc: Exception) -> None:
    try:
        tray._log_exception(msg, exc)
        return
    except Exception as log_exc:  # @quality-exception exception-transparency: tray logger callback may raise arbitrary runtime errors; fallback to module logging
        logger.exception("Tray exception logger failed while logging secondary device boundary: %s", log_exc)

    _log_module_exception(msg, exc)


__all__ = [
    "apply_selected_secondary_brightness",
    "selected_secondary_backend_name",
    "selected_secondary_context_entry",
    "turn_off_selected_secondary_device",
]
