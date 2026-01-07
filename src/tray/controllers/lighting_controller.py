from __future__ import annotations

import logging
from typing import Any, Optional

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.tray.controllers._lighting_controller_helpers import (
    apply_perkey_mode,
    apply_uniform_none_mode,
    clear_engine_perkey_state,
    ensure_device_best_effort,
    get_effect_name,
    is_reactive_effect,
    is_software_effect,
    parse_menu_int,
    set_engine_perkey_from_config_for_sw_effect,
    try_log_event,
)
from src.core.utils.exceptions import is_device_disconnected

logger = logging.getLogger(__name__)


def start_current_effect(tray: Any) -> None:
    """Start the currently selected effect.

    This is best-effort and must never crash the tray.
    """

    try:
        ensure_device_best_effort(tray)

        effect = get_effect_name(tray)
        if effect == "perkey":
            apply_perkey_mode(tray)
            return

        if effect == "none":
            apply_uniform_none_mode(tray)
            return

        # Prepare per-key state in case the effect is a software effect that needs it.
        # This handles cases like 'reactive_ripple' running on startup where the menu logic hasn't run.
        if effect in SW_EFFECTS:
            set_engine_perkey_from_config_for_sw_effect(tray)
        else:
            clear_engine_perkey_state(tray)

        tray.engine.start_effect(
            effect,
            speed=tray.config.speed,
            brightness=tray.config.brightness,
            color=tray.config.color,
            reactive_color=getattr(tray.config, "reactive_color", None),
            reactive_use_manual_color=bool(getattr(tray.config, "reactive_use_manual_color", False)),
        )
        tray.is_off = False
    except Exception as exc:
        # If the USB device disappeared, mark it unavailable and avoid a scary traceback.
        if is_device_disconnected(exc):
            try:
                tray.engine.mark_device_unavailable()
            except Exception:
                pass
            logger.warning("Keyboard device unavailable: %s", exc)
            return
        try:
            tray._log_exception("Error starting effect: %s", exc)
        except Exception:
            logger.exception("Error starting effect")


def on_speed_clicked(tray: Any, item: Any) -> None:
    speed = parse_menu_int(item)
    if speed is None:
        return

    try_log_event(
        tray,
        "menu",
        "set_speed",
        old=int(getattr(tray.config, "speed", 0) or 0),
        new=int(speed),
    )

    tray.config.speed = speed
    if not tray.is_off:
        start_current_effect(tray)
    tray._update_menu()


def on_brightness_clicked(tray: Any, item: Any) -> None:
    brightness = parse_menu_int(item)
    if brightness is None:
        return

    brightness_hw = brightness * 5
    if brightness_hw > 0:
        tray._last_brightness = brightness_hw

    effect = get_effect_name(tray)
    is_sw_effect = is_software_effect(effect)
    is_reactive = is_reactive_effect(effect)

    # "Brightness Override" maps to different channels depending on mode:
    # - Reactive typing effects: override the base/backdrop brightness (per-key)
    # - Everything else: override the effect/hardware brightness
    if is_reactive:
        try:
            old_val = int(getattr(tray.config, "perkey_brightness", 0) or 0)
        except Exception:
            old_val = 0

        try_log_event(tray, "menu", "set_brightness", old=int(old_val), new=int(brightness_hw))

        try:
            tray.config.perkey_brightness = brightness_hw
        except Exception:
            pass
        try:
            tray.engine.per_key_brightness = brightness_hw
        except Exception:
            pass

        tray._update_menu()
        return

    try_log_event(
        tray,
        "menu",
        "set_brightness",
        old=int(getattr(tray.config, "brightness", 0) or 0),
        new=int(brightness_hw),
    )

    tray.config.brightness = brightness_hw
    # In software effect mode, avoid restarting the effect loop (which does a
    # brief uniform-color fade) and avoid issuing a separate hardware brightness
    # command (which can flash on some devices). The running loop reads
    # engine.brightness on each frame.
    tray.engine.set_brightness(tray.config.brightness, apply_to_hardware=not is_sw_effect)
    if not tray.is_off and not is_sw_effect:
        start_current_effect(tray)
    tray._update_menu()


