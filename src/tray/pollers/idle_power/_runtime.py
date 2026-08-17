from __future__ import annotations

# @quality-exception file-size-analysis: idle-power runtime state machine; policy/sensors/actions already live in sibling modules
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.core.utils.safe_attrs import safe_bool_attr, safe_int_attr, safe_str_attr
from src.tray.controllers.runtime_coordination import (
    capture_transition_revision,
    run_tray_observation_if_current,
    run_tray_transition,
)
from src.tray.idle_power_state import (
    is_dim_temp_active,
    read_forced_off_flags,
    read_idle_power_state_bool_field,
    read_idle_power_state_float_field,
    read_last_resume_at,
)
from src.tray.protocols import IdlePowerTrayProtocol

from ._actions import restore_from_idle
from ._constants import POST_POWER_SOURCE_CHANGE_IDLE_ACTION_SUPPRESSION_S
from ._input_idle import InputIdleTracker
from ._power_source_guard import (
    plan_power_source_guard_update,
    power_source_idle_guard_active as _pure_power_source_idle_guard_active,
)
from ._runtime_sensors import (
    read_desktop_dimmed_state as _read_desktop_dimmed_state,
    read_session_idle_state as _read_session_idle_state,
)
from .policy import IdleAction
from .sensors import BacklightState

logger = logging.getLogger(__name__)

# Idle-power per-iteration diagnostic boundary; drop map LookupError.
_IDLE_POWER_RUNTIME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_IDLE_POWER_IMPORT_EXCEPTIONS = (ImportError,) + _IDLE_POWER_RUNTIME_EXCEPTIONS


@dataclass
class IdlePollLoopState:
    last_error_at: float = 0.0
    last_action_key: str | None = None
    dimmed_true_streak: int = 0
    dimmed_false_streak: int = 0
    screen_off_true_streak: int = 0
    last_on_ac_power: bool | None = None
    last_power_source_change_at: float = 0.0
    backlight_state: BacklightState = field(default_factory=BacklightState)
    input_idle_tracker: InputIdleTracker | None = None
    wayland_idle_tracker: object | None = None
    prev_session_idle: bool | None = None


