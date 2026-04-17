#!/usr/bin/env python3

from __future__ import annotations

import time
from collections.abc import Callable

from . import _support_window_backend_probe as _backend_probe
from . import _support_window_exports as _exports
from . import _support_window_probe_dialogs as _probe_dialogs
from . import _support_window_tasks as _tasks


_PROBE_AUTO_STEP_DURATION_S = _backend_probe._PROBE_AUTO_STEP_DURATION_S
_PROBE_AUTO_SETTLE_DURATION_S = _backend_probe._PROBE_AUTO_SETTLE_DURATION_S
_PROBE_AUTOMATION_ERRORS = _backend_probe._PROBE_AUTOMATION_ERRORS
_SUPPORT_COLLECTION_ERRORS = _tasks._SUPPORT_COLLECTION_ERRORS
_SUPPORT_BUNDLE_BUILD_ERRORS = _exports._SUPPORT_BUNDLE_BUILD_ERRORS

_PROBE_DIALOG_SCREEN_RATIO_CAP = _probe_dialogs._PROBE_DIALOG_SCREEN_RATIO_CAP
_PROBE_DIALOG_ERRORS = _probe_dialogs._PROBE_DIALOG_ERRORS
_probe_dialog_dimensions = _probe_dialogs._probe_dialog_dimensions
_dialog_wraplength = _probe_dialogs._dialog_wraplength
_sync_dialog_prompt_wrap = _probe_dialogs._sync_dialog_prompt_wrap
_bind_dialog_prompt_wrap = _probe_dialogs._bind_dialog_prompt_wrap
_build_dialog_button_row = _probe_dialogs._build_dialog_button_row
_probe_dialog_geometry = _probe_dialogs._probe_dialog_geometry
_show_probe_message_dialog = _probe_dialogs._show_probe_message_dialog
_ask_probe_choice_dialog = _probe_dialogs._ask_probe_choice_dialog
_ask_probe_notes_dialog = _probe_dialogs._ask_probe_notes_dialog

_format_probe_speed_list = _backend_probe._format_probe_speed_list
_tray_process_alive = _backend_probe._tray_process_alive
_probe_config_snapshot = _backend_probe._probe_config_snapshot
_restore_probe_config = _backend_probe._restore_probe_config

run_debug = _tasks.run_debug
run_discovery = _tasks.run_discovery
collect_missing_evidence = _tasks.collect_missing_evidence
save_support_bundle = _exports.save_support_bundle
open_issue_form = _exports.open_issue_form


def _auto_run_backend_speed_probe_via_tray_config(
    plan: dict[str, object],
    *,
    config_cls: _backend_probe._ProbeConfigFactory,
    sleep_fn: Callable[[float], None],
) -> dict[str, object]:
    return _backend_probe._auto_run_backend_speed_probe_via_tray_config(
        plan,
        config_cls=config_cls,
        sleep_fn=sleep_fn,
        probe_config_snapshot_fn=_probe_config_snapshot,
        restore_probe_config_fn=_restore_probe_config,
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
        prompt=prompt,
        current_backend_speed_probe_plan_fn=current_backend_speed_probe_plan_fn,
        tk_runtime_errors=tk_runtime_errors,
        run_in_thread=run_in_thread,
        config_cls=config_cls,
        tray_pid=tray_pid,
        sleep_fn=time.sleep,
        format_probe_speed_list_fn=_format_probe_speed_list,
        tray_process_alive_fn=_tray_process_alive,
        auto_run_backend_speed_probe_fn=_auto_run_backend_speed_probe_via_tray_config,
        complete_backend_speed_probe_fn=_complete_backend_speed_probe,
        show_probe_message_dialog=_show_probe_message_dialog,
        ask_probe_choice_dialog=_ask_probe_choice_dialog,
        tk=tk,
        ttk=ttk,
        scrolledtext=scrolledtext,
    )


def _complete_backend_speed_probe(
    window: _backend_probe._SupportWindowLike,
    *,
    plan: dict[str, object],
    selection_effect_name: str,
    tk_runtime_errors: tuple[type[BaseException], ...],
    started_at: str,
    automation_result: dict[str, object] | None,
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> None:
    return _backend_probe._complete_backend_speed_probe(
        window,
        plan=plan,
        selection_effect_name=selection_effect_name,
        started_at=started_at,
        automation_result=automation_result,
        tk_runtime_errors=tk_runtime_errors,
        ask_probe_choice_dialog=_ask_probe_choice_dialog,
        ask_probe_notes_dialog=_ask_probe_notes_dialog,
        tk=tk,
        ttk=ttk,
        scrolledtext=scrolledtext,
    )
