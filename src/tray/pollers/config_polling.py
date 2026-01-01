from __future__ import annotations

import threading
import time
from pathlib import Path


def start_config_polling(tray, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Poll config file for external changes and apply them."""

    config_path = Path(tray.config.CONFIG_FILE)
    last_mtime = None
    last_applied = None
    last_apply_warn_at = 0.0

    def apply_from_config():
        nonlocal last_applied
        nonlocal last_apply_warn_at

        perkey_sig = None
        if tray.config.effect == 'perkey':
            try:
                perkey_sig = tuple(sorted(tray.config.per_key_colors.items()))
            except Exception as exc:
                # Signature is best-effort; avoid breaking reload on odd types.
                now = time.monotonic()
                if now - last_apply_warn_at > 60:
                    last_apply_warn_at = now
                    try:
                        tray._log_exception("Error computing perkey signature: %s", exc)
                    except (OSError, RuntimeError, ValueError):
                        pass
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

        if tray.is_off and (
            bool(getattr(tray, "_user_forced_off", False))
            or bool(getattr(tray, "_power_forced_off", False))
            or bool(getattr(tray, "_idle_forced_off", False))
        ):
            last_applied = current
            tray._update_menu()
            return

        if tray.config.brightness == 0:
            try:
                tray.engine.turn_off()
            except Exception as exc:
                now = time.monotonic()
                if now - last_apply_warn_at > 60:
                    last_apply_warn_at = now
                    try:
                        tray._log_exception("Failed to turn off engine: %s", exc)
                    except (OSError, RuntimeError, ValueError):
                        pass
            tray.is_off = True
            last_applied = current
            tray._refresh_ui()
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
                        color_map,
                        brightness=tray.config.brightness,
                        enable_user_mode=True,
                    )

            elif tray.config.effect == 'none':
                tray.engine.stop()
                with tray.engine.kb_lock:
                    tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)

            else:
                tray._start_current_effect()

        except Exception as e:
            # Device disconnects can happen at any time. Mark unavailable to avoid
            # spamming errors until a reconnect succeeds.
            errno = getattr(e, "errno", None)
            if errno == 19 or "No such device" in str(e):
                try:
                    tray.engine.mark_device_unavailable()
                except Exception as exc:
                    now = time.monotonic()
                    if now - last_apply_warn_at > 60:
                        last_apply_warn_at = now
                        try:
                            tray._log_exception("Failed to mark device unavailable: %s", exc)
                        except (OSError, RuntimeError, ValueError):
                            pass
            tray._log_exception("Error applying config change: %s", e)

        last_applied = current
        tray._refresh_ui()

    def poll_config():
        nonlocal last_mtime

        last_startup_error_at = 0.0

        try:
            last_mtime = config_path.stat().st_mtime
        except FileNotFoundError:
            last_mtime = None

        try:
            tray.config.reload()
            apply_from_config()
        except Exception as exc:
            # Don't crash the polling thread; but also don't silently eat errors.
            now = time.monotonic()
            if now - last_startup_error_at > 30:
                last_startup_error_at = now
                try:
                    tray._log_exception("Error loading config on startup: %s", exc)
                except (OSError, RuntimeError, ValueError):
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
