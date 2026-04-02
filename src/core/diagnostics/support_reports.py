from __future__ import annotations

import json
from typing import Any


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


def choose_issue_template(*, diagnostics: dict[str, Any] | None, discovery: dict[str, Any] | None) -> str:
    actions = discovery.get("support_actions") if isinstance(discovery, dict) else None
    if isinstance(actions, dict):
        template = str(actions.get("recommended_issue_template") or "").strip()
        if template in ISSUE_TEMPLATE_URLS:
            return template

    selected_probe = _selected_backend_probe(diagnostics)
    stability = str(selected_probe.get("stability") or "") if isinstance(selected_probe, dict) else ""
    if stability == "experimental":
        return EXPERIMENTAL_CONFIRMATION_TEMPLATE
    if stability == "validated":
        return BUG_REPORT_TEMPLATE
    return HARDWARE_SUPPORT_TEMPLATE


def build_issue_report(*, diagnostics: dict[str, Any] | None, discovery: dict[str, Any] | None) -> dict[str, Any]:
    return build_issue_report_with_evidence(diagnostics=diagnostics, discovery=discovery, supplemental_evidence=None)


def build_issue_report_with_evidence(
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    template = choose_issue_template(diagnostics=diagnostics, discovery=discovery)
    fields = _fields_for_template(
        template,
        diagnostics=diagnostics,
        discovery=discovery,
        supplemental_evidence=supplemental_evidence,
    )
    title = _title_for_template(template, diagnostics=diagnostics, discovery=discovery)
    report = {
        "template": template,
        "template_label": ISSUE_TEMPLATE_LABELS.get(template, "Issue report"),
        "issue_url": issue_url_for_template(template),
        "title": title,
        "fields": fields,
    }
    report["markdown"] = _render_issue_report_markdown(report)
    return report


def build_support_bundle_payload(
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "diagnostics": diagnostics,
        "device_discovery": discovery,
        "supplemental_evidence": supplemental_evidence,
        "issue_report": build_issue_report_with_evidence(
            diagnostics=diagnostics,
            discovery=discovery,
            supplemental_evidence=supplemental_evidence,
        ),
    }


def _fields_for_template(
    template: str,
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None,
) -> dict[str, str]:
    if template == EXPERIMENTAL_CONFIRMATION_TEMPLATE:
        return _experimental_confirmation_fields(
            diagnostics=diagnostics,
            discovery=discovery,
            supplemental_evidence=supplemental_evidence,
        )
    if template == BUG_REPORT_TEMPLATE:
        return _bug_report_fields(
            diagnostics=diagnostics,
            discovery=discovery,
            supplemental_evidence=supplemental_evidence,
        )
    return _hardware_support_fields(
        diagnostics=diagnostics,
        discovery=discovery,
        supplemental_evidence=supplemental_evidence,
    )


def _hardware_support_fields(
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None,
) -> dict[str, str]:
    selected_backend = _selected_backend_name(diagnostics, discovery)
    primary_candidate = _primary_candidate(discovery)
    candidate_label = _candidate_label(primary_candidate)
    usb_ids = _usb_ids_text(discovery, diagnostics)

    what_happened_lines = [
        f"- Selected backend: {selected_backend or 'none'}",
        f"- Candidate device: {candidate_label or 'unknown'}",
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
        "diagnostics": _json_text(diagnostics),
        "debug_logs": "Paste KEYRGB_DEBUG=1 keyrgb output here if available.",
        "lsusb": usb_ids,
    }
    capture_commands = _optional_capture_commands_text(discovery)
    if capture_commands:
        fields["extra_capture_commands"] = capture_commands
    capture_results = _supplemental_evidence_text(supplemental_evidence)
    if capture_results:
        fields["additional_evidence"] = capture_results
    return fields


def _experimental_confirmation_fields(
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
    supplemental_evidence: dict[str, Any] | None,
) -> dict[str, str]:
    selected_backend = _selected_backend_name(diagnostics, discovery)
    return {
        "backend": selected_backend or "Other experimental backend",
        "hardware": _hardware_label(diagnostics, discovery),
        "usb_id": _primary_usb_id(discovery, diagnostics),
        "confirmation": "\n".join(
            [
                f"- Experimental backends enabled via: {_experimental_enabled_text(diagnostics)}",
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
        "environment": _environment_text(diagnostics),
        "diagnostics": _json_text(diagnostics),
        "logs": "Paste KEYRGB_DEBUG=1 keyrgb output from a successful run here if available.",
        "extra_notes": _join_non_empty_sections(
            _discovery_summary_text(discovery),
            _optional_capture_commands_text(discovery, prefix="Optional deeper-evidence commands:"),
            _supplemental_evidence_text(supplemental_evidence, prefix="Collected additional evidence:"),
        ),
    }


def _bug_report_fields(
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
                f"Selected backend: {_selected_backend_name(diagnostics, discovery) or 'unknown'}",
                f"Detected hardware: {_hardware_label(diagnostics, discovery)}",
            ]
        ),
        "version": _version_text(diagnostics),
        "environment": _environment_text(diagnostics),
        "diagnostics": _json_text(diagnostics),
        "logs": _join_non_empty_sections(
            "Paste KEYRGB_DEBUG=1 keyrgb output around the failure here if available.",
            _supplemental_evidence_text(supplemental_evidence, prefix="Collected additional evidence:"),
        ),
    }


def _title_for_template(
    template: str,
    *,
    diagnostics: dict[str, Any] | None,
    discovery: dict[str, Any] | None,
) -> str:
    hardware = _hardware_label(diagnostics, discovery)
    usb_id = _primary_usb_id(discovery, diagnostics)
    selected_backend = _selected_backend_name(diagnostics, discovery)
    if template == EXPERIMENTAL_CONFIRMATION_TEMPLATE:
        return f"Experimental backend confirmation: {selected_backend or '<backend>'} on {hardware}"
    if template == BUG_REPORT_TEMPLATE:
        return f"Bug: {selected_backend or 'keyRGB'} issue on {hardware}"
    if usb_id:
        return f"Hardware support: {hardware} ({usb_id})"
    return f"Hardware support: {hardware}"


def _render_issue_report_markdown(report: dict[str, Any]) -> str:
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
            if _field_language(field_name) == "json":
                lines.append("```json")
                lines.append(text)
                lines.append("```")
            else:
                lines.append(text)

    return "\n".join(lines).rstrip() + "\n"


def _field_language(field_name: str) -> str | None:
    if field_name in {"diagnostics"}:
        return "json"
    return None


def _join_non_empty_sections(*sections: str) -> str:
    return "\n\n".join(section for section in sections if section)


def _selected_backend_probe(diagnostics: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(diagnostics, dict):
        return None
    backends = diagnostics.get("backends")
    if not isinstance(backends, dict):
        return None
    selected = str(backends.get("selected") or "")
    probes = backends.get("probes")
    if not selected or not isinstance(probes, list):
        return None
    for probe in probes:
        if isinstance(probe, dict) and str(probe.get("name") or "") == selected:
            return probe
    return None


def _selected_backend_name(diagnostics: dict[str, Any] | None, discovery: dict[str, Any] | None) -> str:
    if isinstance(discovery, dict):
        selected = str(discovery.get("selected_backend") or "").strip()
        if selected:
            return selected
    if isinstance(diagnostics, dict):
        backends = diagnostics.get("backends")
        if isinstance(backends, dict):
            selected = str(backends.get("selected") or "").strip()
            if selected:
                return selected
    return ""


def _primary_candidate(discovery: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(discovery, dict):
        return None
    candidates = discovery.get("candidates")
    if not isinstance(candidates, list):
        return None
    for preferred_status in ("unrecognized_ite", "known_dormant", "known_unavailable", "experimental_disabled"):
        for candidate in candidates:
            if isinstance(candidate, dict) and str(candidate.get("status") or "") == preferred_status:
                return candidate
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return None


def _candidate_label(candidate: dict[str, Any] | None) -> str:
    if not isinstance(candidate, dict):
        return ""
    product = str(candidate.get("product") or "").strip()
    manufacturer = str(candidate.get("manufacturer") or "").strip()
    usb_vid = str(candidate.get("usb_vid") or "").strip()
    usb_pid = str(candidate.get("usb_pid") or "").strip()
    usb_id = f"{usb_vid}:{usb_pid}" if usb_vid and usb_pid else ""
    parts = [value for value in (manufacturer, product) if value]
    if usb_id:
        parts.append(usb_id)
    return " / ".join(parts)


def _hardware_label(diagnostics: dict[str, Any] | None, discovery: dict[str, Any] | None) -> str:
    dmi = diagnostics.get("dmi") if isinstance(diagnostics, dict) else None
    if isinstance(dmi, dict):
        vendor = str(dmi.get("sys_vendor") or "").strip()
        product = str(dmi.get("product_name") or "").strip()
        if vendor and product:
            return f"{vendor} {product}"
        if product:
            return product
    candidate_label = _candidate_label(_primary_candidate(discovery))
    if candidate_label:
        return candidate_label
    return "<brand/model>"


def _primary_usb_id(discovery: dict[str, Any] | None, diagnostics: dict[str, Any] | None) -> str:
    candidate = _primary_candidate(discovery)
    if isinstance(candidate, dict):
        usb_vid = str(candidate.get("usb_vid") or "").strip()
        usb_pid = str(candidate.get("usb_pid") or "").strip()
        if usb_vid and usb_pid:
            return f"{usb_vid}:{usb_pid}"
    usb_ids = diagnostics.get("usb_ids") if isinstance(diagnostics, dict) else None
    if isinstance(usb_ids, list) and usb_ids:
        return str(usb_ids[0])
    return ""


def _usb_ids_text(discovery: dict[str, Any] | None, diagnostics: dict[str, Any] | None) -> str:
    items: list[str] = []
    if isinstance(discovery, dict):
        usb_ids = discovery.get("usb_ids")
        if isinstance(usb_ids, list):
            items.extend(str(value) for value in usb_ids if value)
    if not items and isinstance(diagnostics, dict):
        usb_ids = diagnostics.get("usb_ids")
        if isinstance(usb_ids, list):
            items.extend(str(value) for value in usb_ids if value)
    return "\n".join(dict.fromkeys(items))


def _experimental_enabled_text(diagnostics: dict[str, Any] | None) -> str:
    if not isinstance(diagnostics, dict):
        return "unknown"
    backends = diagnostics.get("backends")
    if not isinstance(backends, dict):
        return "unknown"
    selection = backends.get("selection")
    if not isinstance(selection, dict):
        return "unknown"
    enabled = selection.get("experimental_backends_enabled")
    if enabled is True:
        return "enabled"
    if enabled is False:
        return "disabled"
    return "unknown"


def _environment_text(diagnostics: dict[str, Any] | None) -> str:
    if not isinstance(diagnostics, dict):
        return "- Distro:\n- Desktop session:\n- Kernel:\n- KeyRGB version / install method:"

    system = diagnostics.get("system") if isinstance(diagnostics.get("system"), dict) else {}
    env = diagnostics.get("env") if isinstance(diagnostics.get("env"), dict) else {}
    os_release = system.get("os_release") if isinstance(system.get("os_release"), dict) else {}
    distro = str(os_release.get("PRETTY_NAME") or os_release.get("NAME") or "")
    desktop = str(env.get("XDG_CURRENT_DESKTOP") or env.get("DESKTOP_SESSION") or "")
    kernel = str(system.get("kernel_release") or "")
    version = _version_text(diagnostics)
    return "\n".join(
        [
            f"- Distro: {distro}",
            f"- Desktop session: {desktop}",
            f"- Kernel: {kernel}",
            f"- KeyRGB version / install method: {version}",
        ]
    )


def _version_text(diagnostics: dict[str, Any] | None) -> str:
    if not isinstance(diagnostics, dict):
        return "unknown"
    app = diagnostics.get("app")
    if not isinstance(app, dict):
        return "unknown"
    version = str(app.get("version") or "").strip()
    version_source = str(app.get("version_source") or "").strip()
    dist_version = str(app.get("dist_version") or "").strip()
    if version and dist_version and dist_version != version:
        return f"{version} ({version_source}; installed {dist_version})"
    if version and version_source:
        return f"{version} ({version_source})"
    if version:
        return version
    return "unknown"


def _discovery_summary_text(discovery: dict[str, Any] | None) -> str:
    if not isinstance(discovery, dict):
        return ""
    summary = discovery.get("summary")
    actions = discovery.get("support_actions")
    lines: list[str] = []
    if isinstance(summary, dict):
        lines.append(
            "Discovery summary: "
            f"candidates={summary.get('candidate_count')} supported={summary.get('supported_count')} attention={summary.get('attention_count')}"
        )
    candidate = _primary_candidate(discovery)
    if isinstance(candidate, dict):
        lines.append(f"Primary candidate: {_candidate_label(candidate)} status={candidate.get('status')}")
        descriptor_sizes = candidate.get("hidraw_descriptor_sizes")
        if isinstance(descriptor_sizes, list) and descriptor_sizes:
            lines.append("HID report descriptor sizes: " + ", ".join(str(size) for size in descriptor_sizes))
    if isinstance(actions, dict):
        for step in actions.get("next_steps") or []:
            lines.append(f"Next step: {step}")
    return "\n".join(lines)


def _optional_capture_commands_text(discovery: dict[str, Any] | None, *, prefix: str | None = None) -> str:
    if not isinstance(discovery, dict):
        return ""
    actions = discovery.get("support_actions")
    if not isinstance(actions, dict):
        return ""
    commands = actions.get("optional_capture_commands")
    if not isinstance(commands, list) or not commands:
        return ""

    lines: list[str] = []
    if prefix:
        lines.append(prefix)
    lines.extend(f"- {command}" for command in commands if str(command).strip())
    return "\n".join(lines)


def _supplemental_evidence_text(
    supplemental_evidence: dict[str, Any] | None,
    *,
    prefix: str | None = None,
) -> str:
    if not isinstance(supplemental_evidence, dict):
        return ""
    lines: list[str] = []
    has_content = False

    captures = supplemental_evidence.get("captures")
    if isinstance(captures, dict) and captures:
        if prefix and not lines:
            lines.append(prefix)
        for key, payload in captures.items():
            if not isinstance(payload, dict):
                continue
            has_content = True
            lines.append(f"[{key}]")
            command = payload.get("command")
            if isinstance(command, list) and command:
                lines.append("command: " + " ".join(str(part) for part in command))
            via = payload.get("via")
            if via:
                lines.append(f"via: {via}")
            if payload.get("returncode") is not None:
                lines.append(f"returncode: {payload.get('returncode')}")
            stdout = str(payload.get("stdout") or "").strip()
            stderr = str(payload.get("stderr") or "").strip()
            error = str(payload.get("error") or "").strip()
            if stdout:
                lines.append(stdout)
            if stderr:
                lines.append("stderr:")
                lines.append(stderr)
            if error:
                lines.append("error: " + error)
            lines.append("")

    backend_probes = supplemental_evidence.get("backend_probes")
    if isinstance(backend_probes, dict) and backend_probes:
        if prefix and not lines:
            lines.append(prefix)
        has_content = True
        lines.append("Guided backend probes:")
        for key, payload in backend_probes.items():
            if not isinstance(payload, dict):
                continue
            lines.append(f"[{key}]")
            lines.append(f"backend: {payload.get('backend')}")
            lines.append(f"effect: {payload.get('effect_name')}")
            started_at = str(payload.get("started_at") or "").strip()
            completed_at = str(payload.get("completed_at") or "").strip()
            if started_at:
                lines.append(f"started_at: {started_at}")
            if completed_at:
                lines.append(f"completed_at: {completed_at}")
            samples = payload.get("samples")
            if isinstance(samples, list) and samples:
                lines.append("samples:")
                for sample in samples:
                    if not isinstance(sample, dict):
                        continue
                    lines.append(
                        "- ui={ui_speed} payload={payload_speed} raw={raw_speed_hex}".format(
                            ui_speed=sample.get("ui_speed"),
                            payload_speed=sample.get("payload_speed"),
                            raw_speed_hex=sample.get("raw_speed_hex"),
                        )
                    )
            observation = payload.get("observation")
            if isinstance(observation, dict):
                distinct_steps = observation.get("distinct_steps")
                if distinct_steps is not None:
                    lines.append(f"distinct_steps: {distinct_steps}")
                notes = str(observation.get("notes") or "").strip()
                if notes:
                    lines.append("notes: " + notes)
            lines.append("")

    manual = supplemental_evidence.get("manual")
    if isinstance(manual, list) and manual:
        if prefix and not lines:
            lines.append(prefix)
        has_content = True
        lines.append("Remaining manual evidence:")
        for item in manual:
            if isinstance(item, dict):
                lines.append("- " + str(item.get("label") or item.get("key") or "manual step"))
    if not has_content:
        return ""
    return "\n".join(lines).strip()


def _json_text(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return "{}"
    return json.dumps(payload, indent=2, sort_keys=True)