from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar, TypedDict

from ._device_status import (
    backend_display_name,
    backend_status_suffix,
    format_hex_id,
)
from ._menu_status_secondary_devices import (
    DeviceContextEntry,
    secondary_device_context_entry,
    secondary_device_status_text,
)


_T = TypeVar("_T")


class _DeviceCandidate(TypedDict, total=False):
    context_key: str
    device_type: str
    probe_names: list[str]
    product: str
    status: str
    usb_pid: str
    usb_vid: str


class _MenuStatusDevicesTrayProtocol(Protocol):
    backend: object | None
    backend_probe: object | None
    config: object | None
    device_discovery: object | None
    engine: object | None
    secondary_device_controls: object | None
    selected_device_context: str


class _MenuStatusTrayResolver(Protocol):
    def __call__(self, tray: object) -> _MenuStatusDevicesTrayProtocol: ...


class _ProbeDeviceAvailableResolver(Protocol):
    def __call__(self, tray: object) -> bool: ...


class _ProbeIdentifiersResolver(Protocol):
    def __call__(self, tray: _MenuStatusDevicesTrayProtocol) -> dict[str, object]: ...


class _DeviceDiscoveryCandidatesResolver(Protocol):
    def __call__(self, tray: _MenuStatusDevicesTrayProtocol) -> list[_DeviceCandidate]: ...


class _KeyboardStatusTextResolver(Protocol):
    def __call__(self, tray: object) -> str: ...


class _DeviceContextEntriesResolver(Protocol):
    def __call__(self, tray: object) -> list[DeviceContextEntry]: ...


class _SelectedDeviceContextKeyResolver(Protocol):
    def __call__(
        self,
        tray: object,
        *,
        entries: list[DeviceContextEntry] | None = None,
    ) -> str: ...


class _RecoverMenuStatusValue(Protocol):
    def __call__(
        self,
        action: Callable[[], _T],
        *,
        default: _T,
        key: str,
        msg: str,
        recoverable: tuple[type[Exception], ...],
    ) -> _T: ...


def _probe_identifiers(tray: _MenuStatusDevicesTrayProtocol) -> dict[str, object]:
    probe = getattr(tray, "backend_probe", None)
    identifiers = getattr(probe, "identifiers", None) if probe is not None else None
    return dict(identifiers or {})


def _normalized_device_candidate(raw_candidate: object) -> _DeviceCandidate | None:
    if not isinstance(raw_candidate, dict):
        return None

    candidate: _DeviceCandidate = {}

    device_type = str(raw_candidate.get("device_type") or "").strip().lower()
    if device_type:
        candidate["device_type"] = device_type

    product = str(raw_candidate.get("product") or "").strip()
    if product:
        candidate["product"] = product

    status = str(raw_candidate.get("status") or "").strip()
    if status:
        candidate["status"] = status

    usb_vid = str(raw_candidate.get("usb_vid") or "").strip()
    if usb_vid:
        candidate["usb_vid"] = usb_vid

    usb_pid = str(raw_candidate.get("usb_pid") or "").strip()
    if usb_pid:
        candidate["usb_pid"] = usb_pid

    context_key = str(raw_candidate.get("context_key") or "").strip().lower()
    if context_key:
        candidate["context_key"] = context_key

    probe_names = raw_candidate.get("probe_names")
    if isinstance(probe_names, list):
        normalized_probe_names: list[str] = []
        for probe_name in probe_names:
            normalized_probe_name = str(probe_name or "").strip().lower()
            if normalized_probe_name:
                normalized_probe_names.append(normalized_probe_name)
        if normalized_probe_names:
            candidate["probe_names"] = normalized_probe_names

    return candidate


def _device_discovery_candidates(tray: _MenuStatusDevicesTrayProtocol) -> list[_DeviceCandidate]:
    payload = getattr(tray, "device_discovery", None)
    if not isinstance(payload, dict):
        return []

    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        return []

    candidates: list[_DeviceCandidate] = []
    for raw_candidate in raw_candidates:
        candidate = _normalized_device_candidate(raw_candidate)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


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
    display_name = backend_display_name(backend_name)
    status_suffix = backend_status_suffix(backend)

    identifiers = probe_identifiers(tray_state)

    usb_vid = identifiers.get("usb_vid")
    usb_pid = identifiers.get("usb_pid")
    if usb_vid and usb_pid:
        vid = format_hex_id(str(usb_vid))
        pid = format_hex_id(str(usb_pid))
        if vid and pid:
            return f"Keyboard: {display_name} ({vid}:{pid}){status_suffix}"

    led_name = str(identifiers.get("led") or "").strip()
    if led_name:
        return f"Keyboard: {display_name} ({led_name}){status_suffix}"

    brightness_path = str(identifiers.get("brightness") or "").strip()
    if brightness_path:
        return f"Keyboard: {display_name} ({brightness_path}){status_suffix}"

    return f"Keyboard: {display_name}{status_suffix}"


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
            "device_type": "keyboard",
            "status": "supported",
            "text": keyboard_status_text(tray),
        }
    ]

    for candidate in device_discovery_candidates(tray_state):
        entry = secondary_device_context_entry(candidate)
        if entry is not None:
            entries.append(entry)

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
        text = secondary_device_status_text(candidate)
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
