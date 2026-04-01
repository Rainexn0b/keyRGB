from __future__ import annotations

from typing import Any, Callable

from src.core.backends.ite8233.backend import Ite8233Backend
from src.core.utils.exceptions import is_permission_denied
from src.core.utils.safe_attrs import safe_int_attr
from src.tray.protocols import LightingTrayProtocol
from src.tray.ui.menu_status import selected_device_context_entry

from ._lighting_controller_helpers import parse_menu_int, try_log_event


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
    if brightness_hw > 0:
        try:
            tray.config.lightbar_brightness = brightness_hw
        except Exception:
            pass
    else:
        try:
            tray.config.lightbar_brightness = 0
        except Exception:
            pass

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

    try:
        tray.config.lightbar_brightness = 0
    except Exception:
        pass

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
    except Exception as exc:
        notify = getattr(tray, "_notify_permission_issue", None)
        if is_permission_denied(exc) and callable(notify):
            try:
                notify(exc)
                return False
            except Exception:
                pass

        log_exception = getattr(tray, "_log_exception", None)
        if callable(log_exception):
            try:
                log_exception(error_msg, exc)
                return False
            except Exception:
                return False
        return False


def _refresh_menu_best_effort(tray: LightingTrayProtocol) -> None:
    update_menu = getattr(tray, "_update_menu", None)
    if callable(update_menu):
        try:
            update_menu()
        except Exception:
            pass


__all__ = [
    "apply_selected_secondary_brightness",
    "selected_secondary_backend_name",
    "selected_secondary_context_entry",
    "turn_off_selected_secondary_device",
]