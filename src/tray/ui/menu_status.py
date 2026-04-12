from __future__ import annotations

import logging
from typing import Any

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.effects.catalog import backend_hw_effect_names, detected_backend_hw_effect_names
from src.core.effects.catalog import is_forced_hardware_effect, resolve_effect_name_for_backend, strip_effect_namespace
from src.core.effects.catalog import title_for_effect
from src.core.utils.logging_utils import log_throttled
from ._device_status import backend_display_name, backend_status_suffix, format_hex_id, secondary_status_suffix


logger = logging.getLogger(__name__)
_RECOVERABLE_CONFIG_READ_EXCEPTIONS = (OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_PER_KEY_STATUS_EXCEPTIONS = (LookupError, OSError, RuntimeError, TypeError, ValueError)
_RECOVERABLE_DEVICE_AVAILABILITY_EXCEPTIONS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_RECOVERABLE_PROFILE_LOOKUP_EXCEPTIONS = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


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

    if _config_has_nonempty_per_key_colors(cfg):
        return True

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


def _config_has_nonempty_per_key_colors(cfg: Any) -> bool:
    try:
        per_key = getattr(cfg, "per_key_colors", None)
        if per_key is None:
            return False
        return len(per_key) > 0
    except AttributeError:
        return False
    except (
        _RECOVERABLE_CONFIG_READ_EXCEPTIONS + _RECOVERABLE_PER_KEY_STATUS_EXCEPTIONS
    ) as exc:  # @quality-exception exception-transparency: tray status inspection crosses arbitrary config property and __len__ implementations and must remain non-fatal
        _log_menu_debug(
            "tray.menu.per_key_colors",
            "Failed to inspect per-key colors for tray status",
            exc,
            interval_s=60,
        )
        return False


def _title(name: str) -> str:
    return title_for_effect(name)


def keyboard_status_text(tray: Any) -> str:
    """Return a single-line keyboard/device status label for the tray menu."""

    if not probe_device_available(tray):
        return "Keyboard: not detected"

    backend = getattr(tray, "backend", None)
    backend_name = str(getattr(backend, "name", "unknown"))
    display_name = backend_display_name(backend_name)
    status_suffix = backend_status_suffix(backend)

    probe = getattr(tray, "backend_probe", None)
    identifiers = getattr(probe, "identifiers", None) if probe is not None else None
    identifiers = dict(identifiers or {})

    usb_vid = identifiers.get("usb_vid")
    usb_pid = identifiers.get("usb_pid")
    if usb_vid and usb_pid:
        vid = format_hex_id(usb_vid)
        pid = format_hex_id(usb_pid)
        if vid and pid:
            return f"Keyboard: {display_name} ({vid}:{pid}){status_suffix}"

    led_name = identifiers.get("led")
    if led_name:
        return f"Keyboard: {display_name} ({led_name}){status_suffix}"

    brightness_path = identifiers.get("brightness")
    if brightness_path:
        return f"Keyboard: {display_name} ({brightness_path}){status_suffix}"

    return f"Keyboard: {display_name}{status_suffix}"


def device_context_entries(tray: Any) -> list[dict[str, str]]:
    """Return selectable device-context entries for the tray header."""

    entries = [
        {
            "key": "keyboard",
            "device_type": "keyboard",
            "status": "supported",
            "text": keyboard_status_text(tray),
        }
    ]

    payload = getattr(tray, "device_discovery", None)
    if not isinstance(payload, dict):
        return entries

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return entries

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        device_type = str(candidate.get("device_type") or "").strip().lower()
        if not device_type or device_type == "keyboard":
            continue

        usb_vid = format_hex_id(str(candidate.get("usb_vid") or ""))
        usb_pid = format_hex_id(str(candidate.get("usb_pid") or ""))
        status = str(candidate.get("status") or "").strip()
        product = str(candidate.get("product") or "").strip()

        usb_id = f" ({usb_vid}:{usb_pid})" if usb_vid and usb_pid else ""
        details = f": {product}" if product else ""
        label = device_type.replace("_", " ").title()
        key = str(candidate.get("context_key") or "").strip().lower()
        if not key:
            key = f"{device_type}:{usb_vid}:{usb_pid}" if usb_vid and usb_pid else device_type
        backend_name = ""
        probe_names = candidate.get("probe_names")
        if isinstance(probe_names, list):
            for probe_name in probe_names:
                normalized_probe_name = str(probe_name or "").strip().lower()
                if normalized_probe_name:
                    backend_name = normalized_probe_name
                    break
        entries.append(
            {
                "key": key,
                "device_type": device_type,
                "backend_name": backend_name,
                "status": status,
                "text": f"{label}{details}{usb_id}{secondary_status_suffix(status)}",
            }
        )

    return entries


def selected_device_context_key(tray: Any, *, entries: list[dict[str, str]] | None = None) -> str:
    """Return a valid selected device-context key for the tray."""

    available = entries if entries is not None else device_context_entries(tray)
    valid_keys = {str(entry.get("key") or "") for entry in available}

    current = str(getattr(tray, "selected_device_context", "keyboard") or "keyboard")
    if current in valid_keys:
        return current

    fallback = str(available[0].get("key") or "keyboard") if available else "keyboard"
    try:
        setattr(tray, "selected_device_context", fallback)
    except AttributeError:
        pass
    try:
        _cfg = getattr(tray, "config", None)
        if _cfg is not None:
            _cfg.tray_device_context = fallback
    except AttributeError:
        pass
    return fallback


def selected_device_context_entry(tray: Any) -> dict[str, str]:
    """Return the selected device-context entry for the tray."""

    entries = device_context_entries(tray)
    selected_key = selected_device_context_key(tray, entries=entries)
    for entry in entries:
        if str(entry.get("key") or "") == selected_key:
            return entry
    return entries[0] if entries else {"key": "keyboard", "device_type": "keyboard", "status": "supported"}


def secondary_device_status_texts(tray: Any) -> list[str]:
    """Return additional typed device status lines for tray display.

    Today this is used for auxiliary lighting devices such as a secondary
    lightbar controller discovered alongside the main keyboard controller.
    """

    payload = getattr(tray, "device_discovery", None)
    if not isinstance(payload, dict):
        return []

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return []

    lines: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        device_type = str(candidate.get("device_type") or "").strip().lower()
        if not device_type or device_type == "keyboard":
            continue

        usb_vid = format_hex_id(str(candidate.get("usb_vid") or ""))
        usb_pid = format_hex_id(str(candidate.get("usb_pid") or ""))
        usb_id = f" ({usb_vid}:{usb_pid})" if usb_vid and usb_pid else ""

        product = str(candidate.get("product") or "").strip()
        details = f": {product}" if product else ""

        status = str(candidate.get("status") or "").strip()
        status_suffix = secondary_status_suffix(status)
        label = device_type.replace("_", " ").title()
        lines.append(f"{label}{details}{usb_id}{status_suffix}")

    return lines


def device_context_controls_available(tray: Any, context_entry: dict[str, str]) -> bool:
    """Return whether the selected non-keyboard device has live controls."""

    device_type = str(context_entry.get("device_type") or "").strip().lower()
    if device_type == "keyboard":
        return True

    explicit = getattr(tray, "secondary_device_controls", None)
    if isinstance(explicit, dict):
        value = explicit.get(str(context_entry.get("key") or ""))
        if value is not None:
            return bool(value)

    return str(context_entry.get("status") or "").strip() == "supported"


def probe_device_available(tray: Any) -> bool:
    """Best-effort device availability probe."""

    try:
        ensure = getattr(getattr(tray, "engine", None), "_ensure_device_available", None)
        if callable(ensure):
            ensure()
    except _RECOVERABLE_DEVICE_AVAILABILITY_EXCEPTIONS as exc:  # @quality-exception exception-transparency: device availability probing crosses backend I/O and must remain non-fatal for tray status
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
        except _RECOVERABLE_PROFILE_LOOKUP_EXCEPTIONS as exc:
            _log_menu_debug(
                "tray.menu.active_profile",
                "Failed to resolve active per-key profile for tray status",
                exc,
                interval_s=60,
            )
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
    if count <= 0:
        return "Hardware Effects"
    noun = "mode" if count == 1 else "modes"
    return f"Hardware Effects ({count} {noun})"
