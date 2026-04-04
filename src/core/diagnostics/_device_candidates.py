from __future__ import annotations

from typing import Any


def build_candidate_entry(
    *,
    usb_vid: int,
    usb_pid: int,
    manufacturer: str,
    product: str,
    device_type: str,
    status: str,
    recommended_action: str,
    matching_probes: list[dict[str, Any]],
    hidraw_devices: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "usb_vid": f"0x{usb_vid:04x}",
        "usb_pid": f"0x{usb_pid:04x}",
        "manufacturer": manufacturer,
        "product": product,
        "device_type": device_type,
        "status": status,
        "recommended_action": recommended_action,
        "probe_names": [str(p.get("name") or "") for p in matching_probes],
        "probe_stabilities": [str(p.get("stability") or "") for p in matching_probes],
        "probe_selection_reasons": [
            str(p.get("selection_reason") or "") for p in matching_probes if p.get("selection_reason")
        ],
        "hidraw_nodes": [str(h.get("devnode") or "") for h in hidraw_devices],
        "hidraw_descriptor_sizes": [
            int(h.get("report_descriptor_size"))  # type: ignore[arg-type]
            for h in hidraw_devices
            if h.get("report_descriptor_size") is not None
        ],
    }
