from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias, TypeVar

from src.tray.protocols import ConfigPollingTrayProtocol


_LOG_WRITE_EXCEPTIONS = (OSError, RuntimeError, ValueError)
_ResultT = TypeVar("_ResultT")
MonotonicFn: TypeAlias = Callable[[], float]
DeviceDisconnectedFn: TypeAlias = Callable[[Exception], bool]
StateForLogFn: TypeAlias = Callable[[object], object | None]


class CurrentConfigLike(Protocol):
    effect: str
    brightness: int


class ApplyPlanLike(Protocol):
    @property
    def execution_kind(self) -> str: ...


class SyncReactiveFn(Protocol):
    def __call__(self, tray: ConfigPollingTrayProtocol, current: CurrentConfigLike) -> None: ...


class ApplyPerkeyFn(Protocol):
    def __call__(
        self,
        tray: ConfigPollingTrayProtocol,
        current: CurrentConfigLike,
        ite_num_rows: int,
        ite_num_cols: int,
        *,
        cause: str,
    ) -> None: ...


class ApplyUniformFn(Protocol):
    def __call__(self, tray: ConfigPollingTrayProtocol, current: CurrentConfigLike, *, cause: str) -> None: ...


class ApplyEffectFn(Protocol):
    def __call__(self, tray: ConfigPollingTrayProtocol, current: CurrentConfigLike, *, cause: str) -> None: ...


class ApplyTurnOffFn(Protocol):
    def __call__(
        self,
        tray: ConfigPollingTrayProtocol,
        current: CurrentConfigLike,
        cause: str,
        monotonic_fn: MonotonicFn,
        last_apply_warn_at: float,
    ) -> float: ...


def _run_runtime_boundary(
    action: Callable[[], _ResultT],
    *,
    runtime_boundary_exceptions: tuple[type[Exception], ...],
    on_recoverable: Callable[[Exception], _ResultT],
) -> _ResultT:
    try:
        return action()
    except runtime_boundary_exceptions as exc:  # @quality-exception exception-transparency: config-apply backend calls, degraded device-unavailable handling, and post-apply tray UI refresh all cross the same recoverable runtime boundaries and must stay contained while unexpected defects still propagate
        return on_recoverable(exc)


def _throttled_log_exception(
    tray: ConfigPollingTrayProtocol,
    *,
    msg: str,
    exc: Exception,
    monotonic_fn: MonotonicFn,
    last_apply_warn_at: float,
) -> float:
    now = float(monotonic_fn())
    if now - last_apply_warn_at <= 60:
        return last_apply_warn_at

    try:
        tray._log_exception(msg, exc)
    except _LOG_WRITE_EXCEPTIONS:
        pass
    return now


def _mark_device_unavailable_best_effort(
    tray: ConfigPollingTrayProtocol,
    *,
    last_apply_warn_at: float,
    monotonic_fn: MonotonicFn,
    runtime_boundary_exceptions: tuple[type[Exception], ...],
) -> float:
    def _mark_device_unavailable() -> float:
        tray.engine.mark_device_unavailable()
        return last_apply_warn_at

    return _run_runtime_boundary(
        _mark_device_unavailable,
        runtime_boundary_exceptions=runtime_boundary_exceptions,
        on_recoverable=lambda exc: _throttled_log_exception(
            tray,
            msg="Failed to mark device unavailable: %s",
            exc=exc,
            monotonic_fn=monotonic_fn,
            last_apply_warn_at=last_apply_warn_at,
        ),
    )


def _refresh_ui_best_effort(
    tray: ConfigPollingTrayProtocol,
    *,
    last_apply_warn_at: float,
    monotonic_fn: MonotonicFn,
    runtime_boundary_exceptions: tuple[type[Exception], ...],
) -> float:
    def _refresh_ui() -> float:
        tray._refresh_ui()
        return last_apply_warn_at

    return _run_runtime_boundary(
        _refresh_ui,
        runtime_boundary_exceptions=runtime_boundary_exceptions,
        on_recoverable=lambda exc: _throttled_log_exception(
            tray,
            msg="Failed to refresh tray UI after config apply: %s",
            exc=exc,
            monotonic_fn=monotonic_fn,
            last_apply_warn_at=last_apply_warn_at,
        ),
    )


