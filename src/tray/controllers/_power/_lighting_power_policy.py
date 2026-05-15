from __future__ import annotations

from collections.abc import Callable

from src.core.utils.safe_attrs import safe_int_attr
from src.tray.protocols import LightingTrayProtocol

from src.tray.controllers._lighting_controller_helpers import (
    _log_tray_exception,
    get_effect_name,
    is_reactive_effect,
    is_software_effect,
    sync_reactive_effect_brightness_state,
    try_log_event,
)


_BRIGHTNESS_COERCION_EXCEPTIONS = (TypeError, ValueError, OverflowError)
_POWER_POLICY_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def apply_brightness_from_power_policy_impl(
    tray: LightingTrayProtocol,
    brightness: int,
    *,
    start_current_effect: Callable[[LightingTrayProtocol], None],
) -> None:
    try:
        brightness_int = int(brightness)
    except _BRIGHTNESS_COERCION_EXCEPTIONS:
        return

    if brightness_int < 0:
        return

    if tray._user_forced_off:
        return

    if tray._power_forced_off or tray._idle_forced_off:
        return

    try:
        if brightness_int > 0:
            tray._last_brightness = brightness_int

        try_log_event(
            tray,
            "power_policy",
            "apply_brightness",
            old=safe_int_attr(tray.config, "brightness", default=0),
            new=int(brightness_int),
        )

        effect = get_effect_name(tray)
        is_sw_effect = is_software_effect(effect)
        is_reactive = is_reactive_effect(effect)

        prev_cfg_brightness = safe_int_attr(tray.config, "brightness", default=0)
        fade_down = bool(brightness_int < prev_cfg_brightness)
        fade_s = 0.12 if int(brightness_int) <= 0 else 0.25

        if is_reactive:
            tray.config.perkey_brightness = brightness_int
            tray.config.brightness = brightness_int
            sync_reactive_effect_brightness_state(
                tray,
                source="power policy",
                base_brightness=brightness_int,
                fade=fade_down,
                fade_duration_s=fade_s,
            )
            tray._refresh_ui()
            return

        tray.config.brightness = brightness_int
        tray.engine.set_brightness(
            tray.config.brightness,
            apply_to_hardware=not is_sw_effect,
            fade=fade_down,
            fade_duration_s=fade_s,
        )
        if not bool(getattr(tray, "is_off", False)) and not is_sw_effect:
            start_current_effect(tray)
        tray._refresh_ui()
    except _POWER_POLICY_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: power-policy application crosses config setters, backend runtime calls, and UI callbacks; must remain non-fatal
        _log_tray_exception(tray, "Failed to apply tray lighting power-policy brightness: %s", exc)
        return
