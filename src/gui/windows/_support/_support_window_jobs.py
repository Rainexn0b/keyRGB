#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def run_debug(window: Any, *, collect_diagnostics_text: Any, run_in_thread: Any, logger: Any) -> None:
    window.btn_run_debug.configure(state="disabled")
    window.btn_copy_debug.configure(state="disabled")
    window._set_status("Collecting diagnostics…", ok=True)

    def work() -> str:
        try:
            return collect_diagnostics_text(include_usb=True)
        except Exception as exc:  # @quality-exception exception-transparency: diagnostics collection is an arbitrary external boundary and the worker thread must return a safe fallback string instead of raising
            logger.exception("Failed to collect diagnostics")
            return f"Failed to collect diagnostics: {exc}"

    def on_done(text: str) -> None:
        window._diagnostics_json = text if text.strip().startswith("{") else ""
        window._set_text(window.txt_debug, text)
        window.btn_run_debug.configure(state="normal")
        window._refresh_issue_report()
        window._sync_button_state()
        window._set_status("Diagnostics ready", ok=bool(window._diagnostics_json))
        window._maybe_prompt_for_backend_speed_probe()

    run_in_thread(window.root, work, on_done)


def run_discovery(
    window: Any,
    *,
    collect_device_discovery: Any,
    format_device_discovery_text: Any,
    run_in_thread: Any,
    logger: Any,
) -> None:
    window.btn_run_discovery.configure(state="disabled")
    window.btn_copy_discovery.configure(state="disabled")
    window._set_status("Scanning backend candidates…", ok=True)

    def work() -> tuple[str, str]:
        try:
            payload = collect_device_discovery(include_usb=True)
            return json.dumps(payload, indent=2, sort_keys=True), format_device_discovery_text(payload)
        except Exception as exc:  # @quality-exception exception-transparency: device discovery collection is an arbitrary external boundary and the worker thread must return a safe fallback instead of raising
            logger.exception("Failed to collect discovery snapshot")
            return "", f"Failed to scan devices: {exc}"

    def on_done(result: tuple[str, str]) -> None:
        payload_text, display_text = result
        window._discovery_json = payload_text
        backend_probes = None
        if isinstance(window._supplemental_evidence, dict):
            existing_backend_probes = window._supplemental_evidence.get("backend_probes")
            if isinstance(existing_backend_probes, dict) and existing_backend_probes:
                backend_probes = dict(existing_backend_probes)
        window._supplemental_evidence = {"backend_probes": backend_probes} if backend_probes else None
        window._set_text(window.txt_discovery, display_text)
        window.btn_run_discovery.configure(state="normal")
        window._refresh_issue_report()
        window._sync_button_state()
        window._set_status("Discovery scan ready", ok=bool(window._discovery_json))
        window._maybe_prompt_for_missing_evidence()
        window._maybe_prompt_for_backend_speed_probe()

    run_in_thread(window.root, work, on_done)


def collect_missing_evidence(
    window: Any,
    *,
    prompt: bool,
    current_capture_plan_fn: Any,
    messagebox: Any,
    tk_runtime_errors: tuple[type[BaseException], ...],
    collect_additional_evidence: Any,
    run_in_thread: Any,
) -> None:
    plan = current_capture_plan_fn()
    automated = plan.get("automated") if isinstance(plan, dict) else None
    if not isinstance(automated, list) or not automated:
        window._set_status("No extra evidence needed", ok=False)
        return

    if prompt:
        needs_privileged = any(bool(item.get("requires_root")) for item in automated if isinstance(item, dict))
        message = "Collect additional USB/HID evidence for the current unsupported device?"
        if needs_privileged:
            message += " This may prompt for an administrator password."
        try:
            ok = bool(messagebox.askyesno("Collect Missing Evidence", message, parent=window.root))
        except tk_runtime_errors:
            ok = False
        if not ok:
            return

    window.btn_collect_evidence.configure(state="disabled")
    window._set_status("Collecting additional evidence…", ok=True)

    def work() -> dict[str, object]:
        return collect_additional_evidence(window._parsed_json(window._discovery_json), allow_privileged=True)

    def on_done(payload: dict[str, object]) -> None:
        window._merge_supplemental_evidence(payload if isinstance(payload, dict) else None)
        window._refresh_issue_report()
        window._sync_button_state()
        captures = payload.get("captures") if isinstance(payload, dict) else None
        success = 0
        if isinstance(captures, dict):
            success = sum(1 for value in captures.values() if isinstance(value, dict) and value.get("ok"))
        window._set_status(
            "Additional evidence collected" if success else "Additional evidence incomplete", ok=bool(success)
        )

    run_in_thread(window.root, work, on_done)


