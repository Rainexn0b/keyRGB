from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol, TypeVar, cast

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.effects.catalog import backend_hw_effect_names, detected_backend_hw_effect_names
from src.core.effects.catalog import is_forced_hardware_effect, resolve_effect_name_for_backend, strip_effect_namespace
from src.core.effects.catalog import title_for_effect
from src.core.utils.logging_utils import log_throttled

from . import _menu_status_devices


logger = logging.getLogger(__name__)
_T = TypeVar("_T")
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


_DeviceCandidate = _menu_status_devices._DeviceCandidate
DeviceContextEntry = _menu_status_devices.DeviceContextEntry
_MenuStatusDevicesTrayProtocol = _menu_status_devices._MenuStatusDevicesTrayProtocol


class _MenuStatusTrayProtocol(Protocol):
    backend: object | None
    backend_caps: object | None
    backend_probe: object | None
    config: object | None
    device_discovery: object | None
    engine: object | None
    is_off: bool
    secondary_device_controls: object | None
    selected_device_context: str


def _menu_status_tray(tray: object) -> _MenuStatusTrayProtocol:
    return cast(_MenuStatusTrayProtocol, tray)


def is_software_mode(tray: object) -> bool:
    """Return True if we're in software/per-key mode (SW effects available)."""

    tray_state = _menu_status_tray(tray)
    cfg = getattr(tray_state, "config", None)
    effect = resolve_effect_name_for_backend(
        str(getattr(cfg, "effect", "none") or "none"),
        getattr(tray_state, "backend", None),
    )
    effect_base = strip_effect_namespace(effect)

    if effect_base == "perkey" or (effect_base in SW_EFFECTS and not is_forced_hardware_effect(effect)):
        return True

    if _config_has_nonempty_per_key_colors(cfg):
        return True

    return False


def is_hardware_mode(tray: object) -> bool:
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


def _recover_menu_status_value(
    action: Callable[[], _T],
    *,
    default: _T,
    key: str,
    msg: str,
    recoverable: tuple[type[Exception], ...],
) -> _T:
    try:
        return action()
    except recoverable as exc:  # @quality-exception exception-transparency: tray menu status probes must degrade to logged defaults across recoverable config inspection and best-effort device checks
        _log_menu_debug(key, msg, exc, interval_s=60)
        return default


def _config_has_nonempty_per_key_colors(cfg: object | None) -> bool:
    try:
        per_key = _recover_menu_status_value(
            lambda: getattr(cfg, "per_key_colors", None),
            default=None,
            key="tray.menu.per_key_colors",
            msg="Failed to inspect per-key colors for tray status",
            recoverable=_RECOVERABLE_CONFIG_READ_EXCEPTIONS + _RECOVERABLE_PER_KEY_STATUS_EXCEPTIONS,
        )
        if per_key is None:
            return False
        return _recover_menu_status_value(
            lambda: len(per_key) > 0,
            default=False,
            key="tray.menu.per_key_colors",
            msg="Failed to inspect per-key colors for tray status",
            recoverable=_RECOVERABLE_PER_KEY_STATUS_EXCEPTIONS,
        )
    except AttributeError:
        return False


def _title(name: str) -> str:
    return title_for_effect(name)


def _probe_identifiers(tray: _MenuStatusDevicesTrayProtocol) -> dict[str, object]:
    return _menu_status_devices._probe_identifiers(tray)


def _normalized_device_candidate(raw_candidate: object) -> _DeviceCandidate | None:
    return _menu_status_devices._normalized_device_candidate(raw_candidate)


def _device_discovery_candidates(tray: _MenuStatusDevicesTrayProtocol) -> list[_DeviceCandidate]:
    return _menu_status_devices._device_discovery_candidates(tray)


def keyboard_status_text(tray: object) -> str:
    """Return a single-line keyboard/device status label for the tray menu."""

    return _menu_status_devices.keyboard_status_text(
        tray,
        menu_status_tray=_menu_status_tray,
        probe_device_available=probe_device_available,
        probe_identifiers=_probe_identifiers,
    )


def device_context_entries(tray: object) -> list[DeviceContextEntry]:
    """Return selectable device-context entries for the tray header."""

    return _menu_status_devices.device_context_entries(
        tray,
        menu_status_tray=_menu_status_tray,
        keyboard_status_text=keyboard_status_text,
        device_discovery_candidates=_device_discovery_candidates,
    )


def selected_device_context_key(tray: object, *, entries: list[DeviceContextEntry] | None = None) -> str:
    """Return a valid selected device-context key for the tray."""

    return _menu_status_devices.selected_device_context_key(
        tray,
        menu_status_tray=_menu_status_tray,
        device_context_entries=device_context_entries,
        entries=entries,
    )


def selected_device_context_entry(tray: object) -> DeviceContextEntry:
    """Return the selected device-context entry for the tray."""

    return _menu_status_devices.selected_device_context_entry(
        tray,
        device_context_entries=device_context_entries,
        selected_device_context_key=selected_device_context_key,
    )


def secondary_device_status_texts(tray: object) -> list[str]:
    """Return additional typed device status lines for tray display.

    Today this is used for auxiliary lighting devices such as a secondary
    lightbar controller discovered alongside the main keyboard controller.
    """

    return _menu_status_devices.secondary_device_status_texts(
        tray,
        menu_status_tray=_menu_status_tray,
        device_discovery_candidates=_device_discovery_candidates,
    )


def device_context_controls_available(tray: object, context_entry: DeviceContextEntry) -> bool:
    """Return whether the selected non-keyboard device has live controls."""

    return _menu_status_devices.device_context_controls_available(
        tray,
        context_entry,
        menu_status_tray=_menu_status_tray,
    )


def probe_device_available(tray: object) -> bool:
    """Best-effort device availability probe."""

    return _menu_status_devices.probe_device_available(
        tray,
        menu_status_tray=_menu_status_tray,
        recover_menu_status_value=_recover_menu_status_value,
        recoverable_device_availability_exceptions=_RECOVERABLE_DEVICE_AVAILABILITY_EXCEPTIONS,
    )


def tray_lighting_mode_text(tray: object) -> str:
    """Return a single-line lighting mode status for the tray menu."""

    tray_state = _menu_status_tray(tray)
    if (
        bool(getattr(tray_state, "is_off", False))
        or int(getattr(getattr(tray_state, "config", None), "brightness", 0) or 0) == 0
    ):
        return "Active: Off"

    cfg = getattr(tray_state, "config", None)
    effect = resolve_effect_name_for_backend(
        str(getattr(cfg, "effect", "none") or "none"),
        getattr(tray_state, "backend", None),
    )
    effect_base = strip_effect_namespace(effect)
    sw_mode = is_software_mode(tray)
    backend_hw_effects = frozenset(backend_hw_effect_names(getattr(tray_state, "backend", None)))

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


def hardware_effects_menu_text(tray: object) -> str:
    """Return the hardware-effects submenu label with detected count."""

    tray_state = _menu_status_tray(tray)
    caps = getattr(tray_state, "backend_caps", None)
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True
    if not hw_effects_supported:
        return "Hardware Effects"

    count = len(detected_backend_hw_effect_names(getattr(tray_state, "backend", None)))
    if count <= 0:
        return "Hardware Effects"
    noun = "mode" if count == 1 else "modes"
    return f"Hardware Effects ({count} {noun})"
