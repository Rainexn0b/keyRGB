"""Device-candidate discovery and menu-status typing for tray device rows.

Extracted from ``_menu_status_devices.py`` (WS1 / B3 slice 1).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar, TypedDict


_T = TypeVar("_T")


class DeviceCandidate(TypedDict, total=False):
    context_key: str
    device_type: str
    probe_names: list[str]
    product: str
    status: str
    usb_pid: str
    usb_vid: str


# Backward-compatible private alias used by the parent module.
_DeviceCandidate = DeviceCandidate


class MenuStatusDevicesTrayProtocol(Protocol):
    backend: object | None
    backend_probe: object | None
    config: object | None
    device_discovery: object | None
    engine: object | None
    secondary_device_controls: object | None
    selected_device_context: str


_MenuStatusDevicesTrayProtocol = MenuStatusDevicesTrayProtocol


class MenuStatusTrayResolver(Protocol):
    def __call__(self, tray: object) -> MenuStatusDevicesTrayProtocol: ...


_MenuStatusTrayResolver = MenuStatusTrayResolver


class ProbeDeviceAvailableResolver(Protocol):
    def __call__(self, tray: object) -> bool: ...


_ProbeDeviceAvailableResolver = ProbeDeviceAvailableResolver


class ProbeIdentifiersResolver(Protocol):
    def __call__(self, tray: MenuStatusDevicesTrayProtocol) -> dict[str, object]: ...


_ProbeIdentifiersResolver = ProbeIdentifiersResolver


class DeviceDiscoveryCandidatesResolver(Protocol):
    def __call__(self, tray: MenuStatusDevicesTrayProtocol) -> list[DeviceCandidate]: ...


_DeviceDiscoveryCandidatesResolver = DeviceDiscoveryCandidatesResolver


class KeyboardStatusTextResolver(Protocol):
    def __call__(self, tray: object) -> str: ...


_KeyboardStatusTextResolver = KeyboardStatusTextResolver


class DeviceContextEntriesResolver(Protocol):
    def __call__(self, tray: object) -> list: ...


_DeviceContextEntriesResolver = DeviceContextEntriesResolver


class SelectedDeviceContextKeyResolver(Protocol):
    def __call__(
        self,
        tray: object,
        *,
        entries: list | None = None,
    ) -> str: ...


_SelectedDeviceContextKeyResolver = SelectedDeviceContextKeyResolver


class RecoverMenuStatusValue(Protocol):
    def __call__(
        self,
        action: Callable[[], _T],
        *,
        default: _T,
        key: str,
        msg: str,
        recoverable: tuple[type[Exception], ...],
    ) -> _T: ...


_RecoverMenuStatusValue = RecoverMenuStatusValue


def probe_identifiers(tray: MenuStatusDevicesTrayProtocol) -> dict[str, object]:
    probe = getattr(tray, "backend_probe", None)
    identifiers = getattr(probe, "identifiers", None) if probe is not None else None
    return dict(identifiers or {})


def normalized_device_candidate(raw_candidate: object) -> DeviceCandidate | None:
    if not isinstance(raw_candidate, dict):
        return None

    candidate: DeviceCandidate = {}

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


def device_discovery_candidates(tray: MenuStatusDevicesTrayProtocol) -> list[DeviceCandidate]:
    payload = getattr(tray, "device_discovery", None)
    if not isinstance(payload, dict):
        return []

    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        return []

    candidates: list[DeviceCandidate] = []
    for raw_candidate in raw_candidates:
        candidate = normalized_device_candidate(raw_candidate)
        if candidate is not None:
            candidates.append(candidate)
    return candidates
