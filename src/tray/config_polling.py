from __future__ import annotations

import threading
import time
from pathlib import Path


def start_config_polling(tray, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Poll config file for external changes and apply them."""

    config_path = Path(tray.config.CONFIG_FILE)
    last_mtime = None
    last_applied = None

    def apply_from_config():
        nonlocal last_applied

        perkey_sig = None
        if tray.config.effect == 'perkey':
            try:
                perkey_sig = tuple(sorted(tray.config.per_key_colors.items()))
            except Exception:
                perkey_sig = None

        current = (
            tray.config.effect,
            tray.config.speed,
            tray.config.brightness,
            tuple(tray.config.color),
            perkey_sig,
        )

        if current == last_applied:
            return

        if tray.is_off:
            last_applied = current
            tray._update_menu()
            return

        if tray.config.brightness == 0:
            try:
                tray.engine.turn_off()
            except Exception:
                pass
            tray.is_off = True
            last_applied = current
            tray._update_icon()
            tray._update_menu()
            return

        if tray.config.brightness > 0:
            tray._last_brightness = tray.config.brightness

        try:
            if tray.config.effect == 'perkey':
                tray.engine.stop()
                color_map = dict(tray.config.per_key_colors)

                if 0 < len(color_map) < (ite_num_rows * ite_num_cols):
                    base = tuple(tray.config.color)
                    for r in range(ite_num_rows):
                        for c in range(ite_num_cols):
                            color_map.setdefault((r, c), base)

                with tray.engine.kb_lock:
                    tray.engine.kb.set_key_colors(color_map, brightness=tray.config.brightness, enable_user_mode=True)

            elif tray.config.effect == 'none':
                tray.engine.stop()
                with tray.engine.kb_lock:
                    tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)

            else:
                tray._start_current_effect()

        except Exception as e:
            tray._log_exception("Error applying config change: %s", e)

        last_applied = current
        tray._update_icon()
        tray._update_menu()

    def poll_config():
        nonlocal last_mtime

        try:
            last_mtime = config_path.stat().st_mtime
        except FileNotFoundError:
            last_mtime = None

        try:
            tray.config.reload()
            apply_from_config()
        except Exception:
            pass

        while True:
            try:
                mtime = config_path.stat().st_mtime
            except FileNotFoundError:
                mtime = None

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    tray.config.reload()
                    apply_from_config()
                except Exception as e:
                    tray._log_exception("Error reloading config: %s", e)

            time.sleep(0.1)

    threading.Thread(target=poll_config, daemon=True).start()
