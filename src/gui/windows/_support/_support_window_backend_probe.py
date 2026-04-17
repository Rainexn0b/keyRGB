#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Protocol, cast

from . import _support_window_backend_probe_config as _probe_config


_PROBE_AUTO_STEP_DURATION_S = _probe_config._PROBE_AUTO_STEP_DURATION_S
_PROBE_AUTO_SETTLE_DURATION_S = _probe_config._PROBE_AUTO_SETTLE_DURATION_S
_PROBE_AUTOMATION_ERRORS = _probe_config._PROBE_AUTOMATION_ERRORS
ProbeConfigSnapshot = _probe_config.ProbeConfigSnapshot

_ProbeConfigLike = _probe_config._ProbeConfigLike
_ProbePlan = _probe_config._ProbePlan
_ProbeResult = _probe_config._ProbeResult
_SnapshotInput = _probe_config._SnapshotInput
_ProbeConfigFactory = _probe_config._ProbeConfigFactory
_SleepFn = _probe_config._SleepFn
_ProbeConfigSnapshotFn = _probe_config._ProbeConfigSnapshotFn
_RestoreProbeConfigFn = _probe_config._RestoreProbeConfigFn

_format_probe_speed_list = _probe_config._format_probe_speed_list
_tray_process_alive = _probe_config._tray_process_alive
_probe_config_snapshot = _probe_config._probe_config_snapshot
_restore_probe_config = _probe_config._restore_probe_config
_auto_run_backend_speed_probe_via_tray_config = _probe_config._auto_run_backend_speed_probe_via_tray_config


class _ProbeButtonLike(Protocol):
    def configure(self, **kwargs: object) -> None: ...


class _SupportWindowLike(Protocol):
    root: object
    btn_run_speed_probe: _ProbeButtonLike

    def _merge_supplemental_evidence(self, payload: dict[str, object] | None) -> None: ...

    def _refresh_issue_report(self) -> None: ...

    def _set_status(self, text: str, *, ok: bool = True) -> None: ...

    def _sync_button_state(self) -> None: ...


_CurrentBackendSpeedProbePlanFn = Callable[[], object]
_FormatProbeSpeedListFn = Callable[[object], str]
_TrayProcessAliveFn = Callable[[str], bool]
_TkRuntimeErrors = tuple[type[BaseException], ...]


class _AutoRunBackendSpeedProbeFn(Protocol):
    def __call__(
        self,
        plan: _ProbePlan,
        *,
        config_cls: _ProbeConfigFactory,
        sleep_fn: _SleepFn,
    ) -> _ProbeResult: ...


class _CompleteBackendSpeedProbeFn(Protocol):
    def __call__(
        self,
        window: _SupportWindowLike,
        *,
        plan: _ProbePlan,
        selection_effect_name: str,
        started_at: str,
        automation_result: _ProbeResult | None,
        tk_runtime_errors: _TkRuntimeErrors,
        tk: object,
        ttk: object,
        scrolledtext: object,
    ) -> None: ...


class _ShowProbeMessageDialogFn(Protocol):
    def __call__(
        self,
        window: _SupportWindowLike,
        *,
        title: str,
        message: str,
        tk: object,
        ttk: object,
        scrolledtext: object,
        width: int = 720,
        height: int = 560,
    ) -> bool: ...


class _AskProbeChoiceDialogFn(Protocol):
    def __call__(
        self,
        window: _SupportWindowLike,
        *,
        title: str,
        prompt: str,
        tk: object,
        ttk: object,
        choices: list[tuple[str, object]],
        width: int = 520,
        height: int = 240,
    ) -> object: ...


class _AskProbeNotesDialogFn(Protocol):
    def __call__(
        self,
        window: _SupportWindowLike,
        *,
        title: str,
        prompt: str,
        tk: object,
        ttk: object,
        scrolledtext: object,
        width: int = 720,
        height: int = 340,
    ) -> str | None: ...


class _RunInThreadFn(Protocol):
    def __call__(
        self,
        root: object,
        work: Callable[[], _ProbeResult],
        on_done: Callable[[_ProbeResult], None],
    ) -> None: ...


