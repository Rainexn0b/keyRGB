from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from src.core.brightness_layers import SchedulerBrightnessState
from src.core.brightness_layers import compose_power_source_brightness_overrides
from src.core.brightness_layers import is_scheduler_night
from src.core.brightness_layers import parse_scheduler_time
from src.core.brightness_layers import resolve_scheduler_brightness_state
from src.core.power.monitoring.power_supply_sysfs import read_on_ac_power
from src.tray.controllers._brightness_layer import apply_layered_brightness_update
from src.tray.controllers._lighting_controller_helpers import _log_tray_exception, try_log_event
from src.tray.controllers.lighting_controller import start_current_effect


if TYPE_CHECKING:
    from src.tray.protocols import LightingTrayProtocol


logger = logging.getLogger(__name__)

_BRIGHTNESS_COERCION_EXCEPTIONS = (TypeError, ValueError, OverflowError)
_SCHEDULER_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _active_power_source_base_brightness(
    state: SchedulerBrightnessState,
    *,
    on_ac: bool | None,
) -> int | None:
    if not state.defer_base_to_power_policy:
        return state.applied_base_brightness

    if on_ac is None:
        return state.applied_base_brightness

    ac_override, battery_override = compose_power_source_brightness_overrides(
        ac_brightness_override=state.ac_brightness_override,
        battery_brightness_override=state.battery_brightness_override,
        scheduler_base_brightness=state.active_base_brightness,
        scheduler_in_night=state.in_night,
    )
    return ac_override if bool(on_ac) else battery_override


def _apply_time_scheduler_brightness(
    tray: LightingTrayProtocol,
    base_brightness: int | None,
    reactive_brightness: int | None,
) -> None:
    try:
        base_brightness_int = None if base_brightness is None else int(base_brightness)
        reactive_brightness_int = None if reactive_brightness is None else int(reactive_brightness)
    except _BRIGHTNESS_COERCION_EXCEPTIONS:
        return

    if base_brightness_int is None and reactive_brightness_int is None:
        return

    if base_brightness_int is not None and base_brightness_int < 0:
        return
    if reactive_brightness_int is not None and reactive_brightness_int < 0:
        return

    if tray._user_forced_off:
        return

    if tray._power_forced_off or tray._idle_forced_off:
        return

    try:
        apply_layered_brightness_update(
            tray,
            source="time_scheduler",
            base_brightness=base_brightness_int,
            reactive_brightness=reactive_brightness_int,
            reactive_source_label="time-scheduler",
            start_current_effect=start_current_effect,
        )
    except _SCHEDULER_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: time-scheduler brightness application crosses config setters, backend runtime calls, and UI callbacks; must remain non-fatal
        _log_tray_exception(tray, "Failed to apply time-scheduler brightness: %s", exc)
        return


def _parse_time(time_str: str) -> tuple[int, int] | None:
    return parse_scheduler_time(time_str)


def _is_night(now: datetime, day_start: tuple[int, int], night_start: tuple[int, int]) -> bool:
    return is_scheduler_night(now, day_start, night_start)


def _run_scheduler_iteration(tray: LightingTrayProtocol) -> None:
    state = resolve_scheduler_brightness_state(
        tray.config,
        now=datetime.now(),
        power_management_enabled=bool(getattr(tray.config, "power_management_enabled", True)),
    )
    if not state.enabled:
        return
    if not state.times_valid:
        logger.warning(
            "Invalid time-scheduler times: day=%s night=%s",
            getattr(tray.config, "day_start_time", "08:00"),
            getattr(tray.config, "night_start_time", "20:00"),
        )
        return
    on_ac = read_on_ac_power()
    _apply_time_scheduler_brightness(
        tray,
        _active_power_source_base_brightness(state, on_ac=on_ac),
        state.active_reactive_brightness,
    )


def _scheduler_loop(
    tray: LightingTrayProtocol,
    *,
    sleep_fn: Callable[[float], None],
    now_fn: Callable[[], datetime],
) -> None:
    """Main scheduler polling loop.

    Checks every 60 seconds whether the time-scheduler should apply
    brightness overrides.
    """
    last_applied_key: str | None = None

    while True:
        try:
            state = resolve_scheduler_brightness_state(
                tray.config,
                now=now_fn(),
                power_management_enabled=bool(getattr(tray.config, "power_management_enabled", True)),
            )
            if state.enabled and state.times_valid:
                on_ac = read_on_ac_power()
                base_brightness = _active_power_source_base_brightness(state, on_ac=on_ac)
                apply_key = (
                    f"{state.in_night}:{base_brightness}:{state.active_reactive_brightness}:"
                    f"{state.defer_base_to_power_policy}:{on_ac}"
                )

                if apply_key != last_applied_key:
                    _apply_time_scheduler_brightness(
                        tray,
                        base_brightness,
                        state.active_reactive_brightness,
                    )
                    base_deferred = state.defer_base_to_power_policy and base_brightness is None
                    try_log_event(
                        tray,
                        "time_scheduler",
                        (
                            "night_reactive_applied_base_deferred_to_power_policy"
                            if state.in_night and base_deferred
                            else "night_applied"
                            if state.in_night
                            else "day_reactive_applied_base_deferred_to_power_policy"
                            if base_deferred
                            else "day_applied"
                        ),
                    )
                    last_applied_key = apply_key
        except _SCHEDULER_RUNTIME_EXCEPTIONS as exc:
            logger.error("Time-scheduler iteration error: %s", exc, exc_info=True)

        sleep_fn(60.0)


def start_time_scheduler_polling(tray: LightingTrayProtocol) -> None:
    """Start the time-of-day brightness scheduler in a daemon thread."""

    def run_scheduler() -> None:
        _scheduler_loop(tray, sleep_fn=time.sleep, now_fn=datetime.now)

    threading.Thread(target=run_scheduler, daemon=True).start()
