from __future__ import annotations

from typing import Any

from ._report_helpers import (
    BUG_REPORT_TEMPLATE,
    EXPERIMENTAL_CONFIRMATION_TEMPLATE,
    HARDWARE_SUPPORT_TEMPLATE,
    ISSUE_URL as _ISSUE_URL,
    ISSUE_TEMPLATE_LABELS,
    ISSUE_TEMPLATE_URLS,
    fields_for_template,
    issue_url_for_template,
    render_issue_report_markdown,
    selected_backend_probe,
    title_for_template,
)


ISSUE_URL = _ISSUE_URL


def choose_issue_template(*, diagnostics: dict[str, Any] | None, discovery: dict[str, Any] | None) -> str:
    actions = discovery.get("support_actions") if isinstance(discovery, dict) else None
    if isinstance(actions, dict):
        template = str(actions.get("recommended_issue_template") or "").strip()
        if template in ISSUE_TEMPLATE_URLS:
            return template

    selected_probe = selected_backend_probe(diagnostics)
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
    fields = fields_for_template(
        template,
        diagnostics=diagnostics,
        discovery=discovery,
        supplemental_evidence=supplemental_evidence,
    )
    title = title_for_template(template, diagnostics=diagnostics, discovery=discovery)
    report = {
        "template": template,
        "template_label": ISSUE_TEMPLATE_LABELS.get(template, "Issue report"),
        "issue_url": issue_url_for_template(template),
        "title": title,
        "fields": fields,
    }
    report["markdown"] = render_issue_report_markdown(report)
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
