from __future__ import annotations

from typing import Any

from ..support.reports import (
    BUG_REPORT_TEMPLATE,
    EXPERIMENTAL_CONFIRMATION_TEMPLATE,
    HARDWARE_SUPPORT_TEMPLATE,
    issue_url_for_template,
)


ITE_VENDOR_ID = 0x048D

DEVICE_TYPES_BY_USB_KEY: dict[tuple[int, int], str] = {
    (0x048D, 0x600B): "keyboard",
    (0x048D, 0x7001): "lightbar",
}


def parse_probe_usb_key(probe: dict[str, Any], *, parse_hex_int) -> tuple[int, int] | None:
    ids = probe.get("identifiers")
    if not isinstance(ids, dict):
        return None

    vid = parse_hex_int(ids.get("usb_vid"))
    pid = parse_hex_int(ids.get("usb_pid"))
    if vid is None or pid is None:
        return None
    return vid, pid


def parse_usb_id_entry(value: object) -> tuple[int, int] | None:
    text = str(value or "").strip().lower()
    if ":" not in text:
        return None
    vid_txt, pid_txt = text.split(":", 1)
    try:
        return int(vid_txt, 16), int(pid_txt, 16)
    except ValueError:
        return None


def candidate_status(probes: list[dict[str, Any]], *, vendor_id: int) -> tuple[str, str]:
    if any(bool(p.get("available")) for p in probes):
        return "supported", "Handled by an available backend."

    if any(str(p.get("stability") or "") == "dormant" for p in probes):
        return (
            "known_dormant",
            "Known backend scaffold exists, but it is intentionally dormant until protocol evidence is confirmed.",
        )

    if any(
        str(p.get("stability") or "") == "experimental" and not bool(p.get("selection_enabled", False)) for p in probes
    ):
        return (
            "experimental_disabled",
            "Experimental backend exists, but experimental backends are currently disabled.",
        )

    if probes:
        return "known_unavailable", "Recognized by keyRGB, but no usable backend is currently available on this system."

    if vendor_id == ITE_VENDOR_ID:
        return "unrecognized_ite", "Unrecognized ITE-class device. Capture a safe dump and open a support issue."

    return "observed", "Observed by the discovery scan, but not currently classified as a keyRGB RGB candidate."


def candidate_device_type(*, usb_key: tuple[int, int], probes: list[dict[str, Any]]) -> str:
    explicit_type = DEVICE_TYPES_BY_USB_KEY.get(usb_key)
    if explicit_type:
        return explicit_type

    probe_names = {str(probe.get("name") or "").strip().lower() for probe in probes if isinstance(probe, dict)}
    if any("lightbar" in name or name == "ite8233" for name in probe_names):
        return "lightbar"
    if probe_names:
        return "keyboard"
    return "unknown"


def selected_probe(backends: dict[str, Any]) -> dict[str, Any] | None:
    selected = str(backends.get("selected") or "")
    probes = backends.get("probes")
    if not selected or not isinstance(probes, list):
        return None
    for probe in probes:
        if isinstance(probe, dict) and str(probe.get("name") or "") == selected:
            return probe
    return None


def primary_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    for preferred_status in ("unrecognized_ite", "known_dormant", "known_unavailable", "experimental_disabled"):
        for candidate in candidates:
            if str(candidate.get("status") or "") == preferred_status:
                return candidate
    return candidates[0] if candidates else None


def candidate_usb_id(candidate: dict[str, Any] | None) -> str:
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


def capture_commands_for_candidate(candidate: dict[str, Any] | None) -> list[str]:
    usb_id = candidate_usb_id(candidate)
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


def support_actions(backends: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    current_selected_probe = selected_probe(backends) if isinstance(backends, dict) else None
    summary = {
        "recommended_issue_template": HARDWARE_SUPPORT_TEMPLATE,
        "recommended_issue_url": issue_url_for_template(HARDWARE_SUPPORT_TEMPLATE),
        "next_steps": [],
    }

    lead_candidate = primary_candidate(candidates)
    attention_candidates = [entry for entry in candidates if str(entry.get("status") or "") != "supported"]
    if attention_candidates:
        next_steps = [
            "Run diagnostics and discovery from the tray, then attach the saved support bundle to a hardware-support issue.",
            "Include KEYRGB_DEBUG=1 logs if the tray starts but the keyboard does not respond.",
        ]
        if isinstance(lead_candidate, dict) and lead_candidate.get("hidraw_nodes"):
            descriptor_sizes = lead_candidate.get("hidraw_descriptor_sizes")
            if not isinstance(descriptor_sizes, list) or not descriptor_sizes:
                next_steps.append(
                    "If permissions allow, rerun the scan after fixing hidraw access so the report can capture the HID descriptor."
                )
        summary["next_steps"] = next_steps
        if isinstance(lead_candidate, dict):
            summary["primary_candidate"] = {  # type: ignore[assignment]
                "usb_vid": lead_candidate.get("usb_vid"),
                "usb_pid": lead_candidate.get("usb_pid"),
                "status": lead_candidate.get("status"),
            }
            capture_commands = capture_commands_for_candidate(lead_candidate)
            if capture_commands:
                summary["optional_capture_commands"] = capture_commands
        return summary

    stability = str(current_selected_probe.get("stability") or "") if isinstance(current_selected_probe, dict) else ""
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
