from __future__ import annotations

import logging
from typing import Any

from src.core.backends.policy import (
    experimental_evidence_for_backend,
    experimental_evidence_label,
    stability_for_backend,
)
from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.effects.catalog import (
    backend_hw_effect_names,
    detected_backend_hw_effect_names,
    is_forced_hardware_effect,
    resolve_effect_name_for_backend,
    strip_effect_namespace,
)
from src.core.effects.catalog import title_for_effect
from src.core.utils.logging_utils import log_throttled

logger = logging.getLogger(__name__)


def is_software_mode(tray: Any) -> bool:
    """Return True if we're in software/per-key mode (SW effects available)."""

    cfg = getattr(tray, "config", None)
    effect = resolve_effect_name_for_backend(
        str(getattr(cfg, "effect", "none") or "none"),
        getattr(tray, "backend", None),
    )
    effect_base = strip_effect_namespace(effect)

    if effect_base == "perkey" or (effect_base in SW_EFFECTS and not is_forced_hardware_effect(effect)):
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


def _backend_display_name(backend_name: str) -> str:
    if backend_name == "sysfs-leds":
        return "Kernel Driver"
    if backend_name == "ite8291r3":
        return "ITE 8291 (USB)"
    if backend_name == "ite8910":
        return "ITE 8910 (USB)"
    if backend_name == "ite8297":
        return "ITE 8297 (USB)"
    return backend_name


def _backend_status_suffix(backend: Any) -> str:
    if backend is None:
        return ""

    if stability_for_backend(backend).value != "experimental":
        return ""

    parts = ["experimental"]
    evidence_label = experimental_evidence_label(experimental_evidence_for_backend(backend))
    if evidence_label:
        parts.append(evidence_label)

    return f" [{', '.join(parts)}]"


def keyboard_status_text(tray: Any) -> str:
    """Return a single-line keyboard/device status label for the tray menu."""

    if not probe_device_available(tray):
        return "Keyboard: not detected"

    backend = getattr(tray, "backend", None)
    backend_name = str(getattr(backend, "name", "unknown"))
    display_name = _backend_display_name(backend_name)
    status_suffix = _backend_status_suffix(backend)

    probe = getattr(tray, "backend_probe", None)
    identifiers = getattr(probe, "identifiers", None) if probe is not None else None
    identifiers = dict(identifiers or {})

    usb_vid = identifiers.get("usb_vid")
    usb_pid = identifiers.get("usb_pid")
    if usb_vid and usb_pid:
        vid = _format_hex_id(usb_vid)
        pid = _format_hex_id(usb_pid)
        if vid and pid:
            return f"Keyboard: {display_name} ({vid}:{pid}){status_suffix}"

    led_name = identifiers.get("led")
    if led_name:
        return f"Keyboard: {display_name} ({led_name}){status_suffix}"

    brightness_path = identifiers.get("brightness")
    if brightness_path:
        return f"Keyboard: {display_name} ({brightness_path}){status_suffix}"

    return f"Keyboard: {display_name}{status_suffix}"


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
    effect = resolve_effect_name_for_backend(
        str(getattr(cfg, "effect", "none") or "none"),
        getattr(tray, "backend", None),
    )
    effect_base = strip_effect_namespace(effect)
    sw_mode = is_software_mode(tray)
    backend_hw_effects = frozenset(backend_hw_effect_names(getattr(tray, "backend", None)))

    if effect_base == "perkey":
        try:
            from src.core.profile import profiles

            active_profile = str(profiles.get_active_profile())
        except Exception:
            active_profile = "(unknown)"

        return f"Mode: Software ({active_profile})"

    if effect_base in SW_EFFECTS and not is_forced_hardware_effect(effect):
        if sw_mode:
            return f"Mode: Software + {_title(effect_base)}"
        return f"Mode: {_title(effect_base)}"

    if effect_base in backend_hw_effects:
        return f"Mode: Hardware + {_title(effect_base)}"

    if effect_base == "none":
        if sw_mode:
            return "Mode: Software (static)"
        return "Mode: Hardware (uniform)"

    return f"Mode: {_title(effect_base)}"


def hardware_effects_menu_text(tray: Any) -> str:
    """Return the hardware-effects submenu label with detected count."""

    caps = getattr(tray, "backend_caps", None)
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True
    if not hw_effects_supported:
        return "Hardware Effects"

    count = len(detected_backend_hw_effect_names(getattr(tray, "backend", None)))
    noun = "mode" if count == 1 else "modes"
    return f"Hardware Effects ({count} {noun})"
