from __future__ import annotations

from collections.abc import Callable

from src.core.utils.safe_attrs import safe_int_attr
from src.tray.protocols import LightingTrayProtocol

from ._lighting_controller_helpers import (
    get_effect_name,
    is_reactive_effect,
    is_software_effect,
    try_log_event,
)


def apply_brightness_from_power_policy_impl(
    tray: LightingTrayProtocol,
    brightness: int,
    *,
    start_current_effect: Callable[[LightingTrayProtocol], None],
) -> None:
    try:
        brightness_int = int(brightness)
    except Exception:
        return

    if brightness_int < 0:
        return

    if bool(getattr(tray, "_user_forced_off", False)):
        return

    if bool(getattr(tray, "_power_forced_off", False)) or bool(getattr(tray, "_idle_forced_off", False)):
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
            try:
                with tray.engine.kb_lock:
                    try:
                        tray.engine.per_key_brightness = brightness_int
                    except Exception:
                        pass
                    tray.engine.set_brightness(
                        brightness_int,
                        apply_to_hardware=False,
                        fade=fade_down,
                        fade_duration_s=fade_s,
                    )
            except Exception:
                pass
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
    except Exception:
        return
