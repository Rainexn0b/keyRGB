from __future__ import annotations

from functools import lru_cache
import logging
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from ._polling_support import call_best_effort as _call_best_effort_impl
from ._polling_support import effective_screen_dim_sync_enabled as _effective_screen_dim_sync_enabled_impl
from ._polling_support import ensure_idle_state as _ensure_idle_state_impl
from ._polling_support import poll_idle_power_loop as _poll_idle_power_loop
from ._polling_support import recover_idle_power_polling_error as _recover_idle_power_polling_error_impl
from ._polling_support import tray_log_event_or_none as _tray_log_event_or_none_impl
from ._polling_support import tray_log_exception_or_none as _tray_log_exception_or_none_impl
from ._runtime import run_idle_power_iteration


if TYPE_CHECKING:
    from src.tray.protocols import IdlePowerTrayProtocol

    from ._runtime import IdlePollLoopState
    from .policy import IdleAction
    from .sensors import BacklightState
else:
    IdlePowerTrayProtocol = object


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _effect_sets() -> tuple[frozenset[str], frozenset[str]]:
    from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET

    return frozenset(REACTIVE_EFFECTS), SW_EFFECTS_SET


def _tray_log_exception_or_none(tray: object) -> Callable[..., object] | None:
    return _tray_log_exception_or_none_impl(tray)


def _tray_log_event_or_none(tray: object) -> Callable[..., object] | None:
    return _tray_log_event_or_none_impl(tray)


def _log_module_exception(msg: str, exc: Exception) -> None:
    logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _call_best_effort(
    func: Callable[..., object] | None,
    *args: object,
    on_recoverable: Callable[[Exception], None],
    **kwargs: object,
) -> bool:
    return _call_best_effort_impl(
        func,
        *args,
        on_recoverable=on_recoverable,
        **kwargs,
    )


def _log_tray_exception(tray: IdlePowerTrayProtocol, msg: str, exc: Exception) -> None:
    if _call_best_effort(
        _tray_log_exception_or_none(tray),
        msg,
        exc,
        on_recoverable=lambda log_exc: _log_module_exception("Idle power tray exception logger failed: %s", log_exc),
    ):
        return

    _log_module_exception(msg, exc)


def _try_log_event(tray: IdlePowerTrayProtocol, source: str, action: str, **fields: object) -> None:
    _call_best_effort(
        _tray_log_event_or_none(tray),
        source,
        action,
        on_recoverable=lambda exc: _log_tray_exception(tray, "Idle power event logging failed: %s", exc),
        **fields,
    )


def _recover_idle_power_polling_error(
    tray: IdlePowerTrayProtocol,
    loop_state: IdlePollLoopState,
    exc: Exception,
) -> None:
    return _recover_idle_power_polling_error_impl(
        tray,
        loop_state,
        exc,
        monotonic_fn=time.monotonic,
        log_tray_exception_fn=_log_tray_exception,
    )


def _effective_screen_dim_sync_enabled(tray: IdlePowerTrayProtocol, requested_enabled: bool) -> bool:
    return _effective_screen_dim_sync_enabled_impl(
        tray,
        requested_enabled,
        try_log_event_fn=_try_log_event,
    )


def _compute_idle_action(
    *,
    dimmed: Optional[bool],
    screen_off: bool,
    is_off: bool,
    idle_forced_off: bool,
    dim_temp_active: bool,
    idle_timeout_s: float,
    power_management_enabled: bool,
    screen_dim_sync_enabled: bool,
    screen_dim_sync_mode: str,
    screen_dim_temp_brightness: int,
    brightness: int,
    user_forced_off: bool,
    power_forced_off: bool,
    last_idle_turn_off_at: float = 0.0,
    last_resume_at: float = 0.0,
    now: float = 0.0,
) -> IdleAction:
    from .policy import compute_idle_action

    return compute_idle_action(
        dimmed=dimmed,
        screen_off=screen_off,
        is_off=is_off,
        idle_forced_off=idle_forced_off,
        dim_temp_active=dim_temp_active,
        idle_timeout_s=idle_timeout_s,
        power_management_enabled=power_management_enabled,
        screen_dim_sync_enabled=screen_dim_sync_enabled,
        screen_dim_sync_mode=screen_dim_sync_mode,
        screen_dim_temp_brightness=screen_dim_temp_brightness,
        brightness=brightness,
        user_forced_off=user_forced_off,
        power_forced_off=power_forced_off,
        last_idle_turn_off_at=last_idle_turn_off_at,
        last_resume_at=last_resume_at,
        now=now,
    )


def _ensure_idle_state(tray: IdlePowerTrayProtocol) -> None:
    _ensure_idle_state_impl(tray)


def _read_dimmed_state(state: BacklightState) -> Optional[bool]:
    from .sensors import read_dimmed_state

    return read_dimmed_state(state)


