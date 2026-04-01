from __future__ import annotations

from typing import Any

from .collectors_backends import backend_probe_snapshot
from .hidraw import hidraw_devices_snapshot
from .io import parse_hex_int
from .support_reports import (
    BUG_REPORT_TEMPLATE,
    EXPERIMENTAL_CONFIRMATION_TEMPLATE,
    HARDWARE_SUPPORT_TEMPLATE,
    issue_url_for_template,
)
from .snapshots import usb_ids_snapshot
from .usb import usb_devices_snapshot

ITE_VENDOR_ID = 0x048D

DEVICE_TYPES_BY_USB_KEY: dict[tuple[int, int], str] = {
    (0x048D, 0x600B): "keyboard",
    (0x048D, 0x7001): "lightbar",
}


def _parse_probe_usb_key(probe: dict[str, Any]) -> tuple[int, int] | None:
    ids = probe.get("identifiers")
    if not isinstance(ids, dict):
        return None

    vid = parse_hex_int(ids.get("usb_vid"))
    pid = parse_hex_int(ids.get("usb_pid"))
    if vid is None or pid is None:
        return None
    return vid, pid


def _parse_usb_id_entry(value: object) -> tuple[int, int] | None:
    text = str(value or "").strip().lower()
    if ":" not in text:
        return None
    vid_txt, pid_txt = text.split(":", 1)
    try:
        return int(vid_txt, 16), int(pid_txt, 16)
    except Exception:
        return None


def _candidate_status(probes: list[dict[str, Any]], *, vendor_id: int) -> tuple[str, str]:
    if any(bool(p.get("available")) for p in probes):
        return "supported", "Handled by an available backend."

    if any(str(p.get("stability") or "") == "dormant" for p in probes):
        return "known_dormant", "Known backend scaffold exists, but it is intentionally dormant until protocol evidence is confirmed."

    if any(
        str(p.get("stability") or "") == "experimental" and not bool(p.get("selection_enabled", False))
        for p in probes
    ):
        return "experimental_disabled", "Experimental backend exists, but experimental backends are currently disabled."

    if probes:
        return "known_unavailable", "Recognized by keyRGB, but no usable backend is currently available on this system."

    if vendor_id == ITE_VENDOR_ID:
        return "unrecognized_ite", "Unrecognized ITE-class device. Capture a safe dump and open a support issue."

    return "observed", "Observed by the discovery scan, but not currently classified as a keyRGB RGB candidate."


def _candidate_device_type(*, usb_key: tuple[int, int], probes: list[dict[str, Any]]) -> str:
    explicit_type = DEVICE_TYPES_BY_USB_KEY.get(usb_key)
    if explicit_type:
        return explicit_type

    probe_names = {str(probe.get("name") or "").strip().lower() for probe in probes if isinstance(probe, dict)}
    if any("lightbar" in name or name == "ite8233" for name in probe_names):
        return "lightbar"
    if probe_names:
        return "keyboard"
    return "unknown"


def _selected_probe(backends: dict[str, Any]) -> dict[str, Any] | None:
    selected = str(backends.get("selected") or "")
    probes = backends.get("probes")
    if not selected or not isinstance(probes, list):
        return None
    for probe in probes:
        if isinstance(probe, dict) and str(probe.get("name") or "") == selected:
            return probe
    return None


def _primary_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    for preferred_status in ("unrecognized_ite", "known_dormant", "known_unavailable", "experimental_disabled"):
        for candidate in candidates:
            if str(candidate.get("status") or "") == preferred_status:
                return candidate
    return candidates[0] if candidates else None


def _candidate_usb_id(candidate: dict[str, Any] | None) -> str:
    if not isinstance(candidate, dict):
        return ""
    usb_vid = str(candidate.get("usb_vid") or "").strip().lower()
    usb_pid = str(candidate.get("usb_pid") or "").strip().lower()
    if not usb_vid or not usb_pid:
        return ""
    usb_vid = usb_vid.replace("0x", "")
    usb_pid = usb_pid.replace("0x", "")
    if not usb_vid or not usb_pid:
        return ""
    return f"{usb_vid}:{usb_pid}"


def _capture_commands_for_candidate(candidate: dict[str, Any] | None) -> list[str]:
    usb_id = _candidate_usb_id(candidate)
    if not usb_id:
        return []

    commands = [f"lsusb -v -d {usb_id}"]
    hidraw_nodes = candidate.get("hidraw_nodes") if isinstance(candidate, dict) else None
    descriptor_sizes = candidate.get("hidraw_descriptor_sizes") if isinstance(candidate, dict) else None
    has_hidraw = isinstance(hidraw_nodes, list) and any(str(node).strip() for node in hidraw_nodes)
    has_descriptor = isinstance(descriptor_sizes, list) and any(size is not None for size in descriptor_sizes)
    if has_hidraw and not has_descriptor:
        commands.append(f"sudo usbhid-dump -d {usb_id} -e descriptor")
    return commands


