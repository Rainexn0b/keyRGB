from __future__ import annotations

import time
from collections.abc import Callable

from ._transition_constants import (
    SOFT_OFF_FADE_DURATION_S,
    SOFT_ON_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
)
from src.tray.protocols import LightingTrayProtocol


def turn_off_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    software_effect_target_routes_aux_devices: Callable[[LightingTrayProtocol], bool],
    turn_off_secondary_software_targets: Callable[[LightingTrayProtocol], None],
) -> None:
    try_log_event(tray, "menu", "turn_off")
    tray._user_forced_off = True
    tray._idle_forced_off = False
    tray.engine.turn_off()
    if software_effect_target_routes_aux_devices(tray):
        turn_off_secondary_software_targets(tray)
    tray.is_off = True
    tray._refresh_ui()


def turn_on_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    start_current_effect: Callable[..., None],
) -> None:
    try_log_event(tray, "menu", "turn_on")
    tray._user_forced_off = False
    tray._idle_forced_off = False
    tray.is_off = False

    if tray.config.brightness == 0:
        tray.config.brightness = tray._last_brightness if tray._last_brightness > 0 else 25

    start_current_effect(
        tray,
        brightness_override=SOFT_ON_START_BRIGHTNESS,
        fade_in=True,
        fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
    )

    tray._refresh_ui()


def power_turn_off_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    software_effect_target_routes_aux_devices: Callable[[LightingTrayProtocol], bool],
    turn_off_secondary_software_targets: Callable[[LightingTrayProtocol], None],
) -> None:
    try_log_event(tray, "power", "turn_off")
    tray._power_forced_off = True
    tray._idle_forced_off = False
    tray.is_off = True
    tray.engine.turn_off(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S)
    if software_effect_target_routes_aux_devices(tray):
        turn_off_secondary_software_targets(tray)
    tray._refresh_ui()


def power_restore_impl(
    tray: LightingTrayProtocol,
    *,
    try_log_event: Callable[..., None],
    safe_int_attr_fn: Callable[..., int],
    start_current_effect: Callable[..., None],
) -> None:
    tray._last_resume_at = time.monotonic()

    if bool(getattr(tray, "_user_forced_off", False)):
        return

    if bool(getattr(tray, "_idle_forced_off", False)):
        return

    if bool(getattr(tray, "_power_forced_off", False)):
        try_log_event(tray, "power", "restore")
        tray._power_forced_off = False
        tray._idle_forced_off = False

        if safe_int_attr_fn(tray.config, "brightness", default=0) == 0:
            tray.config.brightness = tray._last_brightness if tray._last_brightness > 0 else 25

    if safe_int_attr_fn(tray.config, "brightness", default=0) == 0:
        tray.is_off = True
        return

    tray.engine.current_color = (0, 0, 0)
    tray.is_off = False
    start_current_effect(
        tray,
        brightness_override=SOFT_ON_START_BRIGHTNESS,
        fade_in=True,
        fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
    )
    tray._refresh_ui()
