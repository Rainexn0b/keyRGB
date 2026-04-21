#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Callable


def build_run_debug_job_kwargs(
    *,
    collect_diagnostics_text: Callable[..., str],
    run_in_thread: Callable[..., object],
    logger: object,
) -> dict[str, object]:
    return {
        "collect_diagnostics_text": collect_diagnostics_text,
        "run_in_thread": run_in_thread,
        "logger": logger,
    }


def build_run_discovery_job_kwargs(
    *,
    collect_device_discovery: Callable[..., dict[str, object]],
    format_device_discovery_text: Callable[..., str],
    run_in_thread: Callable[..., object],
    logger: object,
) -> dict[str, object]:
    return {
        "collect_device_discovery": collect_device_discovery,
        "format_device_discovery_text": format_device_discovery_text,
        "run_in_thread": run_in_thread,
        "logger": logger,
    }


def build_save_support_bundle_job_kwargs(
    *,
    asksaveasfilename: Callable[..., str],
    build_support_bundle_payload: Callable[..., dict[str, object]],
    logger: object,
) -> dict[str, object]:
    return {
        "asksaveasfilename": asksaveasfilename,
        "build_support_bundle_payload": build_support_bundle_payload,
        "logger": logger,
    }


def build_open_issue_form_job_kwargs(
    *,
    issue_url: str,
    open_browser: Callable[..., bool],
    browser_open_errors: tuple[type[BaseException], ...],
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> dict[str, object]:
    return {
        "issue_url": issue_url,
        "open_browser": open_browser,
        "browser_open_errors": browser_open_errors,
        "tk_runtime_errors": tk_runtime_errors,
    }


def dispatch_save_support_bundle_job(
    window: object,
    *,
    support_jobs: object,
    asksaveasfilename: Callable[..., str],
    build_support_bundle_payload: Callable[..., dict[str, object]],
    logger: object,
) -> None:
    support_jobs.save_support_bundle(
        window,
        **build_save_support_bundle_job_kwargs(
            asksaveasfilename=asksaveasfilename,
            build_support_bundle_payload=build_support_bundle_payload,
            logger=logger,
        ),
    )


def dispatch_open_issue_form_job(
    window: object,
    *,
    support_jobs: object,
    issue_url: str,
    open_browser: Callable[..., bool],
    browser_open_errors: tuple[type[BaseException], ...],
    tk_runtime_errors: tuple[type[BaseException], ...],
) -> None:
    support_jobs.open_issue_form(
        window,
        **build_open_issue_form_job_kwargs(
            issue_url=issue_url,
            open_browser=open_browser,
            browser_open_errors=browser_open_errors,
            tk_runtime_errors=tk_runtime_errors,
        ),
    )


def build_collect_missing_evidence_job_kwargs(
    *,
    prompt: bool,
    current_capture_plan_fn: Callable[[], dict[str, object]],
    messagebox: object,
    tk_runtime_errors: tuple[type[BaseException], ...],
    collect_additional_evidence: Callable[..., dict[str, object] | None],
    run_in_thread: Callable[..., object],
) -> dict[str, object]:
    return {
        "prompt": prompt,
        "current_capture_plan_fn": current_capture_plan_fn,
        "messagebox": messagebox,
        "tk_runtime_errors": tk_runtime_errors,
        "collect_additional_evidence": collect_additional_evidence,
        "run_in_thread": run_in_thread,
    }


def build_backend_speed_probe_job_kwargs(
    *,
    prompt: bool,
    current_backend_speed_probe_plan_fn: Callable[[], dict[str, object] | None],
    messagebox: object,
    tk_runtime_errors: tuple[type[BaseException], ...],
    run_in_thread: Callable[..., object],
    config_cls: object,
    tray_pid: str,
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> dict[str, object]:
    return {
        "prompt": prompt,
        "current_backend_speed_probe_plan_fn": current_backend_speed_probe_plan_fn,
        "messagebox": messagebox,
        "tk_runtime_errors": tk_runtime_errors,
        "run_in_thread": run_in_thread,
        "config_cls": config_cls,
        "tray_pid": tray_pid,
        "tk": tk,
        "ttk": ttk,
        "scrolledtext": scrolledtext,
    }


def auto_run_backend_speed_probe_via_tray_config(
    plan: dict[str, object],
    *,
    config_cls: object,
    sleep_fn: Callable[[float], None],
    auto_run_backend_speed_probe_fn: Callable[..., dict[str, object]],
    probe_config_snapshot_fn: Callable[..., object],
    restore_probe_config_fn: Callable[..., None],
) -> dict[str, object]:
    return auto_run_backend_speed_probe_fn(
        plan,
        config_cls=config_cls,
        sleep_fn=sleep_fn,
        probe_config_snapshot_fn=probe_config_snapshot_fn,
        restore_probe_config_fn=restore_probe_config_fn,
    )


def build_backend_speed_probe_run_kwargs(
    *,
    prompt: bool,
    current_backend_speed_probe_plan_fn: Callable[[], object],
    tk_runtime_errors: tuple[type[BaseException], ...],
    run_in_thread: Callable[..., object],
    config_cls: object,
    tray_pid: str,
    sleep_fn: Callable[[float], None],
    auto_run_backend_speed_probe_fn: Callable[..., dict[str, object]],
    complete_backend_speed_probe_fn: Callable[..., None],
    show_probe_message_dialog: Callable[..., object],
    ask_probe_choice_dialog: Callable[..., object],
    format_probe_speed_list_fn: Callable[..., str],
    tray_process_alive_fn: Callable[[str], bool],
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> dict[str, object]:
    return {
        "prompt": prompt,
        "current_backend_speed_probe_plan_fn": current_backend_speed_probe_plan_fn,
        "tk_runtime_errors": tk_runtime_errors,
        "run_in_thread": run_in_thread,
        "config_cls": config_cls,
        "tray_pid": tray_pid,
        "sleep_fn": sleep_fn,
        "format_probe_speed_list_fn": format_probe_speed_list_fn,
        "tray_process_alive_fn": tray_process_alive_fn,
        "auto_run_backend_speed_probe_fn": auto_run_backend_speed_probe_fn,
        "complete_backend_speed_probe_fn": complete_backend_speed_probe_fn,
        "show_probe_message_dialog": show_probe_message_dialog,
        "ask_probe_choice_dialog": ask_probe_choice_dialog,
        "tk": tk,
        "ttk": ttk,
        "scrolledtext": scrolledtext,
    }