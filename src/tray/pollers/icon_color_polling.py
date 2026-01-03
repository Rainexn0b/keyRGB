from __future__ import annotations

import threading
import time


def start_icon_color_polling(tray) -> None:
    """Update tray icon color periodically for dynamic effects."""

    def poll_icon_color():
        last_sig = None
        last_error_at = 0.0
        while True:
            try:
                sig = (
                    bool(tray.is_off),
                    str(getattr(tray.config, "effect", "")),
                    int(getattr(tray.config, "speed", 0) or 0),
                    int(getattr(tray.config, "brightness", 0) or 0),
                    tuple(getattr(tray.config, "color", (0, 0, 0)) or (0, 0, 0)),
                )

                # NOTE: On some desktop environments, mutating `pystray.Icon.icon`
                # from a background thread can make the tray icon stop reacting
                # to clicks. Keep the periodic repaint limited to hardware
                # effects only.
                dynamic = sig[1] in {"rainbow", "aurora", "fireworks", "wave", "marquee"}

                if dynamic or sig != last_sig:
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
