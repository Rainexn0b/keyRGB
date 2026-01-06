from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.utils.exceptions import is_device_disconnected


@dataclass(frozen=True)
class ConfigApplyState:
    effect: str
    speed: int
    brightness: int
    color: tuple[int, int, int]
    perkey_sig: tuple | None
    reactive_use_manual: bool
    reactive_color: tuple[int, int, int]


def _compute_config_apply_state(tray) -> ConfigApplyState:
    perkey_sig = None
    if getattr(tray.config, "effect", None) == "perkey":
        try:
            perkey_sig = tuple(sorted(tray.config.per_key_colors.items()))
        except Exception:
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

    try:
        color = tuple(getattr(tray.config, "color", (255, 255, 255)))
    except Exception:
        color = (255, 255, 255)

    return ConfigApplyState(
        effect=str(getattr(tray.config, "effect", "none") or "none"),
        speed=int(getattr(tray.config, "speed", 0) or 0),
        brightness=int(getattr(tray.config, "brightness", 0) or 0),
        color=tuple(color),
        perkey_sig=perkey_sig,
        reactive_use_manual=bool(reactive_use_manual),
        reactive_color=tuple(reactive_color),
    )


def _state_for_log(state: ConfigApplyState | None):
    if state is None:
        return None
    try:
        perkey_keys = 0 if state.perkey_sig is None else len(state.perkey_sig)
        return {
            "effect": state.effect,
            "speed": state.speed,
            "brightness": state.brightness,
            "color": tuple(state.color) if state.color is not None else None,
            "perkey_keys": perkey_keys,
        }
    except Exception:
        return None


def _maybe_apply_fast_path(
    tray,
    *,
    last_applied: ConfigApplyState | None,
    current: ConfigApplyState,
) -> tuple[bool, ConfigApplyState]:
    """Apply fast-path config updates.

    Returns (handled, new_last_applied).
    """

    if last_applied is None:
        return False, current

    # If only the reactive manual color/toggle changed, don't restart effects.
    try:
        only_reactive_changed = (
            last_applied.effect == current.effect
            and last_applied.speed == current.speed
            and last_applied.brightness == current.brightness
            and last_applied.color == current.color
            and last_applied.perkey_sig == current.perkey_sig
            and (
                last_applied.reactive_use_manual != current.reactive_use_manual
                or last_applied.reactive_color != current.reactive_color
            )
        )
    except Exception:
        only_reactive_changed = False

    if only_reactive_changed:
        try:
            tray.engine.reactive_use_manual_color = bool(current.reactive_use_manual)
            tray.engine.reactive_color = tuple(current.reactive_color)
        except Exception:
            pass
        try:
            tray._refresh_ui()
        except Exception:
            pass
        return True, current

    # If only brightness changed for a running software effect, update engine
    # state without restarting the effect loop.
    try:
        only_brightness_changed = (
            last_applied.effect == current.effect
            and last_applied.speed == current.speed
            and last_applied.color == current.color
            and last_applied.perkey_sig == current.perkey_sig
            and last_applied.reactive_use_manual == current.reactive_use_manual
            and last_applied.reactive_color == current.reactive_color
            and last_applied.brightness != current.brightness
        )
    except Exception:
        only_brightness_changed = False

    if only_brightness_changed and str(current.effect) in SW_EFFECTS and bool(getattr(tray.engine, "running", False)):
        try:
            tray.engine.set_brightness(int(current.brightness), apply_to_hardware=False)
        except Exception:
            pass
        try:
            tray._refresh_ui()
        except Exception:
            pass
        return True, current

    return False, current


def _apply_from_config_once(
    tray,
    *,
    ite_num_rows: int,
    ite_num_cols: int,
    cause: str,
    last_applied: ConfigApplyState | None,
    last_apply_warn_at: float,
) -> tuple[ConfigApplyState | None, float]:
    """Apply current tray config once.

    Intended for use by the polling loop and unit tests.
    Returns (new_last_applied, new_last_apply_warn_at).
    """

    # Signature is best-effort; avoid breaking reload on odd types.
    try:
        current = _compute_config_apply_state(tray)
    except Exception as exc:
        now = time.monotonic()
        if now - last_apply_warn_at > 60:
            last_apply_warn_at = now
            try:
                tray._log_exception("Error computing config signature: %s", exc)
            except (OSError, RuntimeError, ValueError):
                pass
        return last_applied, last_apply_warn_at

    if current == last_applied:
        return last_applied, last_apply_warn_at

    log_event = getattr(tray, "_log_event", None)
    if tray.is_off and (
        bool(getattr(tray, "_user_forced_off", False))
        or bool(getattr(tray, "_power_forced_off", False))
        or bool(getattr(tray, "_idle_forced_off", False))
    ):
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
        try:
            tray._update_menu()
        except Exception:
            pass
        return current, last_apply_warn_at

    handled, new_last_applied = _maybe_apply_fast_path(tray, last_applied=last_applied, current=current)
    if handled:
        return new_last_applied, last_apply_warn_at

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
        try:
            tray._refresh_ui()
        except Exception:
            pass
        return current, last_apply_warn_at

    if tray.config.brightness > 0:
        tray._last_brightness = tray.config.brightness

    # Always keep the engine's reactive color settings in sync so a running
    # reactive loop can pick up changes without requiring a restart.
    try:
        tray.engine.reactive_use_manual_color = bool(current.reactive_use_manual)
        tray.engine.reactive_color = tuple(current.reactive_color)
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
        if is_device_disconnected(e):
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

    try:
        tray._refresh_ui()
    except Exception:
        pass

    return current, last_apply_warn_at


def start_config_polling(tray, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Poll config file for external changes and apply them."""

    config_path = Path(tray.config.CONFIG_FILE)
    last_mtime = None
    last_applied: ConfigApplyState | None = None
    last_apply_warn_at = 0.0

    def apply_from_config(*, cause: str) -> None:
        nonlocal last_applied
        nonlocal last_apply_warn_at
        last_applied, last_apply_warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=ite_num_rows,
            ite_num_cols=ite_num_cols,
            cause=str(cause or "unknown"),
            last_applied=last_applied,
            last_apply_warn_at=last_apply_warn_at,
        )

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
