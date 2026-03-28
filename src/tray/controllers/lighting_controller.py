from __future__ import annotations

import logging
from typing import Optional

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.utils.safe_attrs import safe_int_attr
from src.tray.controllers._transition_constants import (
    SOFT_OFF_FADE_DURATION_S,
    SOFT_ON_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
)
from src.tray.controllers._lighting_power_policy import apply_brightness_from_power_policy_impl
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
from src.tray.protocols import LightingTrayProtocol
from src.core.utils.exceptions import is_device_disconnected
from src.core.utils.exceptions import is_permission_denied

logger = logging.getLogger(__name__)


def start_current_effect(
    tray: LightingTrayProtocol,
    *,
    brightness_override: Optional[int] = None,
    fade_in: bool = False,
    fade_in_duration_s: float = 0.25,
) -> None:
    """Start the currently selected effect.

    This is best-effort and must never crash the tray.
    """

    try:
        ensure_device_best_effort(tray)

        target_brightness = safe_int_attr(tray.config, "brightness", default=0)
        start_brightness = target_brightness
        if brightness_override is not None:
            try:
                start_brightness = max(0, min(50, int(brightness_override)))
            except Exception:
                start_brightness = target_brightness

        effect = get_effect_name(tray)
        if effect == "perkey":
            apply_perkey_mode(tray, brightness_override=start_brightness)
            if fade_in and target_brightness > start_brightness and target_brightness > 0:
                tray.engine.set_brightness(
                    target_brightness,
                    apply_to_hardware=True,
                    fade=True,
                    fade_duration_s=float(fade_in_duration_s),
                )
            return

        if effect == "none":
            apply_uniform_none_mode(tray, brightness_override=start_brightness)
            if fade_in and target_brightness > start_brightness and target_brightness > 0:
                tray.engine.set_brightness(
                    target_brightness,
                    apply_to_hardware=True,
                    fade=True,
                    fade_duration_s=float(fade_in_duration_s),
                )
            return

        # Prepare per-key state in case the effect is a software effect that needs it.
        # This handles cases like 'reactive_ripple' running on startup where the menu logic hasn't run.
        if effect in SW_EFFECTS:
            set_engine_perkey_from_config_for_sw_effect(tray)
        else:
            clear_engine_perkey_state(tray)

        # When a fade-in is planned, decide the ramp strategy based on
        # whether the effect runs its own render loop.
        _will_fade = fade_in and target_brightness > start_brightness and target_brightness > 0
        is_loop_effect = is_software_effect(effect) or is_reactive_effect(effect)

        # Hardware-only effects (perkey, none) need a blocking fade and
        # auxiliary brightness caps so _resolve_brightness stays aligned.
        # Loop effects (reactive, SW) use the render loop's per-frame
        # stability guard for smooth ramping — capping reactive_brightness
        # would make pulses invisible during the ramp window.
        _saved_reactive_br = None
        _saved_perkey_br = None
        if _will_fade and not is_loop_effect:
            try:
                _saved_reactive_br = getattr(tray.engine, "reactive_brightness", None)
                tray.engine.reactive_brightness = start_brightness
            except Exception:
                pass
            try:
                _saved_perkey_br = getattr(tray.engine, "per_key_brightness", None)
                if _saved_perkey_br is not None:
                    tray.engine.per_key_brightness = start_brightness
            except Exception:
                pass

        tray.engine.start_effect(
            effect,
            speed=tray.config.speed,
            brightness=start_brightness,
            color=tray.config.color,
            reactive_color=getattr(tray.config, "reactive_color", None),
            reactive_use_manual_color=bool(getattr(tray.config, "reactive_use_manual_color", False)),
        )
        tray.is_off = False

        if _will_fade:
            if is_loop_effect:
                # The render loop's stability guard ramps brightness
                # frame-by-frame (~8 units/frame).  Just set the target
                # atomically — no blocking fade, no aux caps needed.
                tray.engine.set_brightness(
                    target_brightness,
                    apply_to_hardware=False,
                )
            else:
                tray.engine.set_brightness(
                    target_brightness,
                    apply_to_hardware=True,
                    fade=True,
                    fade_duration_s=float(fade_in_duration_s),
                )
            # Restore auxiliary brightness for hardware effects.
            if _saved_reactive_br is not None:
                try:
                    tray.engine.reactive_brightness = int(_saved_reactive_br)
                except Exception:
                    pass
            if _saved_perkey_br is not None:
                try:
                    tray.engine.per_key_brightness = int(_saved_perkey_br)
                except Exception:
                    pass
    except Exception as exc:
        # If the USB device disappeared, mark it unavailable and avoid a scary traceback.
        if is_device_disconnected(exc):
            try:
                tray.engine.mark_device_unavailable()
            except Exception:
                pass
            logger.warning("Keyboard device unavailable: %s", exc)
            return

        # Missing permissions should be surfaced as a user-visible notification.
        notify_permission_issue = getattr(tray, "_notify_permission_issue", None)
        if is_permission_denied(exc) and callable(notify_permission_issue):
            try:
                notify_permission_issue(exc)
            except Exception:
                pass
            return
        try:
            tray._log_exception("Error starting effect: %s", exc)
        except Exception:
            logger.exception("Error starting effect")