def _support_actions(backends: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    selected_probe = _selected_probe(backends) if isinstance(backends, dict) else None
    summary = {
        "recommended_issue_template": HARDWARE_SUPPORT_TEMPLATE,
        "recommended_issue_url": issue_url_for_template(HARDWARE_SUPPORT_TEMPLATE),
        "next_steps": [],
    }

    primary_candidate = _primary_candidate(candidates)
    attention_candidates = [entry for entry in candidates if str(entry.get("status") or "") != "supported"]
    if attention_candidates:
        summary["recommended_issue_template"] = HARDWARE_SUPPORT_TEMPLATE
        summary["recommended_issue_url"] = issue_url_for_template(HARDWARE_SUPPORT_TEMPLATE)
        next_steps = [
            "Run diagnostics and discovery from the tray, then attach the saved support bundle to a hardware-support issue.",
            "Include KEYRGB_DEBUG=1 logs if the tray starts but the keyboard does not respond.",
        ]
        if isinstance(primary_candidate, dict) and primary_candidate.get("hidraw_nodes"):
            descriptor_sizes = primary_candidate.get("hidraw_descriptor_sizes")
            if not isinstance(descriptor_sizes, list) or not descriptor_sizes:
                next_steps.append("If permissions allow, rerun the scan after fixing hidraw access so the report can capture the HID descriptor.")
        summary["next_steps"] = next_steps
        if isinstance(primary_candidate, dict):
            summary["primary_candidate"] = {
                "usb_vid": primary_candidate.get("usb_vid"),
                "usb_pid": primary_candidate.get("usb_pid"),
                "status": primary_candidate.get("status"),
            }
            capture_commands = _capture_commands_for_candidate(primary_candidate)
            if capture_commands:
                summary["optional_capture_commands"] = capture_commands
        return summary

    stability = str(selected_probe.get("stability") or "") if isinstance(selected_probe, dict) else ""
    if stability == "experimental":
        summary["recommended_issue_template"] = EXPERIMENTAL_CONFIRMATION_TEMPLATE
        summary["recommended_issue_url"] = issue_url_for_template(EXPERIMENTAL_CONFIRMATION_TEMPLATE)
        summary["next_steps"] = [
            "If the experimental backend works reliably, save a support bundle and file an experimental-backend-confirmation issue.",
            "Include how many reboots, launches, and resume cycles you tested.",
        ]
        return summary

    if stability == "validated":
        summary["recommended_issue_template"] = BUG_REPORT_TEMPLATE
        summary["recommended_issue_url"] = issue_url_for_template(BUG_REPORT_TEMPLATE)
        summary["next_steps"] = [
            "If supported hardware is still misbehaving, attach diagnostics to a bug report.",
            "Include KEYRGB_DEBUG=1 logs from a failing run if you can reproduce the problem.",
        ]
        return summary

    summary["next_steps"] = [
        "No unsupported RGB candidates were found in this scan.",
        "Use the debug report for current-system troubleshooting if keyRGB still is not working as expected.",
    ]
    return summary


def collect_device_discovery(*, include_usb: bool = True) -> dict[str, Any]:
    backends = backend_probe_snapshot()
    usb_ids = usb_ids_snapshot(include_usb=include_usb)
    hidraw_devices = hidraw_devices_snapshot()

    probes = backends.get("probes") if isinstance(backends, dict) else None
    probe_entries = [p for p in probes if isinstance(p, dict)] if isinstance(probes, list) else []

    known_by_key: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for probe in probe_entries:
        key = _parse_probe_usb_key(probe)
        if key is None:
            continue
        known_by_key.setdefault(key, []).append(probe)

    usb_target_keys = {_parse_usb_id_entry(value) for value in usb_ids}
    usb_targets = sorted(key for key in usb_target_keys if key is not None)
    usb_devices = usb_devices_snapshot(usb_targets)

    hidraw_by_key: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for dev in hidraw_devices:
        vid = parse_hex_int(dev.get("vendor_id"))
        pid = parse_hex_int(dev.get("product_id"))
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
        status, action = _candidate_status(matching_probes, vendor_id=vid)
        device_type = _candidate_device_type(usb_key=key, probes=matching_probes)

        if status == "observed" and vid != ITE_VENDOR_ID:
            continue

        candidates.append(
            {
                "usb_vid": f"0x{vid:04x}",
                "usb_pid": f"0x{pid:04x}",
                "manufacturer": str(dev.get("manufacturer") or ""),
                "product": str(dev.get("product") or ""),
                "device_type": device_type,
                "status": status,
                "recommended_action": action,
                "probe_names": [str(p.get("name") or "") for p in matching_probes],
                "probe_stabilities": [str(p.get("stability") or "") for p in matching_probes],
                "probe_selection_reasons": [
                    str(p.get("selection_reason") or "") for p in matching_probes if p.get("selection_reason")
                ],
                "hidraw_nodes": [str(h.get("devnode") or "") for h in hidraw_by_key.get(key, [])],
                "hidraw_descriptor_sizes": [
                    int(h.get("report_descriptor_size"))
                    for h in hidraw_by_key.get(key, [])
                    if h.get("report_descriptor_size") is not None
                ],
            }
        )

    for key, hidraws in sorted(hidraw_by_key.items()):
        if key in detailed_usb_keys:
            continue
        vid, pid = key
        matching_probes = known_by_key.get(key, [])
        status, action = _candidate_status(matching_probes, vendor_id=vid)
        device_type = _candidate_device_type(usb_key=key, probes=matching_probes)
        if status == "observed" and vid != ITE_VENDOR_ID:
            continue
        candidates.append(
            {
                "usb_vid": f"0x{vid:04x}",
                "usb_pid": f"0x{pid:04x}",
                "manufacturer": "",
                "product": "",
                "device_type": device_type,
                "status": status,
                "recommended_action": action,
                "probe_names": [str(p.get("name") or "") for p in matching_probes],
                "probe_stabilities": [str(p.get("stability") or "") for p in matching_probes],
                "probe_selection_reasons": [
                    str(p.get("selection_reason") or "") for p in matching_probes if p.get("selection_reason")
                ],
                "hidraw_nodes": [str(h.get("devnode") or "") for h in hidraws],
                "hidraw_descriptor_sizes": [
                    int(h.get("report_descriptor_size"))
                    for h in hidraws
                    if h.get("report_descriptor_size") is not None
                ],
            }
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
        "support_actions": _support_actions(backends, candidates),
    }


def format_device_discovery_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("Device discovery:")
    lines.append(f"  selected_backend: {payload.get('selected_backend')}")

    summary = payload.get("summary")
    if isinstance(summary, dict):
        lines.append(f"  candidate_count: {summary.get('candidate_count')}")
        lines.append(f"  supported_count: {summary.get('supported_count')}")
        lines.append(f"  attention_count: {summary.get('attention_count')}")

    support_actions = payload.get("support_actions")
    if isinstance(support_actions, dict):
        lines.append(f"  suggested_issue_template: {support_actions.get('recommended_issue_template')}")
        lines.append(f"  suggested_issue_url: {support_actions.get('recommended_issue_url')}")
        next_steps = support_actions.get("next_steps")
        if isinstance(next_steps, list) and next_steps:
            lines.append("Recommended next steps:")
            for step in next_steps:
                lines.append(f"  - {step}")
        capture_commands = support_actions.get("optional_capture_commands")
        if isinstance(capture_commands, list) and capture_commands:
            lines.append("Optional deeper-evidence commands:")
            for command in capture_commands:
                lines.append(f"  - {command}")

    usb_ids = payload.get("usb_ids")
    if isinstance(usb_ids, list) and usb_ids:
        lines.append("USB IDs:")
        for usb_id in usb_ids:
            lines.append(f"  - {usb_id}")

    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates:
        lines.append("Candidates:")
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            product = str(entry.get("product") or "").strip()
            label = f" {product}" if product else ""
            lines.append(
                f"  - {entry.get('usb_vid')}:{entry.get('usb_pid')}{label} type={entry.get('device_type')} status={entry.get('status')}"
            )
            action = entry.get("recommended_action")
            if action:
                lines.append(f"      next: {action}")
            probes = entry.get("probe_names")
            if isinstance(probes, list) and probes:
                lines.append(f"      probes: {', '.join(str(name) for name in probes if name)}")
            hidraw_nodes = entry.get("hidraw_nodes")
            if isinstance(hidraw_nodes, list) and hidraw_nodes:
                lines.append(f"      hidraw: {', '.join(str(path) for path in hidraw_nodes if path)}")
            descriptor_sizes = entry.get("hidraw_descriptor_sizes")
            if isinstance(descriptor_sizes, list) and descriptor_sizes:
                lines.append(
                    f"      hidraw_descriptor_sizes: {', '.join(str(size) for size in descriptor_sizes)}"
                )
            elif isinstance(hidraw_nodes, list) and hidraw_nodes:
                lines.append("      hidraw_descriptor_sizes: unavailable (check permissions and rerun if needed)")

    if not lines:
        return "(no discovery data available)"
    return "\n".join(lines)