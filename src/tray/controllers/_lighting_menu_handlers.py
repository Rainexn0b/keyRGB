from __future__ import annotations

from typing import Callable

from src.core.utils import safe_attrs
from src.tray.controllers import _lighting_controller_helpers as lighting_controller_helpers
from src.tray.protocols import LightingTrayProtocol


_LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def on_speed_clicked_impl(
    tray: LightingTrayProtocol,
    item: object,
    *,
    start_current_effect: Callable[[LightingTrayProtocol], None],
    log_boundary_exception: Callable[[LightingTrayProtocol, str, Exception], None],
) -> None:
    speed = lighting_controller_helpers.parse_menu_int(item)
    if speed is None:
        return

    lighting_controller_helpers.try_log_event(
        tray,
        "menu",
        "set_speed",
        old=safe_attrs.safe_int_attr(tray.config, "speed", default=0),
        new=int(speed),
    )

    # Save globally and as a per-effect override so each effect remembers its speed.
    tray.config.speed = speed
    effect = lighting_controller_helpers.get_effect_name(tray)
    if effect and effect not in {"none", "perkey"}:
        tray.config.set_effect_speed(effect, speed)

    if not tray.is_off:
        is_loop = lighting_controller_helpers.is_software_effect(
            effect
        ) or lighting_controller_helpers.is_reactive_effect(effect)
        if is_loop:
            # SW/reactive loops read engine.speed on every frame - update in-place
            # without restarting the loop (avoids flicker and state loss).
            try:
                tray.engine.speed = speed
            except _LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS as exc:
                log_boundary_exception(tray, "Failed to update engine speed in place: %s", exc)
                start_current_effect(tray)
        else:
            start_current_effect(tray)
    tray._update_menu()


def on_brightness_clicked_impl(
    tray: LightingTrayProtocol,
    item: object,
    *,
    start_current_effect: Callable[[LightingTrayProtocol], None],
) -> None:
    brightness = lighting_controller_helpers.parse_menu_int(item)
    if brightness is None:
        return

    brightness_hw = brightness * 5
    brightness_int = int(brightness_hw)
    if brightness_hw > 0:
        tray._last_brightness = brightness_hw

    effect = lighting_controller_helpers.get_effect_name(tray)
    is_sw_effect = lighting_controller_helpers.is_software_effect(effect)
    is_reactive = lighting_controller_helpers.is_reactive_effect(effect)

    # Any effect that runs a loop (software or reactive typing) reads
    # engine.brightness on each frame. For these, avoid restarting the loop
    # and avoid issuing an extra hardware brightness write (some firmware
    # flashes on separate brightness commands).
    is_loop_effect = bool(is_sw_effect or is_reactive)

    lighting_controller_helpers.try_log_event(
        tray,
        "menu",
        "set_brightness",
        old=safe_attrs.safe_int_attr(tray.config, "brightness", default=0),
        new=brightness_int,
    )

    tray.config.brightness = brightness_hw

    # For reactive typing effects, keep the tray brightness menu behaving like
    # an overall brightness control so the user sees an immediate change.
    # The dedicated reactive UI slider can still be used to set a different
    # pulse intensity.
    if is_reactive:
        try:
            tray.config.perkey_brightness = brightness_int
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass
        try:
            tray.config.reactive_brightness = brightness_int
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass
        try:
            tray.engine.per_key_brightness = brightness_int
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass
        try:
            tray.engine.reactive_brightness = brightness_int
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass

    tray.engine.set_brightness(tray.config.brightness, apply_to_hardware=not is_loop_effect)
    if not tray.is_off and not is_loop_effect:
        start_current_effect(tray)
    tray._update_menu()
