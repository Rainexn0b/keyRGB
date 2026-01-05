from __future__ import annotations

import threading
import time
from pathlib import Path

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS


def start_config_polling(tray, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Poll config file for external changes and apply them."""

    config_path = Path(tray.config.CONFIG_FILE)
    last_mtime = None
    last_applied = None
    last_apply_warn_at = 0.0

    def _state_for_log(state_tuple):
        if not state_tuple:
            return None
        try:
            eff, spd, bri, col, perkey_sig = state_tuple
            perkey_keys = 0 if perkey_sig is None else len(perkey_sig)
            return {
                "effect": eff,
                "speed": spd,
                "brightness": bri,
                "color": tuple(col) if col is not None else None,
                "perkey_keys": perkey_keys,
            }
        except Exception:
            return None

    def apply_from_config(*, cause: str) -> None:
        nonlocal last_applied
        nonlocal last_apply_warn_at

        perkey_sig = None
        if tray.config.effect == "perkey":
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

        # Reactive typing manual color (may be unused unless enabled).
        try:
            reactive_use_manual = bool(getattr(tray.config, "reactive_use_manual_color", False))
        except Exception:
            reactive_use_manual = False
        try:
            reactive_color = tuple(getattr(tray.config, "reactive_color", (255, 255, 255)))
        except Exception:
            reactive_color = (255, 255, 255)

        current = (
            tray.config.effect,
            tray.config.speed,
            tray.config.brightness,
            tuple(tray.config.color),
            perkey_sig,
            reactive_use_manual,
            reactive_color,
        )

        if current == last_applied:
            return

        # If only the reactive manual color/toggle changed, don't restart effects.
        if last_applied is not None:
            try:
                old_eff, old_spd, old_bri, old_col, old_perkey_sig, old_use_manual, old_rcol = last_applied
                new_eff, new_spd, new_bri, new_col, new_perkey_sig, new_use_manual, new_rcol = current
                only_reactive_changed = (
                    old_eff == new_eff
                    and old_spd == new_spd
                    and old_bri == new_bri
                    and old_col == new_col
                    and old_perkey_sig == new_perkey_sig
                    and (old_use_manual != new_use_manual or old_rcol != new_rcol)
                )
            except Exception:
                only_reactive_changed = False

            if only_reactive_changed:
                try:
                    tray.engine.reactive_use_manual_color = bool(new_use_manual)
                    tray.engine.reactive_color = tuple(new_rcol)
                except Exception:
                    pass
                last_applied = current
                tray._refresh_ui()
                return

        # If only brightness changed for a running software effect, update engine
        # state without restarting the effect loop (prevents a brief uniform-color
        # flash during the engine's restart fade).
        if last_applied is not None:
            try:
                old_eff, old_spd, old_bri, old_col, old_perkey_sig, old_use_manual, old_rcol = last_applied
                new_eff, new_spd, new_bri, new_col, new_perkey_sig, new_use_manual, new_rcol = current
                only_brightness_changed = (
                    old_eff == new_eff
                    and old_spd == new_spd
                    and old_col == new_col
                    and old_perkey_sig == new_perkey_sig
                    and old_use_manual == new_use_manual
                    and old_rcol == new_rcol
                    and old_bri != new_bri
                )
            except Exception:
                only_brightness_changed = False

            if only_brightness_changed and str(new_eff) in SW_EFFECTS and bool(getattr(tray.engine, "running", False)):
                try:
                    tray.engine.set_brightness(int(new_bri), apply_to_hardware=False)
                except Exception:
                    pass
                last_applied = current
                tray._refresh_ui()
                return

        log_event = getattr(tray, "_log_event", None)
        if callable(log_event):
            try:
                old_state = _state_for_log(last_applied)
                new_state = _state_for_log(current)
                log_event(
                    "config",
                    "detected_change",
                    cause=str(cause or "unknown"),
                    old=old_state,
                    new=new_state,
                )
            except Exception:
                pass

        if tray.is_off and (
            bool(getattr(tray, "_user_forced_off", False))
            or bool(getattr(tray, "_power_forced_off", False))
            or bool(getattr(tray, "_idle_forced_off", False))
        ):
            if callable(log_event):
                try:
                    log_event(
                        "config",
                        "skipped_forced_off",
                        cause=str(cause or "unknown"),
                        is_off=True,
                        user_forced_off=bool(getattr(tray, "_user_forced_off", False)),
                        power_forced_off=bool(getattr(tray, "_power_forced_off", False)),
                        idle_forced_off=bool(getattr(tray, "_idle_forced_off", False)),
                    )
                except Exception:
                    pass
            last_applied = current
            tray._update_menu()
            return

        if tray.config.brightness == 0:
            if callable(log_event):
                try:
                    log_event("config", "apply_turn_off", cause=str(cause or "unknown"), brightness=0)
                except Exception:
                    pass
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

        # Always keep the engine's reactive color settings in sync so a running
        # reactive loop can pick up changes without requiring a restart.
        try:
            tray.engine.reactive_use_manual_color = bool(reactive_use_manual)
            tray.engine.reactive_color = tuple(reactive_color)
        except Exception:
            pass

        try:
            if tray.config.effect == "perkey":
                if callable(log_event):
                    try:
                        log_event(
                            "config",
                            "apply_perkey",
                            cause=str(cause or "unknown"),
                            brightness=int(tray.config.brightness),
                            perkey_keys=int(len(getattr(tray.config, "per_key_colors", {}) or {})),
                        )
                    except Exception:
                        pass
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

            elif tray.config.effect == "none":
                if callable(log_event):
                    try:
                        log_event(
                            "config",
                            "apply_uniform",
                            cause=str(cause or "unknown"),
                            brightness=int(tray.config.brightness),
                            color=tuple(tray.config.color),
                        )
                    except Exception:
                        pass
                tray.engine.stop()
                with tray.engine.kb_lock:
                    tray.engine.kb.set_color(tray.config.color, brightness=tray.config.brightness)

            else:
                if callable(log_event):
                    try:
                        log_event(
                            "config",
                            "apply_effect",
                            cause=str(cause or "unknown"),
                            effect=str(tray.config.effect),
                            speed=int(tray.config.speed),
                            brightness=int(tray.config.brightness),
                            color=tuple(tray.config.color),
                        )
                    except Exception:
                        pass
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
            apply_from_config(cause="startup")
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
                    apply_from_config(cause="mtime_change")
                except Exception as e:
                    tray._log_exception("Error reloading config: %s", e)

            time.sleep(0.1)

    threading.Thread(target=poll_config, daemon=True).start()
