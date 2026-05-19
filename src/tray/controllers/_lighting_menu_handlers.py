from __future__ import annotations

from typing import Callable

from src.core.utils import safe_attrs
from src.tray.controllers._brightness_layer import apply_layered_brightness_update
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

    apply_layered_brightness_update(
        tray,
        source="menu",
        base_brightness=int(brightness * 5),
        reactive_brightness=None,
        reactive_source_label="tray brightness",
        start_current_effect=start_current_effect,
    )