def run_backend_speed_probe(
    window: _SupportWindowLike,
    *,
    prompt: bool,
    current_backend_speed_probe_plan_fn: _CurrentBackendSpeedProbePlanFn,
    tk_runtime_errors: _TkRuntimeErrors,
    run_in_thread: _RunInThreadFn,
    config_cls: _ProbeConfigFactory,
    tray_pid: str,
    sleep_fn: _SleepFn,
    format_probe_speed_list_fn: _FormatProbeSpeedListFn,
    tray_process_alive_fn: _TrayProcessAliveFn,
    auto_run_backend_speed_probe_fn: _AutoRunBackendSpeedProbeFn,
    complete_backend_speed_probe_fn: _CompleteBackendSpeedProbeFn,
    show_probe_message_dialog: _ShowProbeMessageDialogFn,
    ask_probe_choice_dialog: _AskProbeChoiceDialogFn,
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> None:
    plan_candidate = current_backend_speed_probe_plan_fn()
    if not isinstance(plan_candidate, dict):
        window._set_status("No guided backend probe available", ok=False)
        return
    plan = cast(_ProbePlan, plan_candidate)

    selection_effect_name = str(plan.get("selection_effect_name") or plan.get("effect_name") or "").strip()
    auto_run_available = tray_process_alive_fn(tray_pid)
    if not auto_run_available:
        window._set_status("Backend speed probe requires the running tray session", ok=False)
        return

    if prompt:
        requested_speed_text = format_probe_speed_list_fn(plan.get("requested_ui_speeds"))
        prompt_message = (
            "Run the guided backend speed probe through the tray now?\n\n"
            "KeyRGB will temporarily switch to the probe effect, hold each test speed for about "
            f"{_PROBE_AUTO_STEP_DURATION_S:.1f} seconds"
            + (f" ({requested_speed_text})" if requested_speed_text else "")
            + ", restore the previous tray effect, and then ask for your observation."
        )
        try:
            ok = ask_probe_choice_dialog(
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
        requested_speed_text = format_probe_speed_list_fn(plan.get("requested_ui_speeds"))
        show_probe_message_dialog(
            window,
            title="Backend Speed Probe",
            message=(
                "KeyRGB will temporarily switch the tray to the probe effect, play each listed speed step, "
                "and then restore the previous tray effect.\n\n"
                + (f"Requested speeds: {requested_speed_text}.\n" if requested_speed_text else "")
                + f"Each speed will stay active for about {_PROBE_AUTO_STEP_DURATION_S:.1f} seconds "
                "with a short settle gap before the next step.\n\n"
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

    def work() -> _ProbeResult:
        try:
            return {
                "ok": True,
                "payload": auto_run_backend_speed_probe_fn(
                    plan,
                    config_cls=config_cls,
                    sleep_fn=sleep_fn,
                ),
            }
        except _PROBE_AUTOMATION_ERRORS as exc:
            return {"ok": False, "error": str(exc).strip() or exc.__class__.__name__}

    def on_done(result: _ProbeResult) -> None:
        window.btn_run_speed_probe.configure(state="normal")
        if not bool(result.get("ok")):
            window._sync_button_state()
            window._set_status("Automatic backend speed probe failed", ok=False)
            return

        payload = result.get("payload")
        complete_backend_speed_probe_fn(
            window,
            plan=plan,
            selection_effect_name=selection_effect_name,
            started_at=started_at,
            automation_result=cast(_ProbeResult, payload) if isinstance(payload, dict) else None,
            tk_runtime_errors=tk_runtime_errors,
            tk=tk,
            ttk=ttk,
            scrolledtext=scrolledtext,
        )

    run_in_thread(window.root, work, on_done)


def _complete_backend_speed_probe(
    window: _SupportWindowLike,
    *,
    plan: _ProbePlan,
    selection_effect_name: str,
    started_at: str,
    automation_result: _ProbeResult | None,
    tk_runtime_errors: _TkRuntimeErrors,
    ask_probe_choice_dialog: _AskProbeChoiceDialogFn,
    ask_probe_notes_dialog: _AskProbeNotesDialogFn,
    tk: object,
    ttk: object,
    scrolledtext: object,
) -> None:
    try:
        distinct_steps = ask_probe_choice_dialog(
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
        notes = ask_probe_notes_dialog(
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
