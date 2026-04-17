#!/usr/bin/env python3

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Protocol, TypeAlias, cast

from ._support_window_text_io import (
    _ConfigurableWidget,
    _SupportWindowOutputLike,
    _TextWidget,
    copy_text as copy_text,
    save_text_via_dialog as save_text_via_dialog,
    set_status as set_status,
    set_text as set_text,
)

JsonDict: TypeAlias = dict[str, object]
CapturePlanFn: TypeAlias = Callable[[], JsonDict]
BackendSpeedProbePlanFn: TypeAlias = Callable[[], JsonDict | None]
CanRunBackendSpeedProbeFn: TypeAlias = Callable[[], bool]


class _MessageBoxLike(Protocol):
    def askyesno(self, title: str, message: str, parent: object | None = None) -> object: ...


class _ParsedJsonFn(Protocol):
    def __call__(self, text: str) -> JsonDict | None: ...


class _BuildAdditionalEvidencePlanFn(Protocol):
    def __call__(self, discovery: JsonDict | None) -> JsonDict: ...


class _BuildBackendSpeedProbePlanFn(Protocol):
    def __call__(self, backend_name: object) -> JsonDict | None: ...


class _BuildIssueReportWithEvidenceFn(Protocol):
    def __call__(
        self,
        *,
        diagnostics: JsonDict | None,
        discovery: JsonDict | None,
        supplemental_evidence: JsonDict | None,
    ) -> JsonDict: ...


class _SupportWindowLike(_SupportWindowOutputLike, Protocol):
    _diagnostics_json: str
    _discovery_json: str
    _supplemental_evidence: JsonDict | None
    _issue_report: JsonDict | None
    _capture_prompt_key: str
    _backend_probe_prompt_key: str
    issue_meta_label: _ConfigurableWidget
    status_label: _ConfigurableWidget
    txt_issue: _TextWidget
    btn_copy_debug: _ConfigurableWidget
    btn_copy_discovery: _ConfigurableWidget
    btn_save_debug: _ConfigurableWidget
    btn_save_discovery: _ConfigurableWidget
    btn_copy_issue: _ConfigurableWidget
    btn_save_issue: _ConfigurableWidget
    btn_open_issue: _ConfigurableWidget
    btn_collect_evidence: _ConfigurableWidget
    btn_save_bundle: _ConfigurableWidget
    btn_run_speed_probe: _ConfigurableWidget

    def _set_text(self, widget: _TextWidget, text: str) -> None: ...

    def _set_status(self, text: str, *, ok: bool = True) -> None: ...

    def collect_missing_evidence(self, *, prompt: bool = True) -> None: ...

    def run_backend_speed_probe(self, *, prompt: bool = True) -> None: ...


def _support_window(window: object) -> _SupportWindowLike:
    return cast(_SupportWindowLike, window)


def _json_dict(value: object) -> JsonDict | None:
    return value if isinstance(value, dict) else None


def _selected_backend_name(*, discovery: JsonDict | None, diagnostics: JsonDict | None) -> str:
    if isinstance(discovery, dict):
        selected_backend = str(discovery.get("selected_backend") or "").strip().lower()
        if selected_backend:
            return selected_backend

    backends = _json_dict(diagnostics.get("backends")) if isinstance(diagnostics, dict) else None
    return str(backends.get("selected") or "").strip().lower() if isinstance(backends, dict) else ""


def _guided_speed_probe_plan(diagnostics: JsonDict | None) -> JsonDict | None:
    backends = _json_dict(diagnostics.get("backends")) if isinstance(diagnostics, dict) else None
    plans = backends.get("guided_speed_probes") if isinstance(backends, dict) else None
    if not isinstance(plans, list):
        return None

    for plan in plans:
        plan_dict = _json_dict(plan)
        if plan_dict is not None:
            return plan_dict
    return None


def parsed_json(text: str) -> JsonDict | None:
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def current_capture_plan(
    window: object,
    *,
    build_additional_evidence_plan: _BuildAdditionalEvidencePlanFn,
    parsed_json_fn: _ParsedJsonFn,
) -> JsonDict:
    support_window = _support_window(window)
    return build_additional_evidence_plan(parsed_json_fn(support_window._discovery_json))


def current_backend_speed_probe_plan(
    window: object,
    *,
    build_backend_speed_probe_plan: _BuildBackendSpeedProbePlanFn,
    parsed_json_fn: _ParsedJsonFn,
) -> JsonDict | None:
    support_window = _support_window(window)
    diagnostics = parsed_json_fn(support_window._diagnostics_json)
    guided_plan = _guided_speed_probe_plan(diagnostics)
    if guided_plan is not None:
        return guided_plan

    discovery = parsed_json_fn(support_window._discovery_json)
    backend_name = _selected_backend_name(discovery=discovery, diagnostics=diagnostics)
    if not backend_name:
        return None

    plan = build_backend_speed_probe_plan(backend_name)
    return plan if isinstance(plan, dict) else None


