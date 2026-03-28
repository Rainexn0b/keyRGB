from __future__ import annotations

import logging
from typing import Any

from src.core.effects.catalog import HW_EFFECTS_SET as HW_EFFECTS
from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.effects.catalog import title_for_effect
from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)


def is_software_mode(tray: Any) -> bool:
    """Return True if we're in software/per-key mode (SW effects available)."""

    cfg = getattr(tray, "config", None)
    effect = str(getattr(cfg, "effect", "none") or "none")

    if effect == "perkey" or effect in SW_EFFECTS:
        return True

    try:
        per_key = getattr(cfg, "per_key_colors", None) or None
        if per_key and len(per_key) > 0:
            return True
    except Exception:
        pass

    return False


def is_hardware_mode(tray: Any) -> bool:
    """Return True if we're in hardware mode (HW effects available)."""

    return not is_software_mode(tray)


def _log_menu_debug(key: str, msg: str, exc: Exception, *, interval_s: float = 60) -> None:
    log_throttled(
        logger,
        key,
        interval_s=interval_s,
        level=logging.DEBUG,
        msg=msg,
        exc=exc,
    )


def _format_hex_id(val: str) -> str:
    s = str(val or "").strip().lower() if val is not None else ""
    if s.startswith("0x"):
        s = s[2:]
    return s


def _title(name: str) -> str:
    return title_for_effect(name)


def keyboard_status_text(tray: Any) -> str:
    """Return a single-line keyboard/device status label for the tray menu."""

    if not probe_device_available(tray):
        return "Keyboard: not detected"

    backend = getattr(tray, "backend", None)
    backend_name = str(getattr(backend, "name", "unknown"))
    display_name = backend_name
    if backend_name == "sysfs-leds":
        display_name = "Kernel Driver"
    elif backend_name == "ite8291r3":
        display_name = "ITE 8291 (USB)"

    probe = getattr(tray, "backend_probe", None)
    identifiers = getattr(probe, "identifiers", None) if probe is not None else None
    identifiers = dict(identifiers or {})

    usb_vid = identifiers.get("usb_vid")
    usb_pid = identifiers.get("usb_pid")
    if usb_vid and usb_pid:
        vid = _format_hex_id(usb_vid)
        pid = _format_hex_id(usb_pid)
        if vid and pid:
            return f"Keyboard: {display_name} ({vid}:{pid})"

    led_name = identifiers.get("led")
    if led_name:
        return f"Keyboard: {display_name} ({led_name})"

    brightness_path = identifiers.get("brightness")
    if brightness_path:
        return f"Keyboard: {display_name} ({brightness_path})"

    return f"Keyboard: {display_name}"


def probe_device_available(tray: Any) -> bool:
    """Best-effort device availability probe."""

    try:
        ensure = getattr(getattr(tray, "engine", None), "_ensure_device_available", None)
        if callable(ensure):
            ensure()
    except Exception as exc:
        _log_menu_debug(
            "tray.menu.ensure_device",
            "Failed to ensure device availability",
            exc,
            interval_s=60,
        )

    return bool(getattr(getattr(tray, "engine", None), "device_available", True))


def tray_lighting_mode_text(tray: Any) -> str:
    """Return a single-line lighting mode status for the tray menu."""

    if bool(getattr(tray, "is_off", False)) or int(getattr(getattr(tray, "config", None), "brightness", 0) or 0) == 0:
        return "Active: Off"

    cfg = getattr(tray, "config", None)
    effect = str(getattr(cfg, "effect", "none") or "none")
    sw_mode = is_software_mode(tray)

    if effect == "perkey":
        try:
            from src.core.profile import profiles

            active_profile = str(profiles.get_active_profile())
        except Exception:
            active_profile = "(unknown)"

        return f"Mode: Software ({active_profile})"

    if effect in SW_EFFECTS:
        if sw_mode:
            return f"Mode: Software + {_title(effect)}"
        return f"Mode: {_title(effect)}"

    if effect in HW_EFFECTS:
        return f"Mode: Hardware + {_title(effect)}"

    if effect == "none":
        if sw_mode:
            return "Mode: Software (static)"
        return "Mode: Hardware (uniform)"

    return f"Mode: {_title(effect)}"