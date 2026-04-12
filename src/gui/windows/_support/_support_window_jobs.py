#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import time
import tkinter as tk
from datetime import datetime, timezone
from typing import Any


_PROBE_AUTO_STEP_DURATION_S = 2.5
_PROBE_AUTO_SETTLE_DURATION_S = 0.5
_PROBE_DIALOG_SCREEN_RATIO_CAP = 0.92
_PROBE_AUTOMATION_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_PROBE_DIALOG_ERRORS = (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError)
_SUPPORT_COLLECTION_ERRORS = (AttributeError, ImportError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_SUPPORT_BUNDLE_BUILD_ERRORS = (AttributeError, LookupError, RuntimeError)


def _format_probe_speed_list(values: object) -> str:
    if not isinstance(values, list):
        return ""

    out: list[str] = []
    for value in values:
        if isinstance(value, int | float):
            out.append(str(int(value)))
            continue
        text = str(value or "").strip()
        if text:
            out.append(text)
    return ", ".join(out)


def _probe_dialog_dimensions(window: Any, *, width: int, height: int) -> tuple[int, int]:
    try:
        root = window.root
        screen_w = int(root.winfo_screenwidth())
        screen_h = int(root.winfo_screenheight())
        max_w = max(320, int(screen_w * _PROBE_DIALOG_SCREEN_RATIO_CAP))
        max_h = max(220, int(screen_h * _PROBE_DIALOG_SCREEN_RATIO_CAP))
        return min(int(width), max_w), min(int(height), max_h)
    except _PROBE_DIALOG_ERRORS:
        return int(width), int(height)


def _dialog_wraplength(container: Any, *, padding: int, minimum: int) -> int:
    try:
        width = int(container.winfo_width())
    except _PROBE_DIALOG_ERRORS:
        return int(minimum)
    if width <= 1:
        return int(minimum)
    return max(int(minimum), width - int(padding))


def _sync_dialog_prompt_wrap(label: Any, container: Any, *, padding: int, minimum: int) -> None:
    try:
        label.configure(wraplength=_dialog_wraplength(container, padding=padding, minimum=minimum))
    except _PROBE_DIALOG_ERRORS:
        return


def _bind_dialog_prompt_wrap(dialog: Any, label: Any, container: Any, *, padding: int, minimum: int) -> None:
    def _sync(_event=None) -> None:
        _sync_dialog_prompt_wrap(label, container, padding=padding, minimum=minimum)

    for widget in (dialog, container):
        try:
            widget.bind("<Configure>", _sync, add="+")
        except _PROBE_DIALOG_ERRORS:
            continue

    try:
        dialog.after(0, _sync)
    except _PROBE_DIALOG_ERRORS:
        return


def _build_dialog_button_row(
    container: Any,
    *,
    ttk: Any,
    row: int,
    pady: tuple[int, int],
    actions: list[tuple[str, Any]],
    columns: int,
) -> list[Any]:
    button_row = ttk.Frame(container)
    button_row.grid(row=row, column=0, sticky="ew", pady=pady)

    total_columns = max(1, min(int(columns), len(actions) if actions else 1))
    for column in range(total_columns):
        try:
            button_row.columnconfigure(column, weight=1)
        except _PROBE_DIALOG_ERRORS:
            continue

    created_buttons: list[Any] = []
    for index, (label, command) in enumerate(actions):
        grid_row = index // total_columns
        grid_column = index % total_columns
        button = ttk.Button(button_row, text=str(label), command=command)
        button.grid(
            row=grid_row,
            column=grid_column,
            sticky="ew",
            padx=(0 if grid_column == 0 else 8, 0),
            pady=(0 if grid_row == 0 else 8, 0),
        )
        created_buttons.append(button)

    return created_buttons


def _probe_dialog_geometry(window: Any, *, width: int, height: int) -> str:
    try:
        root = window.root
        root.update_idletasks()
        screen_w = int(root.winfo_screenwidth())
        screen_h = int(root.winfo_screenheight())
        width, height = _probe_dialog_dimensions(window, width=width, height=height)
        root_x = int(root.winfo_rootx())
        root_y = int(root.winfo_rooty())
        root_w = max(int(root.winfo_width()), width)
        root_h = max(int(root.winfo_height()), height)
        x = root_x + max(24, (root_w - width) // 2)
        y = root_y + max(24, (root_h - height) // 3)
        x = max(0, min(screen_w - width, x))
        y = max(0, min(screen_h - height, y))
        return f"{width}x{height}+{x}+{y}"
    except _PROBE_DIALOG_ERRORS:
        return f"{width}x{height}"


def _show_probe_message_dialog(
    window: Any,
    *,
    title: str,
    message: str,
    tk: Any,
    ttk: Any,
    scrolledtext: Any,
    width: int = 720,
    height: int = 560,
) -> bool:
    width, height = _probe_dialog_dimensions(window, width=width, height=height)
    dialog = tk.Toplevel(window.root)
    dialog.title(title)
    dialog.transient(window.root)
    dialog.geometry(_probe_dialog_geometry(window, width=width, height=height))
    dialog.minsize(min(560, width), min(360, height))
    dialog.resizable(True, True)

    container = ttk.Frame(dialog, padding=14)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(0, weight=1)

    body = scrolledtext.ScrolledText(
        container,
        wrap="word",
        height=18,
        background=window._bg_color,
        foreground=window._fg_color,
        insertbackground=window._fg_color,
    )
    body.grid(row=0, column=0, sticky="nsew")
    body.insert("1.0", str(message or ""))
    body.configure(state="disabled")

    result = {"ok": False}

    def close(*, ok: bool) -> None:
        result["ok"] = bool(ok)
        try:
            dialog.grab_release()
        except _PROBE_DIALOG_ERRORS:
            pass
        dialog.destroy()

    created_buttons = _build_dialog_button_row(
        container,
        ttk=ttk,
        row=1,
        pady=(12, 0),
        actions=[("OK", lambda: close(ok=True))],
        columns=1,
    )
    ok_btn = created_buttons[0]

    dialog.protocol("WM_DELETE_WINDOW", lambda: close(ok=False))
    try:
        dialog.grab_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    try:
        ok_btn.focus_set()
        body.focus_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    dialog.wait_window()
    return bool(result["ok"])


def _ask_probe_choice_dialog(
    window: Any,
    *,
    title: str,
    prompt: str,
    tk: Any,
    ttk: Any,
    choices: list[tuple[str, object]],
    width: int = 520,
    height: int = 240,
) -> object:
    width, height = _probe_dialog_dimensions(window, width=width, height=height)
    dialog = tk.Toplevel(window.root)
    dialog.title(title)
    dialog.transient(window.root)
    dialog.geometry(_probe_dialog_geometry(window, width=width, height=height))
    dialog.minsize(min(420, width), min(200, height))
    dialog.resizable(True, False)

    container = ttk.Frame(dialog, padding=16)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)

    prompt_label = ttk.Label(container, text=str(prompt or ""), justify="left", wraplength=width - 72)
    prompt_label.grid(row=0, column=0, sticky="w")
    _bind_dialog_prompt_wrap(dialog, prompt_label, container, padding=72, minimum=220)

    result = {"value": None}

    def close(value: object) -> None:
        result["value"] = value
        try:
            dialog.grab_release()
        except _PROBE_DIALOG_ERRORS:
            pass
        dialog.destroy()

    created_buttons = _build_dialog_button_row(
        container,
        ttk=ttk,
        row=1,
        pady=(18, 0),
        actions=[(str(label), (lambda v=value: close(v))) for label, value in choices],
        columns=2,
    )

    dialog.protocol("WM_DELETE_WINDOW", lambda: close(None))
    try:
        dialog.grab_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    try:
        if created_buttons:
            created_buttons[0].focus_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    dialog.wait_window()
    return result["value"]


def _ask_probe_notes_dialog(
    window: Any,
    *,
    title: str,
    prompt: str,
    tk: Any,
    ttk: Any,
    scrolledtext: Any,
    width: int = 720,
    height: int = 340,
) -> str | None:
    width, height = _probe_dialog_dimensions(window, width=width, height=height)
    dialog = tk.Toplevel(window.root)
    dialog.title(title)
    dialog.transient(window.root)
    dialog.geometry(_probe_dialog_geometry(window, width=width, height=height))
    dialog.minsize(min(560, width), min(260, height))
    dialog.resizable(True, True)

    container = ttk.Frame(dialog, padding=16)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(1, weight=1)

    prompt_label = ttk.Label(container, text=str(prompt or ""), justify="left", wraplength=width - 72)
    prompt_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
    _bind_dialog_prompt_wrap(dialog, prompt_label, container, padding=72, minimum=240)

    notes_box = scrolledtext.ScrolledText(
        container,
        wrap="word",
        height=10,
        background=window._bg_color,
        foreground=window._fg_color,
        insertbackground=window._fg_color,
    )
    notes_box.grid(row=1, column=0, sticky="nsew")

    result = {"value": None}

    def close(*, ok: bool) -> None:
        if ok:
            result["value"] = str(notes_box.get("1.0", "end")).strip()
        try:
            dialog.grab_release()
        except _PROBE_DIALOG_ERRORS:
            pass
        dialog.destroy()

    _build_dialog_button_row(
        container,
        ttk=ttk,
        row=2,
        pady=(12, 0),
        actions=[("OK", lambda: close(ok=True)), ("Cancel", lambda: close(ok=False))],
        columns=2,
    )

    dialog.protocol("WM_DELETE_WINDOW", lambda: close(ok=False))
    try:
        dialog.grab_set()
        notes_box.focus_set()
    except _PROBE_DIALOG_ERRORS:
        pass
    dialog.wait_window()
    return result["value"]


def _tray_process_alive(tray_pid: object) -> bool:
    try:
        pid = int(str(tray_pid or "").strip())
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    return os.path.exists(f"/proc/{pid}")


def _probe_config_snapshot(config: Any) -> dict[str, object]:
    effect_speeds = None
    settings = config._settings
    if isinstance(settings, dict):
        raw_effect_speeds = settings.get("effect_speeds")
        if isinstance(raw_effect_speeds, dict):
            effect_speeds = dict(raw_effect_speeds)

    try:
        speed = int(getattr(config, "speed", 0))
    except (TypeError, ValueError, OverflowError):
        speed = 0

    return {
        "effect": str(getattr(config, "effect", "none") or "none"),
        "speed": max(0, min(10, speed)),
        "effect_speeds": effect_speeds,
    }


def _restore_probe_config(config: Any, *, snapshot: dict[str, object]) -> None:
    settings = config._settings
    save_fn = config._save
    raw_effect_speeds = snapshot.get("effect_speeds")
    if isinstance(settings, dict) and callable(save_fn):
        if isinstance(raw_effect_speeds, dict) and raw_effect_speeds:
            settings["effect_speeds"] = dict(raw_effect_speeds)
        else:
            settings.pop("effect_speeds", None)
        save_fn()

    try:
        config.speed = int(snapshot.get("speed") or 0)
    except _PROBE_AUTOMATION_ERRORS:
        pass

    try:
        config.effect = str(snapshot.get("effect") or "none")
    except _PROBE_AUTOMATION_ERRORS:
        pass


def _auto_run_backend_speed_probe_via_tray_config(
    plan: dict[str, object],
    *,
    config_cls: Any,
    sleep_fn: Any,
) -> dict[str, object]:
    config = config_cls()
    snapshot = _probe_config_snapshot(config)
    effect_name = str(plan.get("effect_name") or "").strip()
    selection_effect_name = str(plan.get("selection_effect_name") or effect_name).strip() or effect_name
    requested_ui_speeds = [
        max(0, min(10, int(value)))
        for value in plan.get("requested_ui_speeds") or []
        if isinstance(value, int | float) or str(value).strip().isdigit()
    ]

    try:
        if selection_effect_name:
            config.effect = selection_effect_name
            sleep_fn(_PROBE_AUTO_SETTLE_DURATION_S)

        for ui_speed in requested_ui_speeds:
            config.set_effect_speed(effect_name, int(ui_speed))
            config.speed = int(ui_speed)
            sleep_fn(_PROBE_AUTO_STEP_DURATION_S)

        return {
            "execution_mode": "auto",
            "applied_ui_speeds": [int(value) for value in requested_ui_speeds],
            "step_duration_s": float(_PROBE_AUTO_STEP_DURATION_S),
            "settle_duration_s": float(_PROBE_AUTO_SETTLE_DURATION_S),
            "restored_effect": str(snapshot.get("effect") or "none"),
        }
    finally:
        _restore_probe_config(config, snapshot=snapshot)
        sleep_fn(_PROBE_AUTO_SETTLE_DURATION_S)


def run_debug(window: Any, *, collect_diagnostics_text: Any, run_in_thread: Any, logger: Any) -> None:
    window.btn_run_debug.configure(state="disabled")
    window.btn_copy_debug.configure(state="disabled")
    window._set_status("Collecting diagnostics…", ok=True)

    def work() -> str:
        try:
            return collect_diagnostics_text(include_usb=True)
        except _SUPPORT_COLLECTION_ERRORS as exc:
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
        except _SUPPORT_COLLECTION_ERRORS as exc:
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
    tk_runtime_errors: tuple[type[BaseException], ...],
    run_in_thread: Any,
    config_cls: Any,
    tray_pid: str,
    tk: Any,
    ttk: Any,
    scrolledtext: Any,
) -> None:
    plan = current_backend_speed_probe_plan_fn()
    if not isinstance(plan, dict):
        window._set_status("No guided backend probe available", ok=False)
        return

    selection_effect_name = str(plan.get("selection_effect_name") or plan.get("effect_name") or "").strip()
    auto_run_available = _tray_process_alive(tray_pid)
    if not auto_run_available:
        window._set_status("Backend speed probe requires the running tray session", ok=False)
        return

    if prompt:
        requested_speed_text = _format_probe_speed_list(plan.get("requested_ui_speeds"))
        prompt_message = (
            "Run the guided backend speed probe through the tray now?\n\n"
            "KeyRGB will temporarily switch to the probe effect, hold each test speed for about "
            f"{_PROBE_AUTO_STEP_DURATION_S:.1f} seconds"
            + (f" ({requested_speed_text})" if requested_speed_text else "")
            + ", restore the previous tray effect, and then ask for your observation."
        )
        try:
            ok = _ask_probe_choice_dialog(
                window,
                title="Backend Speed Probe",
                prompt=prompt_message,
                tk=tk,
                ttk=ttk,
                choices=[("Run probe", True), ("Cancel", None)],
                width=640,
                height=230,
            )
        except tk_runtime_errors:
            ok = None
        if ok is None:
            return

    started_at = datetime.now(timezone.utc).isoformat()
    try:
        requested_speed_text = _format_probe_speed_list(plan.get("requested_ui_speeds"))
        _show_probe_message_dialog(
            window,
            title="Backend Speed Probe",
            message=(
                "KeyRGB will temporarily switch the tray to the probe effect, play each listed speed step, and then restore the previous tray effect.\n\n"
                + (f"Requested speeds: {requested_speed_text}.\n" if requested_speed_text else "")
                + f"Each speed will stay active for about {_PROBE_AUTO_STEP_DURATION_S:.1f} seconds with a short settle gap before the next step.\n\n"
                "Watch the keyboard now. When the auto-run finishes, KeyRGB will ask for your observation."
            ),
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolledtext,
            width=680,
            height=320,
        )
    except tk_runtime_errors:
        pass

    window.btn_run_speed_probe.configure(state="disabled")
    window._set_status("Auto-running backend speed probe…", ok=True)

    def work() -> dict[str, object]:
        try:
            return {
                "ok": True,
                "payload": _auto_run_backend_speed_probe_via_tray_config(
                    plan,
                    config_cls=config_cls,
                    sleep_fn=time.sleep,
                ),
            }
        except _PROBE_AUTOMATION_ERRORS as exc:
            return {"ok": False, "error": str(exc).strip() or exc.__class__.__name__}

    def on_done(result: dict[str, object]) -> None:
        window.btn_run_speed_probe.configure(state="normal")
        if not bool(result.get("ok")):
            window._sync_button_state()
            window._set_status("Automatic backend speed probe failed", ok=False)
            return
        _complete_backend_speed_probe(
            window,
            plan=plan,
            selection_effect_name=selection_effect_name,
            messagebox=messagebox,
            tk_runtime_errors=tk_runtime_errors,
            started_at=started_at,
            automation_result=result.get("payload") if isinstance(result.get("payload"), dict) else None,
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolledtext,
        )

    run_in_thread(window.root, work, on_done)


def _complete_backend_speed_probe(
    window: Any,
    *,
    plan: dict[str, object],
    selection_effect_name: str,
    messagebox: Any,
    tk_runtime_errors: tuple[type[BaseException], ...],
    started_at: str,
    automation_result: dict[str, object] | None,
    tk: Any,
    ttk: Any,
    scrolledtext: Any,
) -> None:

    try:
        distinct_steps = _ask_probe_choice_dialog(
            window,
            title="Backend Speed Probe",
            prompt="Did the listed speed steps look clearly distinct on the keyboard?",
            tk=tk,
            ttk=ttk,
            choices=[("Yes", True), ("No", False), ("Cancel", None)],
            width=560,
            height=220,
        )
    except tk_runtime_errors:
        distinct_steps = None

    try:
        notes = _ask_probe_notes_dialog(
            window,
            title="Backend Speed Probe",
            prompt=str(plan.get("observation_prompt") or "Observation notes:"),
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolledtext,
            width=760,
            height=360,
        )
    except tk_runtime_errors:
        notes = None

    completed_at = datetime.now(timezone.utc).isoformat()
    result = {
        "backend": plan.get("backend"),
        "effect_name": plan.get("effect_name"),
        "selection_effect_name": selection_effect_name,
        "requested_ui_speeds": list(plan.get("requested_ui_speeds") or []),
        "samples": list(plan.get("samples") or []),
        "started_at": started_at,
        "completed_at": completed_at,
        "execution_mode": str((automation_result or {}).get("execution_mode") or "auto"),
        "observation": {"distinct_steps": distinct_steps, "notes": str(notes or "").strip()},
    }
    if isinstance(automation_result, dict) and automation_result:
        result["automation"] = dict(automation_result)
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
    except _SUPPORT_BUNDLE_BUILD_ERRORS:
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
