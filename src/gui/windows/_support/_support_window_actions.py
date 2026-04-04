#!/usr/bin/env python3

from __future__ import annotations

import json
from typing import Any


def parsed_json(text: str) -> dict[str, object] | None:
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def current_capture_plan(window: Any, *, build_additional_evidence_plan: Any, parsed_json_fn: Any) -> dict[str, object]:
    return build_additional_evidence_plan(parsed_json_fn(window._discovery_json))


def current_backend_speed_probe_plan(
    window: Any,
    *,
    build_backend_speed_probe_plan: Any,
    parsed_json_fn: Any,
) -> dict[str, object] | None:
    diagnostics = parsed_json_fn(window._diagnostics_json)
    if isinstance(diagnostics, dict):
        backends = diagnostics.get("backends")
        if isinstance(backends, dict):
            plans = backends.get("guided_speed_probes")
            if isinstance(plans, list):
                for plan in plans:
                    if isinstance(plan, dict):
                        return plan

    discovery = parsed_json_fn(window._discovery_json)
    backend_name = ""
    if isinstance(discovery, dict):
        backend_name = str(discovery.get("selected_backend") or "").strip().lower()
    if not backend_name and isinstance(diagnostics, dict):
        backends = diagnostics.get("backends")
        if isinstance(backends, dict):
            backend_name = str(backends.get("selected") or "").strip().lower()
    if not backend_name:
        return None
    plan = build_backend_speed_probe_plan(backend_name)
    return plan if isinstance(plan, dict) else None


def refresh_issue_report(
    window: Any,
    *,
    parsed_json_fn: Any,
    build_issue_report_with_evidence: Any,
    issue_url: str,
) -> None:
    diagnostics = parsed_json_fn(window._diagnostics_json)
    discovery = parsed_json_fn(window._discovery_json)
    if diagnostics is None and discovery is None:
        window._issue_report = None
        window.issue_meta_label.configure(text="Suggested template: run diagnostics or discovery first")
        window._set_text(
            window.txt_issue,
            "Run diagnostics or discovery to generate a suggested issue draft and the recommended GitHub form.\n",
        )
        return
    window._issue_report = build_issue_report_with_evidence(
        diagnostics=diagnostics,
        discovery=discovery,
        supplemental_evidence=window._supplemental_evidence
        if isinstance(window._supplemental_evidence, dict)
        else None,
    )
    template_label = str(window._issue_report.get("template_label") or "Issue report")
    resolved_issue_url = str(window._issue_report.get("issue_url") or issue_url)
    window.issue_meta_label.configure(text=f"Suggested template: {template_label}\nIssue URL: {resolved_issue_url}")
    window._set_text(window.txt_issue, str(window._issue_report.get("markdown") or ""))


def maybe_prompt_for_missing_evidence(
    window: Any,
    *,
    current_capture_plan_fn: Any,
    messagebox: Any,
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    plan = current_capture_plan_fn()
    automated = plan.get("automated") if isinstance(plan, dict) else None
    if not isinstance(automated, list) or not automated:
        return

    usb_id = str(plan.get("usb_id") or "")
    prompt_key = usb_id + ":" + ",".join(str(item.get("key") or "") for item in automated if isinstance(item, dict))
    if not prompt_key or prompt_key == window._capture_prompt_key:
        return
    window._capture_prompt_key = prompt_key

    needs_privileged = any(bool(item.get("requires_root")) for item in automated if isinstance(item, dict))
    message = "KeyRGB can collect additional evidence for this unsupported device now."
    if needs_privileged:
        message += " This may prompt for an administrator password to run read-only capture tools."
    message += "\n\nCollect missing evidence now?"

    try:
        ok = bool(messagebox.askyesno("Collect Missing Evidence", message, parent=window.root))
    except tk_runtime_errors:
        ok = False
    if ok:
        window.collect_missing_evidence(prompt=False)


def maybe_prompt_for_backend_speed_probe(
    window: Any,
    *,
    current_backend_speed_probe_plan_fn: Any,
    messagebox: Any,
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    plan = current_backend_speed_probe_plan_fn()
    if not isinstance(plan, dict):
        return

    prompt_key = str(plan.get("key") or "") + ":" + str(plan.get("backend") or "")
    if not prompt_key or prompt_key == window._backend_probe_prompt_key:
        return
    window._backend_probe_prompt_key = prompt_key

    message = (
        "KeyRGB can guide a backend speed probe for this device now.\n\n"
        "This will not change hardware automatically; it will show you the exact speed steps to try and save your notes into the support bundle.\n\n"
        "Run the probe now?"
    )
    try:
        ok = bool(messagebox.askyesno("Run Backend Speed Probe", message, parent=window.root))
    except tk_runtime_errors:
        ok = False
    if ok:
        window.run_backend_speed_probe(prompt=False)


def sync_button_state(window: Any, *, current_capture_plan_fn: Any, current_backend_speed_probe_plan_fn: Any) -> None:
    window.btn_copy_debug.configure(state="normal" if window._diagnostics_json else "disabled")
    window.btn_copy_discovery.configure(state="normal" if window._discovery_json else "disabled")
    window.btn_save_debug.configure(state="normal" if window._diagnostics_json else "disabled")
    window.btn_save_discovery.configure(state="normal" if window._discovery_json else "disabled")
    plan = current_capture_plan_fn()
    has_capture_plan = bool(plan.get("automated"))
    issue_state = "normal" if window._issue_report and window._issue_report.get("markdown") else "disabled"
    window.btn_copy_issue.configure(state=issue_state)
    window.btn_save_issue.configure(state=issue_state)
    window.btn_open_issue.configure(state=issue_state)
    window.btn_collect_evidence.configure(state="normal" if has_capture_plan else "disabled")
    window.btn_save_bundle.configure(
        state="normal" if (window._diagnostics_json or window._discovery_json) else "disabled"
    )
    window.btn_run_speed_probe.configure(
        state="normal" if isinstance(current_backend_speed_probe_plan_fn(), dict) else "disabled"
    )


def merge_supplemental_evidence(window: Any, payload: dict[str, object] | None) -> None:
    if not isinstance(payload, dict):
        return
    base = dict(window._supplemental_evidence) if isinstance(window._supplemental_evidence, dict) else {}
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged = dict(base.get(key) or {})
            merged.update(value)
            base[key] = merged
        else:
            base[key] = value
    window._supplemental_evidence = base


def set_status(window: Any, text: str, *, ok: bool = True) -> None:
    color = "#00aa00" if ok else "#bb0000"
    window.status_label.configure(text=text, foreground=color)
    window.root.after(2500, lambda: window.status_label.configure(text=""))


def set_text(widget: Any, text: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")


def copy_text(
    window: Any,
    text: str,
    *,
    empty_message: str,
    ok_message: str,
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    if not text:
        window._set_status(empty_message, ok=False)
        return
    try:
        window.root.clipboard_clear()
        window.root.clipboard_append(text)
    except tk_runtime_errors:
        window._set_status("Clipboard copy failed", ok=False)
        return
    window._set_status(ok_message, ok=True)


def save_text_via_dialog(
    window: Any,
    text: str,
    *,
    title: str,
    initialfile: str,
    empty_message: str,
    asksaveasfilename: Any,
) -> None:
    if not text:
        window._set_status(empty_message, ok=False)
        return

    path = asksaveasfilename(
        title=title,
        defaultextension=".json",
        initialfile=initialfile,
        filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")],
    )
    if not path:
        return

    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        window._set_status("Failed to save file", ok=False)
        return

    window._set_status("Saved output", ok=True)
