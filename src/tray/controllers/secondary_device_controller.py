from __future__ import annotations

import logging
from typing import Callable, Protocol

from src.core.utils.exceptions import is_permission_denied
from src.tray import secondary_device_power
from src.tray.secondary_device_routes import SecondaryDeviceRoute, route_for_context_entry
from src.tray.protocols import LightingTrayProtocol
from src.tray.ui.menu_status import DeviceContextEntry, selected_device_context_entry

from ._lighting_controller_helpers import parse_menu_int, try_log_event


logger = logging.getLogger(__name__)
_RECOVERABLE_CONFIG_ATTR_WRITE_EXCEPTIONS = (OSError, OverflowError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_RUNTIME_BOUNDARY_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


class _LightbarDeviceProtocol(Protocol):
    def set_brightness(self, brightness: int) -> None: ...

    def turn_off(self) -> None: ...


def _secondary_current_brightness(tray: LightingTrayProtocol, route: SecondaryDeviceRoute) -> int:
    return secondary_device_power.current_brightness(getattr(tray, "config", None), route)


def _secondary_restore_brightness(tray: LightingTrayProtocol, route: SecondaryDeviceRoute) -> int:
    return secondary_device_power.restore_brightness(
        tray,
        route,
        current_brightness_fn=lambda: _secondary_current_brightness(tray, route),
    )


def selected_secondary_context_entry(tray: LightingTrayProtocol) -> DeviceContextEntry | None:
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


def _selected_secondary_route(tray: LightingTrayProtocol) -> tuple[DeviceContextEntry, SecondaryDeviceRoute] | None:
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
    secondary_device_power.cache_restore_brightness(tray, route, brightness_hw)
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
    secondary_device_power.cache_restore_brightness(tray, route, _secondary_current_brightness(tray, route))

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


def turn_on_selected_secondary_device(tray: LightingTrayProtocol) -> bool:
    resolved = _selected_secondary_route(tray)
    if resolved is None:
        return False
    _entry, route = resolved

    restore_brightness = _secondary_restore_brightness(tray, route)
    secondary_device_power.cache_restore_brightness(tray, route, restore_brightness)
    _set_secondary_brightness_best_effort(
        tray,
        route,
        restore_brightness,
        error_msg=f"Failed to store {route.display_name.lower()} restore brightness: %s",
    )

    try_log_event(tray, "menu", f"turn_on_{route.device_type}")

    ok = _with_secondary_device(
        tray,
        route,
        lambda device: device.set_brightness(int(restore_brightness)),
        error_msg=f"Error turning on {route.display_name.lower()}: %s",
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
    def _apply_to_selected_device() -> None:
        device = route.get_device()
        try:
            operation(device)
        finally:
            close_fn = getattr(device, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except (OSError, RuntimeError, ValueError):
                    logger.debug("Error closing secondary device after one-shot action", exc_info=True)

    def _handle_recoverable_device_failure(exc: Exception) -> None:
        if is_permission_denied(exc):
            notified = _call_tray_callback_best_effort(
                lambda: tray._notify_permission_issue(exc),
                on_recoverable=lambda notify_exc: _log_boundary_exception(
                    tray,
                    "Failed to notify lightbar permission issue: %s",
                    notify_exc,
                ),
            )
            if notified:
                return

        _log_boundary_exception(tray, error_msg, exc)

    return _run_recoverable_runtime_boundary(
        _apply_to_selected_device,
        on_recoverable=_handle_recoverable_device_failure,
    )


def _refresh_menu_best_effort(tray: LightingTrayProtocol) -> None:
    _call_tray_callback_best_effort(
        lambda: tray._update_menu(),
        on_recoverable=lambda exc: _log_boundary_exception(
            tray,
            "Failed to refresh tray menu after lightbar action: %s",
            exc,
        ),
    )


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
            setter(
                secondary_device_power.state_key(route), int(brightness), compatibility_key=route.config_brightness_attr
            )
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


def _run_recoverable_runtime_boundary(
    action: Callable[[], None],
    *,
    on_recoverable: Callable[[Exception], None],
) -> bool:
    try:
        action()
        return True
    except _RECOVERABLE_RUNTIME_BOUNDARY_EXCEPTIONS as exc:  # @quality-exception exception-transparency: runtime tray and device seams must stay non-fatal for recoverable secondary-device failures while unexpected defects still propagate
        on_recoverable(exc)
        return False


def _call_tray_callback_best_effort(
    action: Callable[[], None],
    *,
    on_recoverable: Callable[[Exception], None],
) -> bool:
    return _run_recoverable_runtime_boundary(action, on_recoverable=on_recoverable)


def _log_boundary_exception(tray: LightingTrayProtocol, msg: str, exc: Exception) -> None:
    if _call_tray_callback_best_effort(
        lambda: tray._log_exception(msg, exc),
        on_recoverable=lambda log_exc: logger.exception(
            "Tray exception logger failed while logging secondary device boundary: %s", log_exc
        ),
    ):
        return

    _log_module_exception(msg, exc)


__all__ = [
    "apply_selected_secondary_brightness",
    "selected_secondary_backend_name",
    "selected_secondary_context_entry",
    "turn_on_selected_secondary_device",
    "turn_off_selected_secondary_device",
]
