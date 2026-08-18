"""Hardware-poll blank-recovery executors and shared polling helpers.

Extracted from ``hardware_polling.py`` (WS1 / A3 slice 1) to drop the parent
module below the REFACTOR LOC band without changing behavior. The parent
module re-imports these names so existing monkeypatch seams and tests
importing ``from src.tray.pollers.hardware_polling import _recover_*`` keep
working unchanged.

Grouping rationale: the recovery group needs the same logging, refresh, and
tray-callback-resolution helpers as the main polling loop. Moving both
together keeps the import direction one-way (``hardware_polling`` →
``_recovery``) and avoids a circular import.
"""

from __future__ import annotations

# @quality-exception file-size-analysis: cohesive hardware blank-recovery + shared poll helpers; intentionally extracted as one ownership unit from hardware_polling
import time
from collections.abc import Callable
from typing import TypeVar

from src.tray.idle_power_state import (
    any_forced_off,
    clear_idle_power_state_field,
    ensure_tray_idle_power_state,
    is_dim_temp_active,
    read_idle_power_state_bool_field,
    read_idle_power_state_float_field,
    set_idle_power_state_field,
)
from src.tray.pollers.hardware._decisions import (
    DEFAULT_HARDWARE_POLL_INTERVAL_S,
    FAST_HARDWARE_POLL_INTERVAL_S,
    POWER_SOURCE_RECOVERY_COOLDOWN_S,
    POWER_SOURCE_RECOVERY_WINDOW_S,
    STABLE_ZERO_BRIGHTNESS_BACKOFF_S,
    STABLE_ZERO_BRIGHTNESS_MAX_CONSECUTIVE_ATTEMPTS,
    STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S,
    hardware_poll_interval_s as _pure_hardware_poll_interval_s,
    power_source_recovery_window_active as _pure_power_source_recovery_window_active,
    should_attempt_power_source_blank_recovery,
    should_attempt_stable_zero_brightness_recovery,
)
from src.tray.protocols import IdlePowerTrayProtocol

_T = TypeVar("_T")

_BRIGHTNESS_COERCION_ERRORS = (TypeError, ValueError, OverflowError)
_HARDWARE_POLL_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_HARDWARE_POLL_RECOVERY_EXCEPTIONS = (OSError, RuntimeError, ValueError)


# ---------------------------------------------------------------------------
# Shared impure helpers (used by both the polling loop and the recovery group)
# ---------------------------------------------------------------------------


def _resolve_tray_callback(tray: object, name: str):
    instance_callback = vars(tray).get(name)
    if callable(instance_callback):
        return instance_callback

    class_callback = getattr(type(tray), name, None)
    if not callable(class_callback):
        return None

    return lambda *args, **kwargs: class_callback(tray, *args, **kwargs)


def _log_polled_hardware_event(tray: IdlePowerTrayProtocol, action: str, **fields: object) -> None:
    log_event = _resolve_tray_callback(tray, "_log_event")
    if not callable(log_event):
        return

    _run_recoverable_hardware_poll_boundary(
        lambda: log_event("hardware", action, **fields),
        on_recoverable=lambda _exc: None,
    )


def _refresh_ui_without_icon_animation(tray: IdlePowerTrayProtocol) -> None:
    try:
        tray._refresh_ui(animate_icon=False, refresh_menu=False)
        return
    except TypeError:
        pass
    try:
        tray._refresh_ui(animate_icon=False)
    except TypeError:
        tray._refresh_ui()


def _log_hardware_polling_error_best_effort(tray: IdlePowerTrayProtocol, exc: Exception) -> None:
    try:
        tray._log_exception("Hardware polling error: %s", exc)
    except _HARDWARE_POLL_RECOVERY_EXCEPTIONS:
        return


def _run_recoverable_hardware_poll_boundary(
    action: Callable[[], _T],
    *,
    on_recoverable: Callable[[Exception], None],
) -> _T | None:
    try:
        return action()
    except _HARDWARE_POLL_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: hardware polling crosses runtime backend I/O and best-effort tray callback seams; recoverable runtime failures must stay non-fatal while unexpected defects still propagate
        on_recoverable(exc)
        return None


# ---------------------------------------------------------------------------
# State queries (used by interval/recovery eligibility)
# ---------------------------------------------------------------------------


def _power_source_transition_at(tray: IdlePowerTrayProtocol) -> float:
    return read_idle_power_state_float_field(
        tray,
        attr_name="_last_power_source_transition_at",
        state_name="last_power_source_transition_at",
        default=0.0,
    )


