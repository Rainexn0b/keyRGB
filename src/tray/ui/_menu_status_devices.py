from __future__ import annotations

from src.core.secondary_device_runtime import EffectiveSecondaryRoute, iter_effective_secondary_routes
from src.tray.secondary_device_routes import route_for_context_entry

from . import _device_status as _devstat
from . import _menu_status_device_discovery as _discovery
from . import _menu_status_secondary_devices as _secondary

# Local short names (typing + helpers) — avoids a 15-line multi-import block.
_DeviceCandidate = _discovery.DeviceCandidate
_DeviceContextEntriesResolver = _discovery.DeviceContextEntriesResolver
_DeviceDiscoveryCandidatesResolver = _discovery.DeviceDiscoveryCandidatesResolver
_KeyboardStatusTextResolver = _discovery.KeyboardStatusTextResolver
_MenuStatusDevicesTrayProtocol = _discovery.MenuStatusDevicesTrayProtocol
_MenuStatusTrayResolver = _discovery.MenuStatusTrayResolver
_ProbeDeviceAvailableResolver = _discovery.ProbeDeviceAvailableResolver
_ProbeIdentifiersResolver = _discovery.ProbeIdentifiersResolver
_RecoverMenuStatusValue = _discovery.RecoverMenuStatusValue
_SelectedDeviceContextKeyResolver = _discovery.SelectedDeviceContextKeyResolver
DeviceContextEntry = _secondary.DeviceContextEntry


def _probe_identifiers(tray: _MenuStatusDevicesTrayProtocol) -> dict[str, object]:
    return _discovery.probe_identifiers(tray)


def _normalized_device_candidate(raw_candidate: object) -> _DeviceCandidate | None:
    return _discovery.normalized_device_candidate(raw_candidate)


def _device_discovery_candidates(tray: _MenuStatusDevicesTrayProtocol) -> list[_DeviceCandidate]:
    return _discovery.device_discovery_candidates(tray)


def keyboard_status_text(
    tray: object,
    *,
    menu_status_tray: _MenuStatusTrayResolver,
    probe_device_available: _ProbeDeviceAvailableResolver,
    probe_identifiers: _ProbeIdentifiersResolver,
) -> str:
    """Return a single-line keyboard/device status label for the tray menu."""

    tray_state = menu_status_tray(tray)
    if not probe_device_available(tray):
        return "Keyboard: not detected"

    backend = getattr(tray_state, "backend", None)
    backend_name = str(getattr(backend, "name", "unknown"))
    display_name = _devstat.backend_display_name(backend_name)
    status_suffix = _devstat.backend_status_suffix(backend)

    identifiers = probe_identifiers(tray_state)

    usb_vid = identifiers.get("usb_vid")
    usb_pid = identifiers.get("usb_pid")
    if usb_vid and usb_pid:
        vid = _devstat.format_hex_id(str(usb_vid))
        pid = _devstat.format_hex_id(str(usb_pid))
        if vid and pid:
            return f"Keyboard: {display_name} ({vid}:{pid}){status_suffix}"

    led_name = str(identifiers.get("led") or "").strip()
    if led_name:
        return f"Keyboard: {display_name} ({led_name}){status_suffix}"

    brightness_path = str(identifiers.get("brightness") or "").strip()
    if brightness_path:
        return f"Keyboard: {display_name} ({brightness_path}){status_suffix}"

    return f"Keyboard: {display_name}{status_suffix}"


def _effective_device_context_entry(
    effective: EffectiveSecondaryRoute,
    *,
    primary_identifiers: dict[str, object],
) -> DeviceContextEntry:
    label = effective.display_name
    if effective.simulated:
        label = f"{label} (simulated)"
    elif effective.route.parent_backend_name is not None:
        vid = _devstat.format_hex_id(str(primary_identifiers.get("usb_vid") or ""))
        pid = _devstat.format_hex_id(str(primary_identifiers.get("usb_pid") or ""))
        shared_id = f" {vid}:{pid}" if vid and pid else ""
        label = f"{label} (shared controller{shared_id})"
    return {
        "key": effective.backend_name,
        "device_type": effective.device_type,
        "backend_name": effective.backend_name,
        "connected": True,
        "is_virtual_area": effective.route.parent_backend_name is not None,
        "simulated": effective.simulated,
        "source": "simulation" if effective.simulated else "effective_route",
        "status": "supported",
        "text": label,
    }


def _candidate_state_keys(entries: list[DeviceContextEntry]) -> set[str]:
    state_keys: set[str] = set()
    for entry in entries:
        route = route_for_context_entry(entry)
        if route is not None:
            state_keys.add(route.state_key)
    return state_keys