def _read_screen_off_state_drm() -> Optional[bool]:
    from .sensors import read_screen_off_state_drm

    return read_screen_off_state_drm()


def _run(argv: list[str], *, timeout_s: float = 1.0) -> Optional[str]:
    from .sensors import run

    return run(argv, timeout_s=timeout_s)


def _get_session_id() -> Optional[str]:
    from .sensors import get_session_id

    return get_session_id()


def _read_logind_idle_seconds(*, session_id: str) -> Optional[float]:
    from ._logind import read_logind_idle_seconds

    return read_logind_idle_seconds(
        session_id=session_id,
        run_fn=lambda argv, timeout_s: _run(argv, timeout_s=timeout_s),
        monotonic_fn=time.monotonic,
    )


def _restore_from_idle(tray: IdlePowerTrayProtocol) -> None:
    from ._actions import restore_from_idle

    return restore_from_idle(tray)


def _apply_idle_action(
    tray: IdlePowerTrayProtocol,
    *,
    action: IdleAction,
    dim_temp_brightness: int,
) -> None:
    from ._actions import apply_idle_action

    reactive_effects_set, sw_effects_set = _effect_sets()

    return apply_idle_action(
        tray,
        action=action,
        dim_temp_brightness=int(dim_temp_brightness),
        restore_from_idle_fn=_restore_from_idle,
        reactive_effects_set=reactive_effects_set,
        sw_effects_set=sw_effects_set,
    )


def _debounce_dim_and_screen_off(
    *,
    dimmed_raw: Optional[bool],
    screen_off_raw: bool,
    dimmed_true_streak: int,
    dimmed_false_streak: int,
    screen_off_true_streak: int,
    debounce_polls_dimmed_true: int,
    debounce_polls_dimmed_false: int,
    debounce_polls_screen_off_true: int,
) -> tuple[Optional[bool], bool, int, int, int]:
    from ._utils import debounce_dim_and_screen_off

    return debounce_dim_and_screen_off(
        dimmed_raw=dimmed_raw,
        screen_off_raw=screen_off_raw,
        dimmed_true_streak=dimmed_true_streak,
        dimmed_false_streak=dimmed_false_streak,
        screen_off_true_streak=screen_off_true_streak,
        debounce_polls_dimmed_true=debounce_polls_dimmed_true,
        debounce_polls_dimmed_false=debounce_polls_dimmed_false,
        debounce_polls_screen_off_true=debounce_polls_screen_off_true,
    )


def _build_idle_action_key(
    *,
    action: IdleAction,
    dimmed: Optional[bool],
    screen_off: bool,
    brightness: int,
    dim_sync_mode: str,
    dim_temp_brightness: int,
) -> str:
    from ._utils import build_idle_action_key

    return build_idle_action_key(
        action=action,
        dimmed=dimmed,
        screen_off=screen_off,
        brightness=brightness,
        dim_sync_mode=dim_sync_mode,
        dim_temp_brightness=dim_temp_brightness,
    )


def _should_log_idle_action(
    *,
    action: IdleAction,
    action_key: str,
    last_action_key: Optional[str],
) -> bool:
    from ._utils import should_log_idle_action

    return should_log_idle_action(
        action=action,
        action_key=str(action_key),
        last_action_key=last_action_key,
    )


def start_idle_power_polling(
    tray: IdlePowerTrayProtocol,
    *,
    ite_num_rows: int,
    ite_num_cols: int,
    idle_timeout_s: float = 60.0,
) -> None:
    """Power-management: sync keyboard lighting with display dimming."""

    _ensure_idle_state(tray)

    def poll_idle_power() -> None:
        from ._runtime import IdlePollLoopState

        _poll_idle_power_loop(
            tray,
            idle_timeout_s=float(idle_timeout_s),
            create_loop_state_fn=IdlePollLoopState,
            get_session_id_fn=_get_session_id,
            run_idle_power_iteration_fn=run_idle_power_iteration,
            now_monotonic_fn=time.monotonic,
            sleep_fn=time.sleep,
            ensure_idle_state_fn=_ensure_idle_state,
            read_dimmed_state_fn=_read_dimmed_state,
            read_screen_off_state_drm_fn=_read_screen_off_state_drm,
            debounce_dim_and_screen_off_fn=_debounce_dim_and_screen_off,
            read_logind_idle_seconds_fn=_read_logind_idle_seconds,
            effective_screen_dim_sync_enabled_fn=_effective_screen_dim_sync_enabled,
            compute_idle_action_fn=_compute_idle_action,
            build_idle_action_key_fn=_build_idle_action_key,
            should_log_idle_action_fn=_should_log_idle_action,
            apply_idle_action_fn=_apply_idle_action,
            call_best_effort_fn=_call_best_effort,
            recover_idle_power_polling_error_fn=_recover_idle_power_polling_error,
        )

    threading.Thread(target=poll_idle_power, daemon=True).start()


__all__ = [
    "start_idle_power_polling",
    "_compute_idle_action",
]