def _power_source_recovery_window_active(tray: IdlePowerTrayProtocol, *, now: float) -> bool:
    return _pure_power_source_recovery_window_active(
        now=now,
        last_power_source_transition_at=_power_source_transition_at(tray),
        window_s=POWER_SOURCE_RECOVERY_WINDOW_S,
    )


def _hardware_poll_interval_s(tray: IdlePowerTrayProtocol, *, now: float) -> float:
    return _pure_hardware_poll_interval_s(
        now=now,
        last_power_source_transition_at=_power_source_transition_at(tray),
        pending_zero_confirm_at=pending_zero_confirm_at(tray),
        window_s=POWER_SOURCE_RECOVERY_WINDOW_S,
        fast_s=FAST_HARDWARE_POLL_INTERVAL_S,
        default_s=DEFAULT_HARDWARE_POLL_INTERVAL_S,
    )


def pending_zero_confirm_at(tray: IdlePowerTrayProtocol) -> float:
    """Read the pending zero-confirmation timestamp (0.0 when none)."""

    try:
        owner = ensure_tray_idle_power_state(tray)
        return float(getattr(owner, "pending_zero_confirm_at", 0.0))
    except (AttributeError, TypeError, ValueError):
        return 0.0


def set_pending_zero_confirm_at(tray: IdlePowerTrayProtocol, value: float) -> None:
    """Write the pending zero-confirmation timestamp (0.0 clears it)."""

    try:
        owner = ensure_tray_idle_power_state(tray)
        owner.pending_zero_confirm_at = max(0.0, float(value))
    except (AttributeError, TypeError, ValueError):
        return


def controller_sleep_respect_enabled(tray: IdlePowerTrayProtocol) -> bool:
    """Whether the controller's native sleep timeout is treated as an off state."""

    from src.core.utils.safe_attrs import safe_bool_attr

    return safe_bool_attr(getattr(tray, "config", None), "controller_sleep_respect", default=False)


def controller_sleep_off_active(tray: IdlePowerTrayProtocol) -> bool:
    """Whether the deck was deliberately left dark after a controller sleep."""

    return read_idle_power_state_bool_field(
        tray,
        attr_name="_controller_sleep_off",
        state_name="controller_sleep_off",
        default=False,
    )


def set_controller_sleep_off(tray: IdlePowerTrayProtocol, value: bool, *, now: float = 0.0) -> None:
    """Set/clear the controller-sleep-off state (+ its timestamp when setting)."""

    set_idle_power_state_field(
        tray,
        attr_name="_controller_sleep_off",
        state_name="controller_sleep_off",
        value=bool(value),
    )
    set_idle_power_state_field(
        tray,
        attr_name="_controller_sleep_off_at",
        state_name="controller_sleep_off_at",
        value=float(now) if value else 0.0,
    )


def _configured_brightness_intent(tray: IdlePowerTrayProtocol) -> int:
    try:
        return int(getattr(getattr(tray, "config", None), "brightness", 0))
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0


# ---------------------------------------------------------------------------
# Recovery group
# ---------------------------------------------------------------------------


def _power_source_blank_recovery_eligible(tray: IdlePowerTrayProtocol, *, now: float | None = None) -> bool:
    when = time.monotonic() if now is None else float(now)
    try:
        last_recovery_at = read_idle_power_state_float_field(
            tray,
            attr_name="_last_power_source_blank_recovery_at",
            state_name="last_power_source_blank_recovery_at",
            default=0.0,
        )
    except _BRIGHTNESS_COERCION_ERRORS:
        last_recovery_at = 0.0
    return should_attempt_power_source_blank_recovery(
        now=when,
        last_power_source_transition_at=_power_source_transition_at(tray),
        last_recovery_at=float(last_recovery_at),
        any_forced_off=any_forced_off(tray),
        configured_brightness_intent=_configured_brightness_intent(tray),
        window_s=POWER_SOURCE_RECOVERY_WINDOW_S,
        cooldown_s=POWER_SOURCE_RECOVERY_COOLDOWN_S,
    )


def _seed_reactive_restore_damp_best_effort(tray: IdlePowerTrayProtocol) -> None:
    """Seed reactive restore damp before an effect restart (defense in depth).

    ``_execute_blank_recovery`` may call ``start_current_effect()`` which runs
    ``engine.stop()`` and wipes ``_reactive_state`` — including the post-restore
    pulse damp that prevents a deck-wide flash on the first post-restart frame.
    Mirroring the idle-wake path (``_transition_actions``) we queue+apply a
    restore seed so the first keystroke after a hardware-poll-triggered restart
    stays visually damped.

    No-op for non-reactive effects and for trays without the expected engine
    or config attributes.
    """

    try:
        config = getattr(tray, "config", None)
        effect = str(getattr(config, "effect", "none") or "none")
    except _HARDWARE_POLL_RUNTIME_EXCEPTIONS:
        return

    # Late import to avoid pulling the effects catalog into the polling module
    # graph on every interpreter start; only needed when a recovery fires.
    try:
        from src.core.effects.catalog import REACTIVE_EFFECTS
        from src.core.effects.reactive._reactive_restore_seed import (
            seed_reactive_restore_windows,
        )
    except ImportError:
        return

    if effect not in REACTIVE_EFFECTS:
        return

    engine = getattr(tray, "engine", None)
    if engine is None:
        return

    try:
        seed_reactive_restore_windows(engine, fade_in_duration_s=0.0)
    except (AttributeError, TypeError, ValueError):
        return


