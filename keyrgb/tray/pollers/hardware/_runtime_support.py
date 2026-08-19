"""Small runtime probes shared by the hardware polling loop."""

from __future__ import annotations

from collections.abc import Callable

from keyrgb.core.effects.reactive.effects import _reactive_active_pulse_mix_or_default
from keyrgb.tray.protocols import IdlePowerTrayProtocol

_REACTIVE_PULSE_MIX_READ_ERRORS = (AttributeError, TypeError, ValueError)


def reactive_pulse_mix_or_zero(tray: IdlePowerTrayProtocol) -> float:
    """Read the advisory live reactive pulse mix without taking ``kb_lock``."""

    try:
        return float(_reactive_active_pulse_mix_or_default(tray.engine, default=0.0))
    except _REACTIVE_PULSE_MIX_READ_ERRORS:
        return 0.0


def poll_hardware_once(
    tray: IdlePowerTrayProtocol,
    *,
    last_brightness: object,
    last_off_state: object,
    apply_polled_state_fn: Callable[..., tuple[int, bool] | None],
) -> tuple[int, bool] | None:
    """Read one coherent hardware snapshot and pass it to the state reducer."""

    with tray.engine.kb_lock:
        current_brightness = tray.engine.kb.get_brightness()
        current_off = tray.engine.kb.is_off()

    return apply_polled_state_fn(
        tray,
        raw_brightness=int(current_brightness),
        current_brightness=int(current_brightness),
        current_off=bool(current_off),
        last_brightness=last_brightness,
        last_off_state=last_off_state,
    )
