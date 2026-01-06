from __future__ import annotations

import logging
from typing import Any, Optional

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.utils.exceptions import is_device_disconnected

logger = logging.getLogger(__name__)


def _parse_menu_int(item: Any) -> Optional[int]:
    """Parse an integer from a pystray radio label.

    Historically, menu labels included leading marker glyphs. We accept both
    plain integers ("5") and older formats.
    """

    s = str(item).replace("🔘", "").replace("⚪", "").strip()
    try:
        return int(s)
    except Exception:
        return None


def start_current_effect(tray: Any) -> None:
    """Start the currently selected effect.

    This is best-effort and must never crash the tray.
    """

    try:
        # Best-effort: if the device was unplugged/replugged, try to reacquire.
        try:
            ensure = getattr(tray.engine, "_ensure_device_available", None)
            if callable(ensure):
                ensure()
        except Exception:
            pass

        if tray.config.effect == "perkey":
            tray.engine.stop()
            if tray.config.brightness == 0:
                tray.engine.turn_off()
                tray.is_off = True
                return

            # Record per-key mode so software effects can respect it later.
            try:
                tray.engine.per_key_colors = dict(getattr(tray.config, "per_key_colors", {}) or {})
            except Exception:
                tray.engine.per_key_colors = None
            try:
                tray.engine.per_key_brightness = int(getattr(tray.config, "perkey_brightness", tray.config.brightness) or 0)
            except Exception:
                tray.engine.per_key_brightness = None

            with tray.engine.kb_lock:
                if hasattr(tray.engine.kb, "enable_user_mode"):
                    try:
                        tray.engine.kb.enable_user_mode(brightness=tray.config.brightness, save=True)
                    except TypeError:
                        try:
                            tray.engine.kb.enable_user_mode(brightness=tray.config.brightness)
                        except Exception:
                            pass
                    except Exception:
                        pass
                tray.engine.kb.set_key_colors(
                    tray.config.per_key_colors,
                    brightness=tray.config.brightness,
                    enable_user_mode=True,
                )
            tray.is_off = False
            return

        if tray.config.effect == "none":
            tray.engine.stop()
            if tray.config.brightness == 0:
                tray.engine.turn_off()
                tray.is_off = True
                return

            # Record uniform mode so software effects don't accidentally reuse per-key.
            try:
                tray.engine.per_key_colors = None
            except Exception:
                pass
            try:
                tray.engine.per_key_brightness = None
            except Exception:
                pass

            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
            tray.is_off = False
            return

        tray.engine.start_effect(
            tray.config.effect,
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
    speed = _parse_menu_int(item)
    if speed is None:
        return

    log_event = getattr(tray, "_log_event", None)
    if callable(log_event):
        try:
            log_event("menu", "set_speed", old=int(getattr(tray.config, "speed", 0) or 0), new=int(speed))
        except Exception:
            pass

    tray.config.speed = speed
    if not tray.is_off:
        start_current_effect(tray)
    tray._update_menu()


def on_brightness_clicked(tray: Any, item: Any) -> None:
    brightness = _parse_menu_int(item)
    if brightness is None:
        return

    brightness_hw = brightness * 5
    if brightness_hw > 0:
        tray._last_brightness = brightness_hw

    log_event = getattr(tray, "_log_event", None)
    if callable(log_event):
        try:
            log_event(
                "menu",
                "set_brightness",
                old=int(getattr(tray.config, "brightness", 0) or 0),
                new=int(brightness_hw),
            )
        except Exception:
            pass

    tray.config.brightness = brightness_hw
    # In software effect mode, avoid restarting the effect loop (which does a
    # brief uniform-color fade) and avoid issuing a separate hardware brightness
    # command (which can flash on some devices). The running loop reads
    # engine.brightness on each frame.
    try:
        is_sw_effect = str(getattr(tray.config, "effect", "none") or "none") in SW_EFFECTS
    except Exception:
        is_sw_effect = False

    tray.engine.set_brightness(tray.config.brightness, apply_to_hardware=not is_sw_effect)
    if not tray.is_off and not is_sw_effect:
        start_current_effect(tray)
    tray._update_menu()


def turn_off(tray: Any) -> None:
    log_event = getattr(tray, "_log_event", None)
    if callable(log_event):
        try:
            log_event("menu", "turn_off")
        except Exception:
            pass
    tray._user_forced_off = True
    tray._idle_forced_off = False
    tray.engine.turn_off()
    tray.is_off = True
    tray._refresh_ui()


def turn_on(tray: Any) -> None:
    log_event = getattr(tray, "_log_event", None)
    if callable(log_event):
        try:
            log_event("menu", "turn_on")
        except Exception:
            pass
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
    log_event = getattr(tray, "_log_event", None)
    if callable(log_event):
        try:
            log_event("power", "turn_off")
        except Exception:
            pass
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
        log_event = getattr(tray, "_log_event", None)
        if callable(log_event):
            try:
                log_event("power", "restore")
            except Exception:
                pass
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

        log_event = getattr(tray, "_log_event", None)
        if callable(log_event):
            try:
                log_event(
                    "power_policy",
                    "apply_brightness",
                    old=int(getattr(tray.config, "brightness", 0) or 0),
                    new=int(brightness_int),
                )
            except Exception:
                pass

        # Power-source policy defines the baseline. Persist into config so the
        # tray UI reflects the effective brightness after plug/unplug (and on
        # startup).
        tray.config.brightness = brightness_int

        try:
            is_sw_effect = str(getattr(tray.config, "effect", "none") or "none") in SW_EFFECTS
        except Exception:
            is_sw_effect = False

        tray.engine.set_brightness(tray.config.brightness, apply_to_hardware=not is_sw_effect)
        if not bool(getattr(tray, "is_off", False)) and not is_sw_effect:
            start_current_effect(tray)
        tray._refresh_ui()
    except Exception:
        return