def on_speed_clicked(tray: LightingTrayProtocol, item: object) -> None:
    speed = parse_menu_int(item)
    if speed is None:
        return

    try_log_event(
        tray,
        "menu",
        "set_speed",
        old=safe_int_attr(tray.config, "speed", default=0),
        new=int(speed),
    )

    tray.config.speed = speed
    if not tray.is_off:
        start_current_effect(tray)
    tray._update_menu()


def on_brightness_clicked(tray: LightingTrayProtocol, item: object) -> None:
    brightness = parse_menu_int(item)
    if brightness is None:
        return

    brightness_hw = brightness * 5
    if brightness_hw > 0:
        tray._last_brightness = brightness_hw

    effect = get_effect_name(tray)
    is_sw_effect = is_software_effect(effect)
    is_reactive = is_reactive_effect(effect)

    # Any effect that runs a loop (software or reactive typing) reads
    # `engine.brightness` on each frame. For these, avoid restarting the loop
    # and avoid issuing an extra hardware brightness write (some firmware
    # flashes on separate brightness commands).
    is_loop_effect = bool(is_sw_effect or is_reactive)

    try_log_event(
        tray,
        "menu",
        "set_brightness",
        old=safe_int_attr(tray.config, "brightness", default=0),
        new=int(brightness_hw),
    )

    tray.config.brightness = brightness_hw

    # For reactive typing effects, keep the tray brightness menu behaving like
    # an "overall brightness" control so the user sees an immediate change.
    # The dedicated reactive UI slider can still be used to set a different
    # pulse intensity.
    if is_reactive:
        try:
            tray.config.reactive_brightness = int(brightness_hw)
        except Exception:
            pass
        try:
            tray.engine.reactive_brightness = int(brightness_hw)
        except Exception:
            pass

    tray.engine.set_brightness(tray.config.brightness, apply_to_hardware=not is_loop_effect)
    if not tray.is_off and not is_loop_effect:
        start_current_effect(tray)
    tray._update_menu()


def turn_off(tray: LightingTrayProtocol) -> None:
    try_log_event(tray, "menu", "turn_off")
    tray._user_forced_off = True
    tray._idle_forced_off = False
    tray.engine.turn_off()
    tray.is_off = True
    tray._refresh_ui()


def turn_on(tray: LightingTrayProtocol) -> None:
    try_log_event(tray, "menu", "turn_on")
    tray._user_forced_off = False
    tray._idle_forced_off = False
    tray.is_off = False

    if tray.config.brightness == 0:
        tray.config.brightness = tray._last_brightness if tray._last_brightness > 0 else 25

    # Fade-in from a minimal brightness to reduce abrupt on/off transitions.
    start_current_effect(
        tray,
        brightness_override=SOFT_ON_START_BRIGHTNESS,
        fade_in=True,
        fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
    )

    tray._refresh_ui()


def power_turn_off(tray: LightingTrayProtocol) -> None:
    try_log_event(tray, "power", "turn_off")
    tray._power_forced_off = True
    tray._idle_forced_off = False
    tray.is_off = True
    tray.engine.turn_off(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S)
    tray._refresh_ui()


def power_restore(tray: LightingTrayProtocol) -> None:
    # Track resume time so idle polling can ignore stale screen-off state.
    try:
        import time

        tray._last_resume_at = time.monotonic()
    except Exception:
        pass

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
        if safe_int_attr(tray.config, "brightness", default=0) == 0:
            tray.config.brightness = tray._last_brightness if tray._last_brightness > 0 else 25

    # If the user explicitly configured brightness=0, treat that as off.
    if safe_int_attr(tray.config, "brightness", default=0) == 0:
        tray.is_off = True
        return

    # Common restore path: hardware may have reset to off across suspend.
    # Avoid a visible flash from fading from a stale prior color.
    try:
        tray.engine.current_color = (0, 0, 0)
    except Exception:
        pass
    tray.is_off = False
    start_current_effect(
        tray,
        brightness_override=SOFT_ON_START_BRIGHTNESS,
        fade_in=True,
        fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
    )
    tray._refresh_ui()


def apply_brightness_from_power_policy(tray: LightingTrayProtocol, brightness: int) -> None:
    """Best-effort brightness apply used by PowerManager battery-saver."""

    apply_brightness_from_power_policy_impl(
        tray,
        brightness,
        start_current_effect=start_current_effect,
    )
