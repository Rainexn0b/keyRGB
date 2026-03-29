from __future__ import annotations

import threading
import time
from typing import Final

from src.core.effects.catalog import resolve_effect_name_for_backend

_ANIMATED_ICON_EFFECTS: Final[frozenset[str]] = frozenset(
    {
        "rainbow",
        "rainbow_wave",
        "rainbow_swirl",
        "spectrum_cycle",
        "color_cycle",
        "random",
        "aurora",
        "fireworks",
        "wave",
        "marquee",
    }
)


def _has_animated_icon_state(*, effect: str, config: object | None) -> bool:
    if effect in _ANIMATED_ICON_EFFECTS:
        return True

    if effect == "reactive_ripple":
        return not bool(getattr(config, "reactive_use_manual_color", False))

    return False


def _normalize_color(value) -> tuple[int, int, int]:
    try:
        if value is None:
            return (0, 0, 0)
        if isinstance(value, tuple) and len(value) == 3:
            r, g, b = value
        else:
            seq = list(value)
            if len(seq) != 3:
                return (0, 0, 0)
            r, g, b = seq
        return (int(r), int(g), int(b))
    except Exception:
        return (0, 0, 0)


def _compute_icon_sig(tray) -> tuple[bool, str, int, int, tuple[int, int, int], bool]:
    config = getattr(tray, "config", None)
    raw_effect = (getattr(config, "effect", "") or "") if config is not None else ""
    effect = resolve_effect_name_for_backend(raw_effect, getattr(tray, "backend", None))
    speed = getattr(config, "speed", 0) if config is not None else 0
    brightness = getattr(config, "brightness", 0) if config is not None else 0
    color = getattr(config, "color", (0, 0, 0)) if config is not None else (0, 0, 0)

    try:
        speed_i = int(speed or 0)
    except Exception:
        speed_i = 0

    try:
        brightness_i = int(brightness or 0)
    except Exception:
        brightness_i = 0

    return (
        bool(getattr(tray, "is_off", False)),
        str(effect),
        speed_i,
        brightness_i,
        _normalize_color(color),
        _has_animated_icon_state(effect=str(effect), config=config),
    )


def _should_update_icon(sig, last_sig) -> bool:
    # NOTE: On some desktop environments, mutating `pystray.Icon.icon`
    # from a background thread can make the tray icon stop reacting
    # to clicks. Keep the periodic repaint limited to states where the
    # tray icon renderer is actually animated.
    dynamic = bool(sig) and bool(sig[5])
    return bool(dynamic) or (sig != last_sig)


def start_icon_color_polling(tray) -> None:
    """Update tray icon color periodically for dynamic effects."""

    def poll_icon_color():
        last_sig = None
        last_error_at = 0.0
        while True:
            try:
                sig = _compute_icon_sig(tray)
                if _should_update_icon(sig, last_sig):
                    try:
                        tray._update_icon(animate=False)
                    except TypeError:
                        tray._update_icon()
                    last_sig = sig
            except Exception as exc:
                now = time.monotonic()
                if now - last_error_at > 60:
                    last_error_at = now
                    try:
                        tray._log_exception("Icon color polling error: %s", exc)
                    except (OSError, RuntimeError, ValueError):
                        return

            time.sleep(0.8)

    threading.Thread(target=poll_icon_color, daemon=True).start()
