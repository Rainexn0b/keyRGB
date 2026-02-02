from __future__ import annotations

import threading
import time


_DYNAMIC_ICON_EFFECTS = {"rainbow", "aurora", "fireworks", "wave", "marquee"}


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


def _compute_icon_sig(tray) -> tuple[bool, str, int, int, tuple[int, int, int]]:
    config = getattr(tray, "config", None)
    effect = (getattr(config, "effect", "") or "") if config is not None else ""
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
    )


def _should_update_icon(sig, last_sig) -> bool:
    # NOTE: On some desktop environments, mutating `pystray.Icon.icon`
    # from a background thread can make the tray icon stop reacting
    # to clicks. Keep the periodic repaint limited to hardware
    # effects only.
    dynamic = bool(sig) and (sig[1] in _DYNAMIC_ICON_EFFECTS)
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