def run_backend_speed_probe(
    window: Any,
    *,
    prompt: bool,
    current_backend_speed_probe_plan_fn: Any,
    messagebox: Any,
    simpledialog: Any,
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    plan = current_backend_speed_probe_plan_fn()
    if not isinstance(plan, dict):
        window._set_status("No guided backend probe available", ok=False)
        return

    if prompt:
        try:
            ok = bool(
                messagebox.askyesno(
                    "Run Backend Speed Probe",
                    "Use the guided backend speed probe for the current diagnostics snapshot?",
                    parent=window.root,
                )
            )
        except tk_runtime_errors:
            ok = False
        if not ok:
            return

    instructions = "\n".join(f"- {line}" for line in plan.get("instructions") or [])
    samples_text = ", ".join(
        f"UI {sample.get('ui_speed')} -> raw {sample.get('raw_speed_hex')}"
        for sample in plan.get("samples") or []
        if isinstance(sample, dict)
    )
    message = (
        f"Backend: {plan.get('backend')}\n"
        f"Effect: {plan.get('effect_name')}\n"
        f"Samples: {samples_text}\n\n"
        f"{instructions}\n\n"
        "Click OK after you have tested the listed speed values."
    )
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        messagebox.showinfo("Backend Speed Probe", message, parent=window.root)
    except tk_runtime_errors:
        pass

    try:
        distinct_steps = messagebox.askyesnocancel(
            "Backend Speed Probe",
            "Did the listed speed steps look clearly distinct on the keyboard?",
            parent=window.root,
        )
    except tk_runtime_errors:
        distinct_steps = None

    try:
        notes = simpledialog.askstring(
            "Backend Speed Probe",
            str(plan.get("observation_prompt") or "Observation notes:"),
            parent=window.root,
        )
    except tk_runtime_errors:
        notes = None

    completed_at = datetime.now(timezone.utc).isoformat()
    result = {
        "backend": plan.get("backend"),
        "effect_name": plan.get("effect_name"),
        "requested_ui_speeds": list(plan.get("requested_ui_speeds") or []),
        "samples": list(plan.get("samples") or []),
        "started_at": started_at,
        "completed_at": completed_at,
        "observation": {"distinct_steps": distinct_steps, "notes": str(notes or "").strip()},
    }
    window._merge_supplemental_evidence({"backend_probes": {str(plan.get("key") or "backend_probe"): result}})
    window._refresh_issue_report()
    window._sync_button_state()
    window._set_status("Backend speed probe recorded", ok=True)


def save_support_bundle(
    window: Any,
    *,
    asksaveasfilename: Any,
    build_support_bundle_payload: Any,
    logger: Any,
) -> None:
    if not window._diagnostics_json and not window._discovery_json:
        window._set_status("Run diagnostics or discovery first", ok=False)
        return

    path = asksaveasfilename(
        title="Save support bundle",
        defaultextension=".json",
        initialfile="keyrgb-support-bundle.json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )
    if not path:
        return

    try:
        payload = build_support_bundle_payload(
            diagnostics=window._parsed_json(window._diagnostics_json),
            discovery=window._parsed_json(window._discovery_json),
            supplemental_evidence=window._supplemental_evidence
            if isinstance(window._supplemental_evidence, dict)
            else None,
        )
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except (OSError, TypeError, ValueError):
        window._set_status("Failed to save bundle", ok=False)
        return
    except Exception:  # @quality-exception exception-transparency: unexpected error saving the support bundle JSON; narrow catch above already handles expected IO/serialization errors
        logger.exception("Failed to save support bundle")
        window._set_status("Failed to save bundle", ok=False)
        return

    window._set_status("Saved support bundle", ok=True)


def open_issue_form(
    window: Any,
    *,
    issue_url: str,
    open_browser: Any,
    browser_open_errors: tuple[type[BaseException], ...],
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    resolved_issue_url = str((window._issue_report or {}).get("issue_url") or issue_url)
    try:
        ok = bool(open_browser(resolved_issue_url, new=2))
    except browser_open_errors:
        ok = False

    if ok:
        window._set_status("Opened issue form", ok=True)
        return

    try:
        window.root.clipboard_clear()
        window.root.clipboard_append(resolved_issue_url)
        window._set_status("Couldn't open browser; issue URL copied", ok=False)
    except tk_runtime_errors:
        window._set_status("Couldn't open browser", ok=False)
