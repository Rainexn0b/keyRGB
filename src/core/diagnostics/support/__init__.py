from __future__ import annotations

from .evidence import build_additional_evidence_plan, collect_additional_evidence
from .speed_probe import (
    ITE8291R3_SPEED_PROBE_EFFECT,
    ITE8291R3_SPEED_PROBE_KEY,
    ITE8291R3_SPEED_PROBE_UI_SPEEDS,
    ITE8910_SPEED_PROBE_EFFECT,
    ITE8910_SPEED_PROBE_KEY,
    ITE8910_SPEED_PROBE_UI_SPEEDS,
    build_backend_speed_probe_plan,
    build_backend_speed_probe_plans,
)
from .reports import (
    BUG_REPORT_TEMPLATE,
    EXPERIMENTAL_CONFIRMATION_TEMPLATE,
    HARDWARE_SUPPORT_TEMPLATE,
    ISSUE_URL,
    build_issue_report,
    build_issue_report_with_evidence,
    build_support_bundle_payload,
    choose_issue_template,
    issue_url_for_template,
)

__all__ = [
    "BUG_REPORT_TEMPLATE",
    "EXPERIMENTAL_CONFIRMATION_TEMPLATE",
    "HARDWARE_SUPPORT_TEMPLATE",
    "ISSUE_URL",
    "ITE8291R3_SPEED_PROBE_EFFECT",
    "ITE8291R3_SPEED_PROBE_KEY",
    "ITE8291R3_SPEED_PROBE_UI_SPEEDS",
    "ITE8910_SPEED_PROBE_EFFECT",
    "ITE8910_SPEED_PROBE_KEY",
    "ITE8910_SPEED_PROBE_UI_SPEEDS",
    "build_additional_evidence_plan",
    "build_backend_speed_probe_plan",
    "build_backend_speed_probe_plans",
    "build_issue_report",
    "build_issue_report_with_evidence",
    "build_support_bundle_payload",
    "choose_issue_template",
    "collect_additional_evidence",
    "issue_url_for_template",
]
