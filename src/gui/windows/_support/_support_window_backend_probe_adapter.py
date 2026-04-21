#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class SupportBackendProbeRuntimeDeps:
    auto_run_backend_speed_probe_fn: Callable[..., dict[str, object]]
    probe_config_snapshot_fn: Callable[..., object]
    restore_probe_config_fn: Callable[..., None]
    complete_backend_speed_probe_fn: Callable[..., None]
    show_probe_message_dialog: Callable[..., object]
    ask_probe_choice_dialog: Callable[..., object]
    ask_probe_notes_dialog: Callable[..., object]
    format_probe_speed_list_fn: Callable[..., str]
    tray_process_alive_fn: Callable[[str], bool]


def auto_run_backend_speed_probe_via_tray_config(
    plan: dict[str, object],
    *,
    config_cls: object,
    sleep_fn: Callable[[float], None],
    deps: SupportBackendProbeRuntimeDeps,
    build_auto_run_kwargs_fn: Callable[..., dict[str, object]],
) -> dict[str, object]:
    return deps.auto_run_backend_speed_probe_fn(
        plan,
        **build_auto_run_kwargs_fn(
            config_cls=config_cls,
            sleep_fn=sleep_fn,
            auto_run_backend_speed_probe_fn=deps.auto_run_backend_speed_probe_fn,
            probe_config_snapshot_fn=deps.probe_config_snapshot_fn,
            restore_probe_config_fn=deps.restore_probe_config_fn,
        ),
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
    deps: SupportBackendProbeRuntimeDeps,
    auto_run_backend_speed_probe_via_tray_config_fn: Callable[..., dict[str, object]],
    complete_backend_speed_probe_fn: Callable[..., None],
    tk: object,
    ttk: object,
    scrolledtext: object,
    build_run_kwargs_fn: Callable[..., dict[str, object]],
) -> dict[str, object]:
    return build_run_kwargs_fn(
        prompt=prompt,
        current_backend_speed_probe_plan_fn=current_backend_speed_probe_plan_fn,
        tk_runtime_errors=tk_runtime_errors,
        run_in_thread=run_in_thread,
        config_cls=config_cls,
        tray_pid=tray_pid,
        sleep_fn=sleep_fn,
        auto_run_backend_speed_probe_fn=auto_run_backend_speed_probe_via_tray_config_fn,
        complete_backend_speed_probe_fn=complete_backend_speed_probe_fn,
        show_probe_message_dialog=deps.show_probe_message_dialog,
        ask_probe_choice_dialog=deps.ask_probe_choice_dialog,
        ask_probe_notes_dialog=deps.ask_probe_notes_dialog,
        format_probe_speed_list_fn=deps.format_probe_speed_list_fn,
        tray_process_alive_fn=deps.tray_process_alive_fn,
        tk=tk,
        ttk=ttk,
        scrolledtext=scrolledtext,
    )


def complete_backend_speed_probe(
    window: object,
    *,
    plan: dict[str, object],
    selection_effect_name: str,
    tk_runtime_errors: tuple[type[BaseException], ...],
    started_at: str,
    automation_result: dict[str, object] | None,
    deps: SupportBackendProbeRuntimeDeps,
    complete_backend_speed_probe_fn: Callable[..., None],
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> None:
    complete_backend_speed_probe_fn(
        window,
        plan=plan,
        selection_effect_name=selection_effect_name,
        started_at=started_at,
        automation_result=automation_result,
        tk_runtime_errors=tk_runtime_errors,
        ask_probe_choice_dialog=deps.ask_probe_choice_dialog,
        ask_probe_notes_dialog=deps.ask_probe_notes_dialog,
        tk=tk,
        ttk=ttk,
        scrolledtext=scrolledtext,
    )