def turn_off(tray: Any) -> None:
    try_log_event(tray, "menu", "turn_off")
    tray._user_forced_off = True
    tray._idle_forced_off = False
    tray.engine.turn_off()
    tray.is_off = True
    tray._refresh_ui()


def turn_on(tray: Any) -> None:
    try_log_event(tray, "menu", "turn_on")
    tray._user_forced_off = False
    tray._idle_forced_off = False
    tray.is_off = False

    if tray.config.brightness == 0:
        tray.config.brightness = tray._last_brightness if tray._last_brightness > 0 else 25

    if tray.config.effect == "none":
        with tray.engine.kb_lock:
            tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
    else:
        start_current_effect(tray)

    tray._refresh_ui()


def power_turn_off(tray: Any) -> None:
    try_log_event(tray, "power", "turn_off")
    tray._power_forced_off = True
    tray._idle_forced_off = False
    tray.is_off = True
    tray.engine.turn_off()
    tray._refresh_ui()


def power_restore(tray: Any) -> None:
    # Never fight explicit user off.
    if bool(getattr(tray, "_user_forced_off", False)):
        return

    # If lighting is intentionally forced off by idle policy, don't restore.
    if bool(getattr(tray, "_idle_forced_off", False)):
        return

    if bool(getattr(tray, "_power_forced_off", False)):
        try_log_event(tray, "power", "restore")
        tray._power_forced_off = False
        tray._idle_forced_off = False

        # If we forced off, ensure we have a usable brightness to restore.
        if int(getattr(tray.config, "brightness", 0) or 0) == 0:
            tray.config.brightness = tray._last_brightness if tray._last_brightness > 0 else 25

    # If the user explicitly configured brightness=0, treat that as off.
    if int(getattr(tray.config, "brightness", 0) or 0) == 0:
        tray.is_off = True
        return

    # Common restore path: hardware may have reset to off across suspend.
    tray.is_off = False
    start_current_effect(tray)
    tray._refresh_ui()


def apply_brightness_from_power_policy(tray: Any, brightness: int) -> None:
    """Best-effort brightness apply used by PowerManager battery-saver."""

    try:
        brightness_int = int(brightness)
    except Exception:
        return

    if brightness_int < 0:
        return

    # If the user explicitly turned the keyboard off, don't fight it.
    if bool(getattr(tray, "_user_forced_off", False)):
        return

    # If lighting is forced off due to power/idle policy, don't fight it.
    if bool(getattr(tray, "_power_forced_off", False)) or bool(getattr(tray, "_idle_forced_off", False)):
        return

    try:
        if brightness_int > 0:
            tray._last_brightness = brightness_int

        try_log_event(
            tray,
            "power_policy",
            "apply_brightness",
            old=int(getattr(tray.config, "brightness", 0) or 0),
            new=int(brightness_int),
        )

        effect = get_effect_name(tray)
        is_sw_effect = is_software_effect(effect)
        is_reactive = is_reactive_effect(effect)

        # Power-source policy defines the baseline. Persist into config so the
        # tray UI reflects the effective brightness after plug/unplug (and on
        # startup).
        if is_reactive:
            tray.config.perkey_brightness = brightness_int
            try:
                tray.engine.per_key_brightness = brightness_int
            except Exception:
                pass
            tray._refresh_ui()
            return

        tray.config.brightness = brightness_int
        tray.engine.set_brightness(tray.config.brightness, apply_to_hardware=not is_sw_effect)
        if not bool(getattr(tray, "is_off", False)) and not is_sw_effect:
            start_current_effect(tray)
        tray._refresh_ui()
    except Exception:
        return
