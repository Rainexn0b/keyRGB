from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

from ._device_status import format_hex_id, secondary_status_suffix


class DeviceContextEntry(TypedDict, total=False):
    backend_name: str
    device_type: str
    key: str
    status: str
    text: str


def secondary_device_context_entry(candidate: Mapping[str, object]) -> DeviceContextEntry | None:
    device_type = _secondary_device_type(candidate)
    if device_type is None:
        return None

    usb_vid, usb_pid = _secondary_usb_identifiers(candidate)
    status = _candidate_text(candidate, "status")
    return {
        "key": _secondary_context_key(candidate, device_type=device_type, usb_vid=usb_vid, usb_pid=usb_pid),
        "device_type": device_type,
        "backend_name": _secondary_backend_name(candidate),
        "status": status,
        "text": _secondary_device_text(
            device_type=device_type,
            product=_candidate_text(candidate, "product"),
            usb_vid=usb_vid,
            usb_pid=usb_pid,
            status=status,
        ),
    }


def secondary_device_status_text(candidate: Mapping[str, object]) -> str | None:
    device_type = _secondary_device_type(candidate)
    if device_type is None:
        return None

    usb_vid, usb_pid = _secondary_usb_identifiers(candidate)
    return _secondary_device_text(
        device_type=device_type,
        product=_candidate_text(candidate, "product"),
        usb_vid=usb_vid,
        usb_pid=usb_pid,
        status=_candidate_text(candidate, "status"),
    )


def _candidate_text(candidate: Mapping[str, object], key: str) -> str:
    return str(candidate.get(key) or "").strip()


def _secondary_backend_name(candidate: Mapping[str, object]) -> str:
    probe_names = candidate.get("probe_names")
    if not isinstance(probe_names, list):
        return ""

    for probe_name in probe_names:
        normalized_probe_name = str(probe_name or "").strip().lower()
        if normalized_probe_name:
            return normalized_probe_name
    return ""


def _secondary_context_key(
    candidate: Mapping[str, object],
    *,
    device_type: str,
    usb_vid: str,
    usb_pid: str,
) -> str:
    context_key = _candidate_text(candidate, "context_key").lower()
    if context_key:
        return context_key
    if usb_vid and usb_pid:
        return f"{device_type}:{usb_vid}:{usb_pid}"
    return device_type


def _secondary_device_text(
    *,
    device_type: str,
    product: str,
    usb_vid: str,
    usb_pid: str,
    status: str,
) -> str:
    usb_id = f" ({usb_vid}:{usb_pid})" if usb_vid and usb_pid else ""
    details = f": {product}" if product else ""
    label = device_type.replace("_", " ").title()
    return f"{label}{details}{usb_id}{secondary_status_suffix(status)}"


def _secondary_device_type(candidate: Mapping[str, object]) -> str | None:
    device_type = _candidate_text(candidate, "device_type").lower()
    if not device_type or device_type == "keyboard":
        return None
    return device_type


def _secondary_usb_identifiers(candidate: Mapping[str, object]) -> tuple[str, str]:
    return (
        format_hex_id(_candidate_text(candidate, "usb_vid")),
        format_hex_id(_candidate_text(candidate, "usb_pid")),
    )
