from __future__ import annotations

from typing import Any

from .._device_candidates import build_candidate_entry
from ..io import parse_hex_int
from .classification import (
    candidate_device_type,
    candidate_status,
    parse_probe_usb_key,
    parse_usb_id_entry,
    support_actions,
)


def build_device_discovery_payload(
    *,
    backends: dict[str, Any],
    usb_ids: list[str],
    hidraw_devices: list[dict[str, Any]],
    usb_devices_loader,
) -> dict[str, Any]:
    probes = backends.get("probes") if isinstance(backends, dict) else None
    probe_entries = [probe for probe in probes if isinstance(probe, dict)] if isinstance(probes, list) else []

    known_by_key: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for probe in probe_entries:
        key = parse_probe_usb_key(probe, parse_hex_int=parse_hex_int)
        if key is None:
            continue
        known_by_key.setdefault(key, []).append(probe)

    usb_target_keys = {parse_usb_id_entry(value) for value in usb_ids}
    usb_targets = sorted(key for key in usb_target_keys if key is not None)
    usb_devices = usb_devices_loader(usb_targets)

    hidraw_by_key: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for dev in hidraw_devices:
        vid = parse_hex_int(dev.get("vendor_id"))  # type: ignore[arg-type]
        pid = parse_hex_int(dev.get("product_id"))  # type: ignore[arg-type]
        if vid is None or pid is None:
            continue
        hidraw_by_key.setdefault((vid, pid), []).append(dev)

    detailed_usb_keys: set[tuple[int, int]] = set()
    candidates: list[dict[str, Any]] = []

    for dev in usb_devices:
        vid = parse_hex_int(dev.get("idVendor"))
        pid = parse_hex_int(dev.get("idProduct"))
        if vid is None or pid is None:
            continue

        key = (vid, pid)
        detailed_usb_keys.add(key)
        matching_probes = known_by_key.get(key, [])
        status, action = candidate_status(matching_probes, vendor_id=vid)
        device_type = candidate_device_type(usb_key=key, probes=matching_probes)

        if status == "observed" and vid != 0x048D:
            continue

        candidates.append(
            build_candidate_entry(
                usb_vid=vid,
                usb_pid=pid,
                manufacturer=str(dev.get("manufacturer") or ""),
                product=str(dev.get("product") or ""),
                device_type=device_type,
                status=status,
                recommended_action=action,
                matching_probes=matching_probes,
                hidraw_devices=hidraw_by_key.get(key, []),
            )
        )

    for key, hidraws in sorted(hidraw_by_key.items()):
        if key in detailed_usb_keys:
            continue
        vid, pid = key
        matching_probes = known_by_key.get(key, [])
        status, action = candidate_status(matching_probes, vendor_id=vid)
        device_type = candidate_device_type(usb_key=key, probes=matching_probes)
        if status == "observed" and vid != 0x048D:
            continue
        candidates.append(
            build_candidate_entry(
                usb_vid=vid,
                usb_pid=pid,
                manufacturer="",
                product="",
                device_type=device_type,
                status=status,
                recommended_action=action,
                matching_probes=matching_probes,
                hidraw_devices=hidraws,
            )
        )

    candidates.sort(key=lambda entry: (entry.get("status") != "supported", entry.get("usb_vid"), entry.get("usb_pid")))

    return {
        "selected_backend": backends.get("selected") if isinstance(backends, dict) else None,
        "usb_ids": list(usb_ids),
        "hidraw_devices": hidraw_devices,
        "candidates": candidates,
        "summary": {
            "candidate_count": len(candidates),
            "supported_count": sum(1 for entry in candidates if entry.get("status") == "supported"),
            "attention_count": sum(1 for entry in candidates if entry.get("status") != "supported"),
        },
        "support_actions": support_actions(backends, candidates),
    }
