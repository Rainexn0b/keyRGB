from __future__ import annotations

import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


def _parse_menu_int(item: Any) -> Optional[int]:
    """Parse an integer from a pystray radio label.

    Current menu labels include leading marker glyphs like "🔘" / "⚪".
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
        if tray.config.effect == "perkey":
            tray.engine.stop()
            if tray.config.brightness == 0:
                tray.engine.turn_off()
                tray.is_off = True
                return

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

            with tray.engine.kb_lock:
                tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)
            tray.is_off = False
            return

        tray.engine.start_effect(
            tray.config.effect,
            speed=tray.config.speed,
            brightness=tray.config.brightness,
            color=tray.config.color,
        )
        tray.is_off = False
    except Exception as exc:
        try:
            tray._log_exception("Error starting effect: %s", exc)
        except Exception:
            logger.exception("Error starting effect")


def on_speed_clicked(tray: Any, item: Any) -> None:
    speed = _parse_menu_int(item)
    if speed is None:
        return

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

    tray.config.brightness = brightness_hw
    tray.engine.set_brightness(tray.config.brightness)
    if not tray.is_off:
        start_current_effect(tray)
    tray._update_menu()


def turn_off(tray: Any) -> None:
    tray.engine.turn_off()
    tray.is_off = True
    tray._refresh_ui()


def turn_on(tray: Any) -> None:
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
    tray._power_forced_off = True
    tray.is_off = True
    tray.engine.turn_off()
    tray._refresh_ui()


def power_restore(tray: Any) -> None:
    if tray._power_forced_off:
        tray._power_forced_off = False
        tray.is_off = False

        if tray.config.brightness == 0:
            tray.config.brightness = tray._last_brightness if tray._last_brightness > 0 else 25

        start_current_effect(tray)
        tray._refresh_ui()
        return

    if not tray.is_off:
        start_current_effect(tray)


def apply_brightness_from_power_policy(tray: Any, brightness: int) -> None:
    """Best-effort brightness apply used by PowerManager battery-saver."""

    try:
        brightness_int = int(brightness)
    except Exception:
        return

    if brightness_int < 0:
        return

    # If the user explicitly turned the keyboard off, don't fight it.
    if tray.is_off:
        return

    try:
        if brightness_int > 0:
            tray._last_brightness = brightness_int
        tray.config.brightness = brightness_int
        tray.engine.set_brightness(tray.config.brightness)
        start_current_effect(tray)
        tray._refresh_ui()
    except Exception:
        return
