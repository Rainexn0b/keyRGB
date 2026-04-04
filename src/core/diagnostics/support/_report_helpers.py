from __future__ import annotations

from typing import Any

from ._report_text import (
    discovery_summary_text,
    environment_text,
    experimental_enabled_text,
    hardware_label,
    join_non_empty_sections,
    json_text,
    optional_capture_commands_text,
    primary_candidate,
    primary_usb_id,
    selected_backend_name,
    selected_backend_probe as _selected_backend_probe,
    supplemental_evidence_text,
    usb_ids_text,
    version_text,
    candidate_label,
)


selected_backend_probe = _selected_backend_probe


ISSUE_URL = "https://github.com/Rainexn0b/keyRGB/issues/new/choose"
HARDWARE_SUPPORT_TEMPLATE = "hardware-support"
EXPERIMENTAL_CONFIRMATION_TEMPLATE = "experimental-backend-confirmation"
BUG_REPORT_TEMPLATE = "bug-report"

ISSUE_TEMPLATE_URLS = {
    HARDWARE_SUPPORT_TEMPLATE: "https://github.com/Rainexn0b/keyRGB/issues/new?template=hardware-support.yml",
    EXPERIMENTAL_CONFIRMATION_TEMPLATE: (
        "https://github.com/Rainexn0b/keyRGB/issues/new?template=experimental-backend-confirmation.yml"
    ),
    BUG_REPORT_TEMPLATE: "https://github.com/Rainexn0b/keyRGB/issues/new?template=bug-report.yml",
}

ISSUE_TEMPLATE_LABELS = {
    HARDWARE_SUPPORT_TEMPLATE: "Hardware support / diagnostics",
    EXPERIMENTAL_CONFIRMATION_TEMPLATE: "Experimental backend confirmation / promotion request",
    BUG_REPORT_TEMPLATE: "Bug report (supported hardware)",
}


def issue_url_for_template(template: str | None) -> str:
    return ISSUE_TEMPLATE_URLS.get(str(template or ""), ISSUE_URL)


def fields_for_template(
    template: str,
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None,
) -> dict[str, str]:
    if template == EXPERIMENTAL_CONFIRMATION_TEMPLATE:
        return experimental_confirmation_fields(
            diagnostics=diagnostics,
            discovery=discovery,
            supplemental_evidence=supplemental_evidence,
        )
    if template == BUG_REPORT_TEMPLATE:
        return bug_report_fields(
            diagnostics=diagnostics,
            discovery=discovery,
            supplemental_evidence=supplemental_evidence,
        )
    return hardware_support_fields(
        diagnostics=diagnostics,
        discovery=discovery,
        supplemental_evidence=supplemental_evidence,
    )


def hardware_support_fields(
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None,
) -> dict[str, str]:
    selected_backend = selected_backend_name(diagnostics, discovery)
    primary = primary_candidate(discovery)
    candidate = candidate_label(primary)
    usb_ids = usb_ids_text(discovery, diagnostics)

    what_happened_lines = [
        f"- Selected backend: {selected_backend or 'none'}",
        f"- Candidate device: {candidate or 'unknown'}",
        f"- Visible USB IDs: {usb_ids or 'none'}",
        "- Distro/DE:",
        "- Tray starts:",
        "- Uniform color works:",
        "- Brightness works:",
        "- Per-key works:",
        "- Any flicker / fighting with other tools:",
    ]

    fields = {
        "what_happened": "\n".join(what_happened_lines),
        "diagnostics": json_text(diagnostics),
        "debug_logs": "Paste KEYRGB_DEBUG=1 keyrgb output here if available.",
        "lsusb": usb_ids,
    }
    capture_commands = optional_capture_commands_text(discovery)
    if capture_commands:
        fields["extra_capture_commands"] = capture_commands
    capture_results = supplemental_evidence_text(supplemental_evidence)
    if capture_results:
        fields["additional_evidence"] = capture_results
    return fields


def experimental_confirmation_fields(
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None,
) -> dict[str, str]:
    selected_backend = selected_backend_name(diagnostics, discovery)
    return {
        "backend": selected_backend or "Other experimental backend",
        "hardware": hardware_label(diagnostics, discovery),
        "usb_id": primary_usb_id(discovery, diagnostics),
        "confirmation": "\n".join(
            [
                f"- Experimental backends enabled via: {experimental_enabled_text(diagnostics)}",
                f"- Selected backend shown by KeyRGB: {selected_backend or 'unknown'}",
                "- Uniform color works:",
                "- Brightness works:",
                "- Per-key works:",
                "- Effects tested:",
                "- Resume / reboot / relaunch behavior:",
                "- Any flicker, stale LEDs, or conflicts with other tools:",
                "- How many launches / reboots / days you tested:",
            ]
        ),
        "environment": environment_text(diagnostics),
        "diagnostics": json_text(diagnostics),
        "logs": "Paste KEYRGB_DEBUG=1 keyrgb output from a successful run here if available.",
        "extra_notes": join_non_empty_sections(
            discovery_summary_text(discovery),
            optional_capture_commands_text(discovery, prefix="Optional deeper-evidence commands:"),
            supplemental_evidence_text(supplemental_evidence, prefix="Collected additional evidence:"),
        ),
    }


def bug_report_fields(
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None,
) -> dict[str, str]:
    return {
        "summary": "\n".join(
            [
                "Steps:",
                "1. ",
                "2. ",
                "",
                "Expected:",
                "Actual:",
                "",
                f"Selected backend: {selected_backend_name(diagnostics, discovery) or 'unknown'}",
                f"Detected hardware: {hardware_label(diagnostics, discovery)}",
            ]
        ),
        "version": version_text(diagnostics),
        "environment": environment_text(diagnostics),
        "diagnostics": json_text(diagnostics),
        "logs": join_non_empty_sections(
            "Paste KEYRGB_DEBUG=1 keyrgb output around the failure here if available.",
            supplemental_evidence_text(supplemental_evidence, prefix="Collected additional evidence:"),
        ),
    }


def title_for_template(
    template: str,
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
) -> str:
    hardware = hardware_label(diagnostics, discovery)
    usb_id = primary_usb_id(discovery, diagnostics)
    selected_backend = selected_backend_name(diagnostics, discovery)
    if template == EXPERIMENTAL_CONFIRMATION_TEMPLATE:
        return f"Experimental backend confirmation: {selected_backend or '<backend>'} on {hardware}"
    if template == BUG_REPORT_TEMPLATE:
        return f"Bug: {selected_backend or 'keyRGB'} issue on {hardware}"
    if usb_id:
        return f"Hardware support: {hardware} ({usb_id})"
    return f"Hardware support: {hardware}"


def render_issue_report_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"Template: {report.get('template_label')}")
    lines.append(f"Suggested title: {report.get('title')}")
    lines.append(f"Issue URL: {report.get('issue_url')}")

    fields = report.get("fields")
    if isinstance(fields, dict) and fields:
        for field_name, value in fields.items():
            if value is None:
                continue
            text = str(value)
            lines.append("")
            lines.append(f"## {field_name}")
            if field_language(field_name) == "json":
                lines.append("```json")
                lines.append(text)
                lines.append("```")
            else:
                lines.append(text)

    return "\n".join(lines).rstrip() + "\n"


def field_language(field_name: str) -> str | None:
    if field_name in {"diagnostics"}:
        return "json"
    return None