def refresh_issue_report(
    window: object,
    *,
    parsed_json_fn: _ParsedJsonFn,
    build_issue_report_with_evidence: _BuildIssueReportWithEvidenceFn,
    issue_url: str,
) -> None:
    support_window = _support_window(window)
    diagnostics = parsed_json_fn(support_window._diagnostics_json)
    discovery = parsed_json_fn(support_window._discovery_json)
    if diagnostics is None and discovery is None:
        support_window._issue_report = None
        support_window.issue_meta_label.configure(text="Suggested template: run diagnostics or discovery first")
        support_window._set_text(
            support_window.txt_issue,
            "Run diagnostics or discovery to generate a suggested issue draft and the recommended GitHub form.\n",
        )
        return
    support_window._issue_report = build_issue_report_with_evidence(
        diagnostics=diagnostics,
        discovery=discovery,
        supplemental_evidence=support_window._supplemental_evidence
        if isinstance(support_window._supplemental_evidence, dict)
        else None,
    )
    template_label = str(support_window._issue_report.get("template_label") or "Issue report")
    resolved_issue_url = str(support_window._issue_report.get("issue_url") or issue_url)
    support_window.issue_meta_label.configure(
        text=f"Suggested template: {template_label}\nIssue URL: {resolved_issue_url}"
    )
    support_window._set_text(support_window.txt_issue, str(support_window._issue_report.get("markdown") or ""))


def maybe_prompt_for_missing_evidence(
    window: object,
    *,
    current_capture_plan_fn: CapturePlanFn,
    messagebox: _MessageBoxLike,
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    support_window = _support_window(window)
    plan = current_capture_plan_fn()
    automated = plan.get("automated") if isinstance(plan, dict) else None
    if not isinstance(automated, list) or not automated:
        return

    usb_id = str(plan.get("usb_id") or "")
    prompt_key = usb_id + ":" + ",".join(str(item.get("key") or "") for item in automated if isinstance(item, dict))
    if not prompt_key or prompt_key == support_window._capture_prompt_key:
        return
    support_window._capture_prompt_key = prompt_key

    needs_privileged = any(bool(item.get("requires_root")) for item in automated if isinstance(item, dict))
    message = "KeyRGB can collect additional evidence for this unsupported device now."
    if needs_privileged:
        message += " This may prompt for an administrator password to run read-only capture tools."
    message += "\n\nCollect missing evidence now?"

    try:
        ok = bool(messagebox.askyesno("Collect Missing Evidence", message, parent=support_window.root))
    except tk_runtime_errors:
        ok = False
    if ok:
        support_window.collect_missing_evidence(prompt=False)


def maybe_prompt_for_backend_speed_probe(
    window: object,
    *,
    current_backend_speed_probe_plan_fn: BackendSpeedProbePlanFn,
    can_run_backend_speed_probe_fn: CanRunBackendSpeedProbeFn,
    messagebox: _MessageBoxLike,
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    support_window = _support_window(window)
    plan = current_backend_speed_probe_plan_fn()
    if not isinstance(plan, dict) or not bool(can_run_backend_speed_probe_fn()):
        return

    prompt_key = str(plan.get("key") or "") + ":" + str(plan.get("backend") or "")
    if not prompt_key or prompt_key == support_window._backend_probe_prompt_key:
        return
    support_window._backend_probe_prompt_key = prompt_key

    message = (
        "KeyRGB can guide a backend speed probe for this device now.\n\n"
        "This will temporarily switch the tray to the probe effect, step through the test speeds automatically, restore the previous tray effect, and save your notes into the support bundle.\n\n"
        "Run the probe now?"
    )
    try:
        ok = bool(messagebox.askyesno("Run Backend Speed Probe", message, parent=support_window.root))
    except tk_runtime_errors:
        ok = False
    if ok:
        support_window.run_backend_speed_probe(prompt=False)


def sync_button_state(
    window: object,
    *,
    current_capture_plan_fn: CapturePlanFn,
    current_backend_speed_probe_plan_fn: BackendSpeedProbePlanFn,
    can_run_backend_speed_probe_fn: CanRunBackendSpeedProbeFn,
) -> None:
    support_window = _support_window(window)
    support_window.btn_copy_debug.configure(state="normal" if support_window._diagnostics_json else "disabled")
    support_window.btn_copy_discovery.configure(state="normal" if support_window._discovery_json else "disabled")
    support_window.btn_save_debug.configure(state="normal" if support_window._diagnostics_json else "disabled")
    support_window.btn_save_discovery.configure(state="normal" if support_window._discovery_json else "disabled")
    plan = current_capture_plan_fn()
    has_capture_plan = bool(plan.get("automated"))
    issue_state = (
        "normal" if support_window._issue_report and support_window._issue_report.get("markdown") else "disabled"
    )
    support_window.btn_copy_issue.configure(state=issue_state)
    support_window.btn_save_issue.configure(state=issue_state)
    support_window.btn_open_issue.configure(state=issue_state)
    support_window.btn_collect_evidence.configure(state="normal" if has_capture_plan else "disabled")
    support_window.btn_save_bundle.configure(
        state="normal" if (support_window._diagnostics_json or support_window._discovery_json) else "disabled"
    )
    support_window.btn_run_speed_probe.configure(
        state=(
            "normal"
            if isinstance(current_backend_speed_probe_plan_fn(), dict) and bool(can_run_backend_speed_probe_fn())
            else "disabled"
        )
    )


def merge_supplemental_evidence(window: object, payload: JsonDict | None) -> None:
    support_window = _support_window(window)
    if not isinstance(payload, dict):
        return
    base = (
        dict(support_window._supplemental_evidence) if isinstance(support_window._supplemental_evidence, dict) else {}
    )
    for key, value in payload.items():
        existing_value = _json_dict(base.get(key))
        if isinstance(value, dict) and existing_value is not None:
            merged = dict(existing_value)
            merged.update(value)
            base[key] = merged
        else:
            base[key] = value
    support_window._supplemental_evidence = base
