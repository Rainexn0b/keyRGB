from __future__ import annotations

from typing import Any, Optional

from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET as SW_EFFECTS


REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)


def parse_menu_int(item: Any) -> Optional[int]:
    s = str(item).replace("🔘", "").replace("⚪", "").strip()
    try:
        return int(s)
    except Exception:
        return None


def try_log_event(tray: Any, source: str, action: str, **fields: Any) -> None:
    log_event = getattr(tray, "_log_event", None)
    if not callable(log_event):
        return
    try:
        log_event(source, action, **fields)
    except Exception:
        return


def get_effect_name(tray: Any) -> str:
    try:
        return str(getattr(tray.config, "effect", "none") or "none")
    except Exception:
        return "none"


def is_software_effect(effect: str) -> bool:
    return effect in SW_EFFECTS


def is_reactive_effect(effect: str) -> bool:
    return effect in REACTIVE_EFFECTS_SET


def ensure_device_best_effort(tray: Any) -> None:
    try:
        ensure = getattr(tray.engine, "_ensure_device_available", None)
        if callable(ensure):
            ensure()
    except Exception:
        return


def set_engine_perkey_from_config_for_sw_effect(tray: Any) -> None:
    try:
        tray.engine.per_key_colors = dict(getattr(tray.config, "per_key_colors", {}) or {})
    except Exception:
        tray.engine.per_key_colors = None

    try:
        tray.engine.per_key_brightness = int(getattr(tray.config, "perkey_brightness", 0) or 0)
    except Exception:
        tray.engine.per_key_brightness = None


def clear_engine_perkey_state(tray: Any) -> None:
    try:
        tray.engine.per_key_colors = None
    except Exception:
        pass
    try:
        tray.engine.per_key_brightness = None
    except Exception:
        pass


def apply_perkey_mode(tray: Any, *, brightness_override: Optional[int] = None) -> None:
    tray.engine.stop()
    effective_brightness = (
        int(brightness_override) if brightness_override is not None else int(getattr(tray.config, "brightness", 0) or 0)
    )
    if int(effective_brightness) == 0:
        tray.engine.turn_off()
        tray.is_off = True
        return

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
                tray.engine.kb.enable_user_mode(brightness=effective_brightness, save=True)
            except TypeError:
                try:
                    tray.engine.kb.enable_user_mode(brightness=effective_brightness)
                except Exception:
                    pass
            except Exception:
                pass
        tray.engine.kb.set_key_colors(
            tray.config.per_key_colors,
            brightness=effective_brightness,
            enable_user_mode=True,
        )

    tray.is_off = False


def apply_uniform_none_mode(tray: Any, *, brightness_override: Optional[int] = None) -> None:
    tray.engine.stop()
    effective_brightness = (
        int(brightness_override) if brightness_override is not None else int(getattr(tray.config, "brightness", 0) or 0)
    )
    if int(effective_brightness) == 0:
        tray.engine.turn_off()
        tray.is_off = True
        return

    clear_engine_perkey_state(tray)

    with tray.engine.kb_lock:
        tray.engine.kb.set_color(tray.config.color, brightness=effective_brightness)

    tray.is_off = False