def _configured_recovery_brightness(tray: IdlePowerTrayProtocol) -> int:
    """Brightness level to reassert during blank recovery (config intent)."""

    intent = _configured_brightness_intent(tray)
    if intent > 0:
        return int(intent)
    try:
        return max(0, int(tray.engine.brightness))
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0


def _effect_engine_is_running(tray: IdlePowerTrayProtocol) -> bool:
    engine = getattr(tray, "engine", None)
    if engine is None:
        return False
    try:
        return bool(getattr(engine, "running", False))
    except _HARDWARE_POLL_RECOVERY_EXCEPTIONS:
        return False


def _reassert_user_mode_while_running_best_effort(tray: IdlePowerTrayProtocol) -> bool:
    """Heal a mid-render blank via the render loop, not a poller brightness write.

    A standalone poller ``set_brightness`` races the reactive render thread for
    ``kb_lock`` (frame overruns) and shows up as a visible off→on dip.  The
    reactive render loop already re-applies brightness every frame — but only
    when its cached ``_last_hw_mode_brightness`` differs from the target.  After
    a firmware transient-zero the hardware is at 0 while that cache still says
    40, so the render loop skips the write and the deck stays dark until the
    poller recovers it.

    Clearing the per-key frame signature and setting ``_last_hw_mode_brightness``
    to the just-read ``0`` makes the very next frame (~33 ms away for a live
    reactive effect) call ``apply_hw_brightness`` with ``prev=0`` — a plain
    ``set_brightness(target)``.  That is the correct minimal heal: these ITE
    transient-zeros report ``is_off=False`` (user mode retained, only the
    brightness byte glitched), so no mode command / ``enable_user_mode`` is
    needed.  Using ``None`` here instead would force ``enable_user_mode_once
    (save=True)`` — a full user-mode reinit plus a persistent firmware save that
    visibly flashes and wears flash on every transient.  ``_last_rendered_brightness``
    is deliberately **preserved**: it is the anti-flicker step-guard baseline,
    and resetting it would ramp the re-light 0→8→16→… over several frames (the
    journaled flicker) instead of jumping straight back to the target.
    """

    if not _effect_engine_is_running(tray):
        return False
    engine = getattr(tray, "engine", None)
    if engine is None:
        return False
    try:
        # Record the hardware's actual (blanked) brightness so the next frame
        # issues a plain set_brightness(target) rather than skipping (cache
        # said 40) or doing a save/reinit (None).  Force a frame rewrite by
        # dropping the signature; keep the step-guard baseline intact.
        engine._last_hw_mode_brightness = 0
        try:
            engine._last_reactive_per_key_frame_signature = None
        except _HARDWARE_POLL_RECOVERY_EXCEPTIONS:
            pass
    except _HARDWARE_POLL_RECOVERY_EXCEPTIONS:
        return False
    return True