def device_context_entries(
    tray: object,
    *,
    menu_status_tray: _MenuStatusTrayResolver,
    keyboard_status_text: _KeyboardStatusTextResolver,
    device_discovery_candidates: _DeviceDiscoveryCandidatesResolver,
) -> list[DeviceContextEntry]:
    """Return selectable device-context entries for the tray header."""

    tray_state = menu_status_tray(tray)
    entries: list[DeviceContextEntry] = [
        {
            "key": "keyboard",
            "connected": bool(getattr(getattr(tray_state, "engine", None), "device_available", True)),
            "device_type": "keyboard",
            "is_virtual_area": False,
            "simulated": False,
            "source": "primary",
            "status": "supported",
            "text": keyboard_status_text(tray),
        }
    ]

    for candidate in device_discovery_candidates(tray_state):
        entry = _secondary.secondary_device_context_entry(candidate)
        if entry is not None:
            entries.append(entry)

    seen_state_keys = _candidate_state_keys(entries)
    for effective in iter_effective_secondary_routes():
        if not effective.available or effective.state_key in seen_state_keys:
            continue
        entries.append(
            _effective_device_context_entry(
                effective,
                primary_identifiers=_probe_identifiers(tray_state),
            )
        )
        seen_state_keys.add(effective.state_key)

    return entries


def selected_device_context_key(
    tray: object,
    *,
    menu_status_tray: _MenuStatusTrayResolver,
    device_context_entries: _DeviceContextEntriesResolver,
    entries: list[DeviceContextEntry] | None = None,
) -> str:
    """Return a valid selected device-context key for the tray."""

    tray_state = menu_status_tray(tray)
    available = entries if entries is not None else device_context_entries(tray)
    valid_keys = {str(entry.get("key") or "") for entry in available}

    current = str(getattr(tray_state, "selected_device_context", "keyboard") or "keyboard")
    if current in valid_keys:
        return current

    fallback = str(available[0].get("key") or "keyboard") if available else "keyboard"
    try:
        setattr(tray_state, "selected_device_context", fallback)
    except AttributeError:
        pass
    try:
        cfg = getattr(tray_state, "config", None)
        if cfg is not None:
            cfg.tray_device_context = fallback
    except AttributeError:
        pass
    return fallback


def selected_device_context_entry(
    tray: object,
    *,
    device_context_entries: _DeviceContextEntriesResolver,
    selected_device_context_key: _SelectedDeviceContextKeyResolver,
) -> DeviceContextEntry:
    """Return the selected device-context entry for the tray."""

    entries = device_context_entries(tray)
    selected_key = selected_device_context_key(tray, entries=entries)
    for entry in entries:
        if str(entry.get("key") or "") == selected_key:
            return entry
    if entries:
        return entries[0]
    return {
        "key": "keyboard",
        "device_type": "keyboard",
        "status": "supported",
    }


def secondary_device_status_texts(
    tray: object,
    *,
    menu_status_tray: _MenuStatusTrayResolver,
    device_discovery_candidates: _DeviceDiscoveryCandidatesResolver,
) -> list[str]:
    """Return additional typed device status lines for tray display.

    Today this is used for auxiliary lighting devices such as a secondary
    lightbar controller discovered alongside the main keyboard controller.
    """

    tray_state = menu_status_tray(tray)
    lines: list[str] = []
    for candidate in device_discovery_candidates(tray_state):
        text = _secondary.secondary_device_status_text(candidate)
        if text is not None:
            lines.append(text)

    return lines


def device_context_controls_available(
    tray: object,
    context_entry: DeviceContextEntry,
    *,
    menu_status_tray: _MenuStatusTrayResolver,
) -> bool:
    """Return whether the selected non-keyboard device has live controls."""

    tray_state = menu_status_tray(tray)
    device_type = str(context_entry.get("device_type") or "").strip().lower()
    if device_type == "keyboard":
        return True

    explicit = getattr(tray_state, "secondary_device_controls", None)
    if isinstance(explicit, dict):
        value = explicit.get(str(context_entry.get("key") or ""))
        if value is not None:
            return bool(value)

    return str(context_entry.get("status") or "").strip() == "supported"


def probe_device_available(
    tray: object,
    *,
    menu_status_tray: _MenuStatusTrayResolver,
    recover_menu_status_value: _RecoverMenuStatusValue,
    recoverable_device_availability_exceptions: tuple[type[Exception], ...],
) -> bool:
    """Best-effort device availability probe."""

    tray_state = menu_status_tray(tray)
    ensure = recover_menu_status_value(
        lambda: getattr(getattr(tray_state, "engine", None), "_ensure_device_available", None),
        default=None,
        key="tray.menu.ensure_device",
        msg="Failed to ensure device availability",
        recoverable=recoverable_device_availability_exceptions,
    )
    if callable(ensure):
        recover_menu_status_value(
            ensure,
            default=None,
            key="tray.menu.ensure_device",
            msg="Failed to ensure device availability",
            recoverable=recoverable_device_availability_exceptions,
        )

    return bool(getattr(getattr(tray_state, "engine", None), "device_available", True))
