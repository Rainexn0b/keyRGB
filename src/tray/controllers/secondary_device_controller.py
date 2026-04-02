from __future__ import annotations

import logging
from typing import Any, Callable

from src.core.backends.ite8233.backend import Ite8233Backend
from src.core.utils.exceptions import is_permission_denied
from src.tray.protocols import LightingTrayProtocol
from src.tray.ui.menu_status import selected_device_context_entry

from ._lighting_controller_helpers import parse_menu_int, try_log_event


logger = logging.getLogger(__name__)
_RECOVERABLE_CONFIG_ATTR_WRITE_EXCEPTIONS = (OSError, OverflowError, RuntimeError, TypeError, ValueError)


def selected_secondary_context_entry(tray: LightingTrayProtocol) -> dict[str, str] | None:
    entry = selected_device_context_entry(tray)
    if str(entry.get("device_type") or "").strip().lower() == "keyboard":
        return None
    return entry


def selected_secondary_backend_name(tray: LightingTrayProtocol) -> str | None:
    entry = selected_secondary_context_entry(tray)
    if entry is None:
        return None
    device_type = str(entry.get("device_type") or "").strip().lower()
    if device_type == "lightbar":
        return "ite8233"
    return None


def apply_selected_secondary_brightness(tray: LightingTrayProtocol, item: object) -> bool:
    entry = selected_secondary_context_entry(tray)
    if entry is None:
        return False

    device_type = str(entry.get("device_type") or "").strip().lower()
    if device_type != "lightbar":
        return False

    level = parse_menu_int(item)
    if level is None:
        return False

    brightness_hw = int(level) * 5
    _set_lightbar_brightness_best_effort(
        tray,
        brightness_hw if brightness_hw > 0 else 0,
        error_msg="Failed to store lightbar brightness: %s",
    )

    try_log_event(tray, "menu", "set_lightbar_brightness", new=int(brightness_hw))

    def _apply(device: Any) -> None:
        if brightness_hw <= 0:
            device.turn_off()
            return
        device.set_brightness(int(brightness_hw))

    ok = _with_lightbar_device(tray, _apply, error_msg="Error applying lightbar brightness: %s")
    if ok:
        _refresh_menu_best_effort(tray)
    return ok


def turn_off_selected_secondary_device(tray: LightingTrayProtocol) -> bool:
    entry = selected_secondary_context_entry(tray)
    if entry is None:
        return False

    device_type = str(entry.get("device_type") or "").strip().lower()
    if device_type != "lightbar":
        return False

    _set_lightbar_brightness_best_effort(tray, 0, error_msg="Failed to store lightbar brightness: %s")

    try_log_event(tray, "menu", "turn_off_lightbar")

    ok = _with_lightbar_device(tray, lambda device: device.turn_off(), error_msg="Error turning off lightbar: %s")
    if ok:
        _refresh_menu_best_effort(tray)
    return ok


def _with_lightbar_device(
    tray: LightingTrayProtocol,
    operation: Callable[[Any], None],
    *,
    error_msg: str,
) -> bool:
    try:
        device = Ite8233Backend().get_device()
        operation(device)
        return True
    # @quality-exception exception-transparency: lightbar device access crosses a runtime backend boundary and must remain non-fatal for tray actions
    except Exception as exc:
        notify = getattr(tray, "_notify_permission_issue", None)
        if is_permission_denied(exc) and callable(notify):
            try:
                notify(exc)
                return False
            # @quality-exception exception-transparency: notification callback is a best-effort UI boundary; fall through to traceback logging on failure
            except Exception as notify_exc:
                _log_boundary_exception(tray, "Failed to notify lightbar permission issue: %s", notify_exc)

        _log_boundary_exception(tray, error_msg, exc)
        return False


def _refresh_menu_best_effort(tray: LightingTrayProtocol) -> None:
    update_menu = getattr(tray, "_update_menu", None)
    if callable(update_menu):
        try:
            update_menu()
        # @quality-exception exception-transparency: tray menu refresh is a best-effort UI boundary after a successful lightbar action
        except Exception as exc:
            _log_boundary_exception(tray, "Failed to refresh tray menu after lightbar action: %s", exc)


def _set_lightbar_brightness_best_effort(
    tray: LightingTrayProtocol,
    brightness: int,
    *,
    error_msg: str,
) -> None:
    config = getattr(tray, "config", None)
    if config is None:
        return

    try:
        setattr(config, "lightbar_brightness", int(brightness))
    except AttributeError:
        return
    except _RECOVERABLE_CONFIG_ATTR_WRITE_EXCEPTIONS as exc:
        _log_boundary_exception(tray, error_msg, exc)


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _log_boundary_exception(tray: LightingTrayProtocol, msg: str, exc: Exception) -> None:
    log_exception = getattr(tray, "_log_exception", None)
    if callable(log_exception):
        try:
            log_exception(msg, exc)
            return
        # @quality-exception exception-transparency: tray logger callback may raise arbitrary runtime errors; fall back to module traceback logging
        except Exception as log_exc:
            logger.exception("Tray exception logger failed while logging secondary device boundary: %s", log_exc)

    _log_module_exception(msg, exc)


__all__ = [
    "apply_selected_secondary_brightness",
    "selected_secondary_backend_name",
    "selected_secondary_context_entry",
    "turn_off_selected_secondary_device",
]