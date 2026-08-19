"""Controller-native sleep transitions owned by hardware polling."""

from __future__ import annotations

from typing import cast

from keyrgb.core.backends.policies.sleep_state import is_controller_sleep_state
from keyrgb.tray.idle_power_state import set_idle_power_state_field
from keyrgb.tray.protocols import IdlePowerTrayProtocol, LightingTrayProtocol

from . import _recovery

_HARDWARE_POLL_RECOVERY_EXCEPTIONS = _recovery._HARDWARE_POLL_RECOVERY_EXCEPTIONS
_HARDWARE_POLL_RUNTIME_EXCEPTIONS = _recovery._HARDWARE_POLL_RUNTIME_EXCEPTIONS


def classify_polled_state(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
    current_off: bool,
) -> bool:
    """Classify a snapshot through the backend-declared sleep policy."""

    keyboard = getattr(getattr(tray, "engine", None), "kb", None)
    return is_controller_sleep_state(
        keyboard,
        brightness=int(current_brightness),
        is_off=bool(current_off),
    )


def stop_engine_for_controller_sleep_best_effort(tray: IdlePowerTrayProtocol) -> bool:
    """Stop a still-running effect when controller sleep is honored as off.

    This keeps render threads from writing after the tray has accepted native
    sleep. It also marks mode-off so the next start reasserts user mode; ITE
    firmware sleep reports brightness zero without reporting explicit off.
    """

    engine = tray.engine
    try:
        engine.stop()
        engine._device_mode_off = True
    except _HARDWARE_POLL_RECOVERY_EXCEPTIONS:
        return False
    return True


def clear_post_stop_write_best_effort(tray: IdlePowerTrayProtocol) -> None:
    """Keep honored sleep dark after a final in-flight render frame.

    Hardware polling releases ``kb_lock`` before stopping the effect. A frame
    already waiting for that lock can therefore land before the worker joins.
    Turn off only when a post-stop read proves that race occurred, preserving
    native zero-brightness sleep in the normal case.
    """

    try:
        with tray.engine.kb_lock:
            if int(tray.engine.kb.get_brightness()) > 0:
                tray.engine.kb.turn_off()
    except _HARDWARE_POLL_RUNTIME_EXCEPTIONS:
        return


def restart_effect_after_firmware_wake_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    now: float,
) -> bool:
    """Restart the effect stopped while honoring controller-native sleep.

    A first keypress can wake ITE firmware before the idle-power evdev loop
    claims the event. Since the deck is already physically on, restart at the
    configured brightness instead of issuing another off/soft-on transition.
    """

    set_idle_power_state_field(
        tray,
        attr_name="_last_resume_at",
        state_name="last_resume_at",
        value=float(now),
    )
    start_current_effect = _recovery._resolve_tray_callback(tray, "_start_current_effect")
    try:
        if callable(start_current_effect):
            # Older tray facades returned None after a successful start.
            return start_current_effect() is not False

        from keyrgb.tray.controllers.lighting_controller import start_current_effect as start_effect

        return bool(start_effect(cast(LightingTrayProtocol, tray)))
    except _HARDWARE_POLL_RUNTIME_EXCEPTIONS as exc:
        _recovery._log_hardware_polling_error_best_effort(tray, exc)
        return False