def _keyboard_activity_after(
    *,
    loop_state: IdlePollLoopState,
    timestamp: float,
    create_input_idle_tracker_fn: Callable[[], InputIdleTracker] | None,
    read_input_idle_seconds_fn: Callable[[InputIdleTracker], float | None] | None,
) -> bool:
    """Poll evdev if available and test for keyboard activity after a timestamp."""

    if timestamp <= 0:
        return False
    tracker = loop_state.input_idle_tracker
    if tracker is None and create_input_idle_tracker_fn is not None:
        try:
            tracker = create_input_idle_tracker_fn()
            loop_state.input_idle_tracker = tracker
        except _IDLE_POWER_RUNTIME_EXCEPTIONS:
            return False
    if tracker is not None and read_input_idle_seconds_fn is not None:
        try:
            # Wayland normally owns idle detection and therefore does not poll
            # evdev. Poll explicitly for this keypress-only wake policy.
            read_input_idle_seconds_fn(tracker)
        except _IDLE_POWER_RUNTIME_EXCEPTIONS:
            return False
    if tracker is None:
        return False
    try:
        last_keyboard_activity_at = float(getattr(tracker, "last_keyboard_activity_at", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False
    return last_keyboard_activity_at > timestamp


def _run_idle_power_runtime_boundary_best_effort(operation: Callable[[], None]) -> None:
    try:
        operation()
    except _IDLE_POWER_RUNTIME_EXCEPTIONS:  # @quality-exception exception-transparency: idle-power per-iteration config refresh and idle action diagnostics cross recoverable runtime/config boundaries; polling must stay non-fatal without recursive hot-path logging while unexpected defects still propagate
        return


def _rearm_controller_sleep_restore(tray: IdlePowerTrayProtocol) -> bool:
    """Reset the ITE off latch before restoring from honored firmware sleep."""

    try:
        # Hardware evidence shows that user-mode and brightness writes can be
        # accepted while the deck remains latched dark after controller sleep.
        # A fresh explicit off immediately before the normal soft-on sequence
        # resets that latch, matching the manual off->on recovery path.
        tray.engine.turn_off()
    except _IDLE_POWER_RUNTIME_EXCEPTIONS:
        logger.warning("Controller-sleep hardware re-arm failed", exc_info=True)
        return False
    logger.info("EVENT idle_power:controller_sleep_rearm trigger=keyboard_evdev")
    return True


def _maybe_restore_from_controller_sleep(
    tray: IdlePowerTrayProtocol,
    *,
    loop_state: IdlePollLoopState,
    session_idle: bool | None,
    create_input_idle_tracker_fn: Callable[[], InputIdleTracker] | None = None,
    read_input_idle_seconds_fn: Callable[[InputIdleTracker], float | None] | None = None,
    observation_revision: int | None = None,
) -> None:
    """Restore the deck after controller sleep on keyboard activity only.

    Only meaningful when the opt-in controller-sleep respect left the deck
    dark. Restore when evdev reports keyboard activity newer than the sleep
    timestamp. Mouse, touchpad, and bare compositor resume events deliberately
    do not wake keyboard lighting: the setting promises to wait for a keypress.

    Do **not** level-trigger on bare ``session_idle is False``: that combined
    with a false-positive sleep detection (ITE transient zero while reactive
    was still running) journals as a random off→on soft-on blink.  The opt-in
    is "leave dark until the next input"; edge/activity restore matches that.
    """

    if not read_idle_power_state_bool_field(
        tray,
        attr_name="_controller_sleep_off",
        state_name="controller_sleep_off",
        default=False,
    ):
        return
    sleep_at = read_idle_power_state_float_field(
        tray,
        attr_name="_controller_sleep_off_at",
        state_name="controller_sleep_off_at",
        default=0.0,
    )
    if sleep_at <= 0:
        return

    if not _keyboard_activity_after(
        loop_state=loop_state,
        timestamp=sleep_at,
        create_input_idle_tracker_fn=create_input_idle_tracker_fn,
        read_input_idle_seconds_fn=read_input_idle_seconds_fn,
    ):
        return

    def restore_transition() -> None:
        # Hardware polling may have observed the controller's own first-keypress
        # wake and restarted the stopped effect while evdev was being polled. Do
        # not follow that successful fallback with a second explicit off->soft-on.
        if not read_idle_power_state_bool_field(
            tray,
            attr_name="_controller_sleep_off",
            state_name="controller_sleep_off",
            default=False,
        ):
            return
        if not _rearm_controller_sleep_restore(tray):
            return
        logger.info("EVENT idle_power:controller_sleep_restore trigger=keyboard_evdev")
        restore_from_idle(tray)

    run_tray_observation_if_current(tray, observation_revision, restore_transition)


def _log_idle_action_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    action: IdleAction,
    dimmed: bool | None,
    screen_off: bool,
    brightness: int,
    dim_sync_enabled: bool,
    dim_sync_mode: str,
    dim_temp_brightness: int,
) -> None:
    def _log_event() -> None:
        user_forced_off, power_forced_off, idle_forced_off = read_forced_off_flags(tray)
        tray._log_event(
            "idle_power",
            str(action),
            dimmed=dimmed,
            screen_off=bool(screen_off),
            config_brightness=int(brightness),
            dim_sync_enabled=bool(dim_sync_enabled),
            dim_sync_mode=str(dim_sync_mode),
            dim_temp_brightness=int(dim_temp_brightness),
            is_off=bool(tray.is_off),
            user_forced_off=user_forced_off,
            power_forced_off=power_forced_off,
            idle_forced_off=idle_forced_off,
            dim_temp_active=is_dim_temp_active(tray),
        )

    _run_idle_power_runtime_boundary_best_effort(_log_event)


def _reload_idle_power_config_best_effort(tray: IdlePowerTrayProtocol) -> None:
    reload_config = getattr(tray.config, "reload", None)
    if not callable(reload_config):
        return

    _run_idle_power_runtime_boundary_best_effort(reload_config)


def _read_on_ac_power_best_effort() -> bool | None:
    try:
        from src.core.power.monitoring.power_supply_sysfs import read_on_ac_power
    except _IDLE_POWER_IMPORT_EXCEPTIONS:
        return None

    try:
        return read_on_ac_power()
    except _IDLE_POWER_RUNTIME_EXCEPTIONS:
        return None


def _reset_power_source_sensitive_idle_state(loop_state: IdlePollLoopState) -> None:
    loop_state.dimmed_true_streak = 0
    loop_state.dimmed_false_streak = 0
    loop_state.screen_off_true_streak = 0
    loop_state.backlight_state.baselines.clear()
    loop_state.backlight_state.dimmed.clear()
    loop_state.backlight_state.screen_off = False


def _update_power_source_idle_guard(
    *,
    loop_state: IdlePollLoopState,
    on_ac_power: bool | None,
    now: float,
) -> None:
    plan = plan_power_source_guard_update(
        on_ac_power=on_ac_power,
        last_on_ac_power=loop_state.last_on_ac_power,
        last_power_source_change_at=float(loop_state.last_power_source_change_at or 0.0),
        now=float(now),
    )
    if plan is None:
        return
    loop_state.last_on_ac_power = plan.last_on_ac_power
    loop_state.last_power_source_change_at = plan.last_power_source_change_at
    if plan.reset_sensitive_idle_state:
        _reset_power_source_sensitive_idle_state(loop_state)


def _power_source_idle_guard_active(*, loop_state: IdlePollLoopState, now: float) -> bool:
    return _pure_power_source_idle_guard_active(
        now=float(now),
        last_power_source_change_at=float(loop_state.last_power_source_change_at or 0.0),
        suppression_s=POST_POWER_SOURCE_CHANGE_IDLE_ACTION_SUPPRESSION_S,
    )


def run_idle_power_iteration(
    tray: IdlePowerTrayProtocol,
    *,
    loop_state: IdlePollLoopState,
    idle_timeout_s: float,
    session_id: str | None,
    now_monotonic_fn: Callable[[], float],
    ensure_idle_state_fn: Callable[[IdlePowerTrayProtocol], None],
    read_dimmed_state_fn: Callable[[BacklightState], bool | None],
    read_screen_off_state_drm_fn: Callable[[], bool | None],
    debounce_dim_and_screen_off_fn: Callable[..., tuple[bool | None, bool, int, int, int]],
    read_logind_idle_seconds_fn: Callable[..., float | None],
    read_desktop_dim_timeout_fn: Callable[[bool | None], float | None],
    create_wayland_idle_tracker_fn: Callable[[int], object | None],
    read_wayland_idle_fn: Callable[[Any], bool | None],
    create_input_idle_tracker_fn: Callable[[], InputIdleTracker],
    read_input_idle_seconds_fn: Callable[[InputIdleTracker], float | None],
    effective_screen_dim_sync_enabled_fn: Callable[[IdlePowerTrayProtocol, bool], bool],
    compute_idle_action_fn: Callable[..., IdleAction],
    build_idle_action_key_fn: Callable[..., str],
    should_log_idle_action_fn: Callable[..., bool],
    apply_idle_action_fn: Callable[..., None],
    read_on_ac_power_fn: Callable[[], bool | None] | None = None,
) -> None:
    ensure_idle_state_fn(tray)

    run_tray_transition(tray, lambda: _reload_idle_power_config_best_effort(tray))
    observation_revision = capture_transition_revision(tray)
    now = float(now_monotonic_fn())
    read_on_ac = read_on_ac_power_fn or _read_on_ac_power_best_effort
    _update_power_source_idle_guard(
        loop_state=loop_state,
        on_ac_power=read_on_ac(),
        now=now,
    )

    # Primary dim signal: system dim timeout + session idle.  On Wayland the
    # compositor's idle notifier is preferred because it sees touchpads and
    # other devices that raw evdev cannot; otherwise we fall back to evdev.
    on_ac_power = read_on_ac()
    dimmed, session_idle = _read_desktop_dimmed_state(
        loop_state=loop_state,
        on_ac_power=on_ac_power,
        read_desktop_dim_timeout_fn=read_desktop_dim_timeout_fn,
        create_wayland_idle_tracker_fn=create_wayland_idle_tracker_fn,
        read_wayland_idle_fn=read_wayland_idle_fn,
        create_input_idle_tracker_fn=create_input_idle_tracker_fn,
        read_input_idle_seconds_fn=read_input_idle_seconds_fn,
        fallback_timeout_s=float(idle_timeout_s),
    )

    dimmed_source = "wayland_or_evdev" if dimmed is not None else "none"

    # Fallback dim signal: relative backlight brightness drop.  Used when the
    # desktop timeout or evdev input idle is unavailable.
    if dimmed is None:
        dimmed = read_dimmed_state_fn(loop_state.backlight_state)
        if dimmed is not None:
            dimmed_source = "brightness_heuristic"

    screen_off = bool(loop_state.backlight_state.screen_off) or bool(read_screen_off_state_drm_fn())

    (
        dimmed,
        screen_off,
        loop_state.dimmed_true_streak,
        loop_state.dimmed_false_streak,
        loop_state.screen_off_true_streak,
    ) = debounce_dim_and_screen_off_fn(
        dimmed_raw=dimmed,
        screen_off_raw=bool(screen_off),
        dimmed_true_streak=loop_state.dimmed_true_streak,
        dimmed_false_streak=loop_state.dimmed_false_streak,
        screen_off_true_streak=loop_state.screen_off_true_streak,
        debounce_polls_dimmed_true=safe_int_attr(
            tray.config, "idle_dim_debounce_enter_polls", default=6, min_v=1, max_v=60
        ),
        debounce_polls_dimmed_false=safe_int_attr(
            tray.config, "idle_dim_debounce_exit_polls", default=10, min_v=1, max_v=60
        ),
        debounce_polls_screen_off_true=4,
    )

    power_mgmt_enabled = safe_bool_attr(tray.config, "power_management_enabled", default=True)
    brightness = safe_int_attr(tray.config, "brightness", default=0)

    dim_sync_enabled_requested = safe_bool_attr(tray.config, "screen_dim_sync_enabled", default=True)
    dim_sync_enabled = effective_screen_dim_sync_enabled_fn(tray, bool(dim_sync_enabled_requested))
    dim_sync_mode = safe_str_attr(tray.config, "screen_dim_sync_mode", default="off") or "off"
    dim_temp_brightness = safe_int_attr(tray.config, "screen_dim_temp_brightness", default=5, min_v=1, max_v=50)

    # Tertiary fallback: logind session idle (used when neither the desktop
    # timeout/input-idle path nor the brightness heuristic could determine state).
    if session_idle is None:
        restore_candidate = bool(dimmed is False and (bool(tray.is_off) or is_dim_temp_active(tray)))
        if dimmed is None or restore_candidate:
            session_idle = _read_session_idle_state(
                session_id=session_id,
                idle_timeout_s=float(idle_timeout_s),
                read_logind_idle_seconds_fn=read_logind_idle_seconds_fn,
            )

    if dimmed is None and session_idle is not None:
        dimmed = bool(session_idle)
        dimmed_source = "logind"

    if dimmed is None:
        dimmed_source = "none"

    logger.debug(
        "idle_power:dimmed_source source=%s dimmed=%s session_idle=%s screen_off=%s",
        dimmed_source,
        dimmed,
        session_idle,
        bool(screen_off),
    )

    _maybe_restore_from_controller_sleep(
        tray,
        loop_state=loop_state,
        session_idle=session_idle,
        create_input_idle_tracker_fn=create_input_idle_tracker_fn,
        read_input_idle_seconds_fn=read_input_idle_seconds_fn,
        observation_revision=observation_revision,
    )
    loop_state.prev_session_idle = session_idle

    user_forced_off, power_forced_off, idle_forced_off = read_forced_off_flags(tray)
    last_idle_turn_off_at = read_idle_power_state_float_field(
        tray,
        attr_name="_last_idle_turn_off_at",
        state_name="last_idle_turn_off_at",
        default=0.0,
    )
    idle_restore_requires_keyboard = bool(
        idle_forced_off and safe_bool_attr(tray.config, "controller_sleep_respect", default=False)
    )
    keyboard_activity_after_idle_off = False
    if idle_restore_requires_keyboard:
        keyboard_activity_after_idle_off = _keyboard_activity_after(
            loop_state=loop_state,
            timestamp=last_idle_turn_off_at,
            create_input_idle_tracker_fn=create_input_idle_tracker_fn,
            read_input_idle_seconds_fn=read_input_idle_seconds_fn,
        )
    action = compute_idle_action_fn(
        dimmed=dimmed,
        screen_off=bool(screen_off),
        idle_timeout_s=float(idle_timeout_s),
        is_off=bool(tray.is_off),
        idle_forced_off=idle_forced_off,
        dim_temp_active=is_dim_temp_active(tray),
        power_management_enabled=bool(power_mgmt_enabled),
        screen_dim_sync_enabled=bool(dim_sync_enabled),
        screen_dim_sync_mode=str(dim_sync_mode),
        screen_dim_temp_brightness=int(dim_temp_brightness),
        brightness=int(brightness),
        user_forced_off=user_forced_off,
        power_forced_off=power_forced_off,
        last_idle_turn_off_at=last_idle_turn_off_at,
        last_resume_at=read_last_resume_at(tray),
        now=now,
        session_idle=session_idle,
        controller_sleep_off=read_idle_power_state_bool_field(
            tray,
            attr_name="_controller_sleep_off",
            state_name="controller_sleep_off",
            default=False,
        ),
        idle_restore_requires_keyboard=idle_restore_requires_keyboard,
        keyboard_activity_after_idle_off=keyboard_activity_after_idle_off,
    )
    if _power_source_idle_guard_active(loop_state=loop_state, now=now):
        action = None
    if action == "restore" and idle_restore_requires_keyboard and keyboard_activity_after_idle_off:
        logger.info("EVENT idle_power:screen_idle_restore trigger=keyboard_evdev")

    action_key = build_idle_action_key_fn(
        action=action,
        dimmed=dimmed,
        screen_off=bool(screen_off),
        brightness=int(brightness),
        dim_sync_mode=str(dim_sync_mode),
        dim_temp_brightness=int(dim_temp_brightness),
    )

    if should_log_idle_action_fn(
        action=action,
        action_key=action_key,
        last_action_key=loop_state.last_action_key,
    ):
        loop_state.last_action_key = action_key
        _log_idle_action_best_effort(
            tray,
            action=action,
            dimmed=dimmed,
            screen_off=bool(screen_off),
            brightness=int(brightness),
            dim_sync_enabled=bool(dim_sync_enabled),
            dim_sync_mode=str(dim_sync_mode),
            dim_temp_brightness=int(dim_temp_brightness),
        )

    run_tray_observation_if_current(
        tray,
        observation_revision,
        lambda: apply_idle_action_fn(
            tray,
            action=action,
            dim_temp_brightness=int(dim_temp_brightness),
        ),
    )
