#!/usr/bin/env python3

from __future__ import annotations

import time
from collections.abc import Callable

from . import _support_window_backend_probe_adapter as _backend_probe_adapter
from . import _support_window_backend_probe as _backend_probe
from . import _support_window_exports as _exports

# Retained for external support window callers.
from . import _support_window_job_wiring as _job_wiring
from . import _support_window_probe_dialogs as _probe_dialogs
from . import _support_window_tasks as _tasks

# Retained for external tests.
_probe_dialog_dimensions = _probe_dialogs._probe_dialog_dimensions
# Retained for external tests.
_dialog_wraplength = _probe_dialogs._dialog_wraplength
# Retained for external tests.
_sync_dialog_prompt_wrap = _probe_dialogs._sync_dialog_prompt_wrap
# Retained for external tests.
_build_dialog_button_row = _probe_dialogs._build_dialog_button_row
# Retained for external tests.
_probe_dialog_geometry = _probe_dialogs._probe_dialog_geometry
_show_probe_message_dialog = _probe_dialogs._show_probe_message_dialog
_ask_probe_choice_dialog = _probe_dialogs._ask_probe_choice_dialog
_ask_probe_notes_dialog = _probe_dialogs._ask_probe_notes_dialog
# Retained for external support window callers.
_tray_process_alive = _backend_probe._tray_process_alive
# Retained for external tests.
_probe_config_snapshot = _backend_probe._probe_config_snapshot
# Retained for external tests.
_restore_probe_config = _backend_probe._restore_probe_config

run_debug = _tasks.run_debug
run_discovery = _tasks.run_discovery
collect_missing_evidence = _tasks.collect_missing_evidence
save_support_bundle = _exports.save_support_bundle
open_issue_form = _exports.open_issue_form


def _backend_probe_runtime_deps() -> _backend_probe_adapter.SupportBackendProbeRuntimeDeps:
    return _backend_probe_adapter.SupportBackendProbeRuntimeDeps(
        auto_run_backend_speed_probe_fn=_backend_probe._auto_run_backend_speed_probe_via_tray_config,
        probe_config_snapshot_fn=_probe_config_snapshot,
        restore_probe_config_fn=_restore_probe_config,
        complete_backend_speed_probe_fn=_backend_probe._complete_backend_speed_probe,
        show_probe_message_dialog=_show_probe_message_dialog,
        ask_probe_choice_dialog=_ask_probe_choice_dialog,
        ask_probe_notes_dialog=_ask_probe_notes_dialog,
        format_probe_speed_list_fn=_backend_probe._format_probe_speed_list,
        tray_process_alive_fn=_tray_process_alive,
    )


def _auto_run_backend_speed_probe_via_tray_config(
    plan: dict[str, object],
    *,
    config_cls: _backend_probe._ProbeConfigFactory,
    sleep_fn: Callable[[float], None],
) -> dict[str, object]:
    return _backend_probe_adapter.auto_run_backend_speed_probe_via_tray_config(
        plan,
        config_cls=config_cls,
        sleep_fn=sleep_fn,
        deps=_backend_probe_runtime_deps(),
        build_auto_run_kwargs_fn=_job_wiring.build_auto_run_backend_speed_probe_kwargs,
    )


def run_backend_speed_probe(
    window: _backend_probe._SupportWindowLike,
    *,
    prompt: bool,
    current_backend_speed_probe_plan_fn: _backend_probe._CurrentBackendSpeedProbePlanFn,
    messagebox: _tasks._MessageBox,
    tk_runtime_errors: tuple[type[BaseException], ...],
    run_in_thread: _backend_probe._RunInThreadFn,
    config_cls: _backend_probe._ProbeConfigFactory,
    tray_pid: str,
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> None:
    _ = messagebox
    return _backend_probe.run_backend_speed_probe(
        window,
        **_backend_speed_probe_run_kwargs(
            prompt=prompt,
            current_backend_speed_probe_plan_fn=current_backend_speed_probe_plan_fn,
            tk_runtime_errors=tk_runtime_errors,
            run_in_thread=run_in_thread,
            config_cls=config_cls,
            tray_pid=tray_pid,
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolledtext,
        ),
    )


def _backend_speed_probe_run_kwargs(
    *,
    prompt: bool,
    current_backend_speed_probe_plan_fn: _backend_probe._CurrentBackendSpeedProbePlanFn,
    tk_runtime_errors: tuple[type[BaseException], ...],
    run_in_thread: _backend_probe._RunInThreadFn,
    config_cls: _backend_probe._ProbeConfigFactory,
    tray_pid: str,
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> dict[str, object]:
    return _backend_probe_adapter.build_backend_speed_probe_run_kwargs(
        prompt=prompt,
        current_backend_speed_probe_plan_fn=current_backend_speed_probe_plan_fn,
        tk_runtime_errors=tk_runtime_errors,
        run_in_thread=run_in_thread,
        config_cls=config_cls,
        tray_pid=tray_pid,
        sleep_fn=time.sleep,
        deps=_backend_probe_runtime_deps(),
        auto_run_backend_speed_probe_via_tray_config_fn=_auto_run_backend_speed_probe_via_tray_config,
        complete_backend_speed_probe_fn=_complete_backend_speed_probe,
        tk=tk,
        ttk=ttk,
        scrolledtext=scrolledtext,
        build_run_kwargs_fn=_job_wiring.build_backend_speed_probe_run_kwargs,
    )


def _complete_backend_speed_probe(
    window: _backend_probe._SupportWindowLike,
    *,
    plan: dict[str, object],
    selection_effect_name: str,
    tk_runtime_errors: tuple[type[BaseException], ...],
    started_at: str,
    automation_result: dict[str, object] | None,
    ask_probe_choice_dialog: object,
    ask_probe_notes_dialog: object,
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> None:
    _ = (ask_probe_choice_dialog, ask_probe_notes_dialog)
    return _backend_probe_adapter.complete_backend_speed_probe(
        window,
        plan=plan,
        selection_effect_name=selection_effect_name,
        tk_runtime_errors=tk_runtime_errors,
        started_at=started_at,
        automation_result=automation_result,
        deps=_backend_probe_runtime_deps(),
        complete_backend_speed_probe_fn=_backend_probe._complete_backend_speed_probe,
        tk=tk,
        ttk=ttk,
        scrolledtext=scrolledtext,
    )