def _execute_blank_recovery(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
    now: float,
    recovery_stamp_attr: str,
    recovery_stamp_state: str,
    log_action: str,
) -> bool:
    apply_transition = _resolve_tray_callback(tray, "_apply_power_source_perkey_profile_transition")
    start_current_effect = _resolve_tray_callback(tray, "_start_current_effect")

    # Write the cooldown stamp BEFORE any tray callbacks.  This is defensive:
    # the callbacks (``apply_transition`` / ``start_current_effect`` /
    # ``_refresh_ui``) cross tray/engine/UI boundaries whose interaction with
    # the idle-power state owner is hard to audit.  Writing the stamp first
    # guarantees the cooldown window always applies, even if a callback raises
    # or resets related state.
    set_idle_power_state_field(
        tray,
        attr_name=recovery_stamp_attr,
        state_name=recovery_stamp_state,
        value=float(now),
    )

    try:
        # Prefer render-loop self-heal while a software effect is already
        # running — imperceptible single-frame re-light instead of a poller
        # brightness write that races the render thread (visible off→on dip).
        if _reassert_user_mode_while_running_best_effort(tray):
            tray.is_off = False
            _log_polled_hardware_event(
                tray,
                f"{log_action}_render_heal",
                brightness=int(current_brightness),
            )
            _refresh_ui_without_icon_animation(tray)
            return True

        set_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_brightness_hint",
            state_name="hidden_perkey_restore_brightness_hint",
            value=int(current_brightness),
        )
        set_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_device_off_hint",
            state_name="hidden_perkey_restore_device_off_hint",
            value=False,
        )
        handled = bool(apply_transition()) if callable(apply_transition) else False
        if not handled and callable(start_current_effect):
            # Seed restore damp right before the restart so the fresh
            # ``ReactiveRenderState`` inherits the damp window instead of
            # flashing at full pulse intensity on the first post-restart frame.
            _seed_reactive_restore_damp_best_effort(tray)
            handled = bool(start_current_effect())
    except _HARDWARE_POLL_RUNTIME_EXCEPTIONS as exc:
        _log_hardware_polling_error_best_effort(tray, exc)
        return False
    finally:
        clear_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_brightness_hint",
            state_name="hidden_perkey_restore_brightness_hint",
            value=None,
        )
        clear_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_device_off_hint",
            state_name="hidden_perkey_restore_device_off_hint",
            value=None,
        )

    if not handled:
        return False

    tray.is_off = False
    _log_polled_hardware_event(
        tray,
        log_action,
        brightness=int(current_brightness),
    )
    _refresh_ui_without_icon_animation(tray)
    return True


def _recover_recent_power_source_blank_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
) -> bool:
    now = time.monotonic()
    if not _power_source_blank_recovery_eligible(tray, now=now):
        return False
    return _execute_blank_recovery(
        tray,
        current_brightness=current_brightness,
        now=now,
        recovery_stamp_attr="_last_power_source_blank_recovery_at",
        recovery_stamp_state="last_power_source_blank_recovery_at",
        log_action="power_source_blank_recover",
    )


def _stable_zero_recovery_attempt_count(tray: IdlePowerTrayProtocol) -> int:
    """Read the consecutive stable-zero recovery attempt counter."""

    try:
        owner = ensure_tray_idle_power_state(tray)
        return int(getattr(owner, "stable_zero_recovery_attempt_count", 0))
    except (AttributeError, TypeError, ValueError):
        return 0


def _set_stable_zero_recovery_attempt_count(tray: IdlePowerTrayProtocol, value: int) -> None:
    """Write the consecutive stable-zero recovery attempt counter."""

    try:
        owner = ensure_tray_idle_power_state(tray)
        owner.stable_zero_recovery_attempt_count = max(0, int(value))
    except (AttributeError, TypeError, ValueError):
        return


def reset_stable_zero_recovery_attempt_count(tray: IdlePowerTrayProtocol) -> None:
    """Reset the consecutive-attempt counter.

    Called from the polling loop when a non-zero brightness read is observed,
    indicating the transient has cleared and future stable-zero recovery
    attempts should start from a clean slate.
    """

    _set_stable_zero_recovery_attempt_count(tray, 0)


def _recover_stable_zero_brightness_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
) -> bool:
    now = time.monotonic()
    last_recovery_at = read_idle_power_state_float_field(
        tray,
        attr_name="_last_hardware_blank_recovery_at",
        state_name="last_hardware_blank_recovery_at",
        default=0.0,
    )
    consecutive_attempts = _stable_zero_recovery_attempt_count(tray)
    if not should_attempt_stable_zero_brightness_recovery(
        current_brightness=int(current_brightness),
        dim_temp_active=is_dim_temp_active(tray),
        any_forced_off=any_forced_off(tray),
        configured_brightness_intent=_configured_brightness_intent(tray),
        now=now,
        last_recovery_at=float(last_recovery_at),
        consecutive_attempts=int(consecutive_attempts),
        cooldown_s=STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S,
        max_consecutive_attempts=STABLE_ZERO_BRIGHTNESS_MAX_CONSECUTIVE_ATTEMPTS,
        backoff_s=STABLE_ZERO_BRIGHTNESS_BACKOFF_S,
    ):
        return False
    # Increment the counter BEFORE executing the recovery so that even if the
    # recovery fails (exception / not handled) the circuit breaker still
    # counts the attempt and backs off on the next cycle.
    _set_stable_zero_recovery_attempt_count(tray, int(consecutive_attempts) + 1)
    return _execute_blank_recovery(
        tray,
        current_brightness=current_brightness,
        now=now,
        recovery_stamp_attr="_last_hardware_blank_recovery_at",
        recovery_stamp_state="last_hardware_blank_recovery_at",
        log_action="stable_zero_brightness_recover",
    )