def apply_post_fast_path_execution(
    tray: ConfigPollingTrayProtocol,
    *,
    current: CurrentConfigLike,
    ite_num_rows: int,
    ite_num_cols: int,
    cause: str,
    last_apply_warn_at: float,
    monotonic_fn: MonotonicFn,
    is_device_disconnected_fn: DeviceDisconnectedFn,
    sync_reactive_fn: SyncReactiveFn,
    apply_perkey_fn: ApplyPerkeyFn,
    apply_uniform_fn: ApplyUniformFn,
    apply_effect_fn: ApplyEffectFn,
    runtime_boundary_exceptions: tuple[type[Exception], ...],
) -> float:
    brightness = current.brightness
    if brightness > 0:
        tray._last_brightness = brightness

    sync_reactive_fn(tray, current)

    def _apply_current() -> None:
        effect = current.effect
        if effect == "perkey":
            apply_perkey_fn(tray, current, ite_num_rows, ite_num_cols, cause=cause)
        elif effect == "none":
            apply_uniform_fn(tray, current, cause=cause)
        else:
            apply_effect_fn(tray, current, cause=cause)

    def _recover_apply(exc: Exception) -> None:
        nonlocal last_apply_warn_at
        if is_device_disconnected_fn(exc):
            last_apply_warn_at = _mark_device_unavailable_best_effort(
                tray,
                last_apply_warn_at=last_apply_warn_at,
                monotonic_fn=monotonic_fn,
                runtime_boundary_exceptions=runtime_boundary_exceptions,
            )
        tray._log_exception("Error applying config change: %s", exc)

    _run_runtime_boundary(
        _apply_current,
        runtime_boundary_exceptions=runtime_boundary_exceptions,
        on_recoverable=_recover_apply,
    )

    last_apply_warn_at = _refresh_ui_best_effort(
        tray,
        last_apply_warn_at=last_apply_warn_at,
        monotonic_fn=monotonic_fn,
        runtime_boundary_exceptions=runtime_boundary_exceptions,
    )

    return last_apply_warn_at


def execute_non_fast_path_plan(
    tray: ConfigPollingTrayProtocol,
    *,
    apply_plan: ApplyPlanLike,
    current: CurrentConfigLike,
    last_applied: object,
    cause: str,
    last_apply_warn_at: float,
    state_for_log_fn: StateForLogFn,
    monotonic_fn: MonotonicFn,
    ite_num_rows: int,
    ite_num_cols: int,
    is_device_disconnected_fn: DeviceDisconnectedFn,
    apply_turn_off_fn: ApplyTurnOffFn,
    sync_reactive_fn: SyncReactiveFn,
    apply_perkey_fn: ApplyPerkeyFn,
    apply_uniform_fn: ApplyUniformFn,
    apply_effect_fn: ApplyEffectFn,
    config_fallback_exceptions: tuple[type[Exception], ...],
    runtime_boundary_exceptions: tuple[type[Exception], ...],
) -> float:
    try:
        old_state = state_for_log_fn(last_applied)
        new_state = state_for_log_fn(current)
        tray._log_event(
            "config",
            "detected_change",
            cause=str(cause or "unknown"),
            old=old_state,
            new=new_state,
        )
    except config_fallback_exceptions:
        pass

    if apply_plan.execution_kind == "turn_off":
        return apply_turn_off_fn(tray, current, cause, monotonic_fn, last_apply_warn_at)

    return apply_post_fast_path_execution(
        tray,
        current=current,
        ite_num_rows=ite_num_rows,
        ite_num_cols=ite_num_cols,
        cause=cause,
        last_apply_warn_at=last_apply_warn_at,
        monotonic_fn=monotonic_fn,
        is_device_disconnected_fn=is_device_disconnected_fn,
        sync_reactive_fn=sync_reactive_fn,
        apply_perkey_fn=apply_perkey_fn,
        apply_uniform_fn=apply_uniform_fn,
        apply_effect_fn=apply_effect_fn,
        runtime_boundary_exceptions=runtime_boundary_exceptions,
    )
