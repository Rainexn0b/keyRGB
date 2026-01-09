from __future__ import annotations

from typing import Any


def _log_detected_change(tray: Any, last_applied, current, cause: str, state_for_log_fn):
    log_event = getattr(tray, "_log_event", None)
    if not callable(log_event):
        return
    try:
        old_state = state_for_log_fn(last_applied)
        new_state = state_for_log_fn(current)
        log_event(
            "config",
            "detected_change",
            cause=str(cause or "unknown"),
            old=old_state,
            new=new_state,
        )
    except Exception:
        pass


def _handle_forced_off(tray: Any, last_applied, current, cause: str, state_for_log_fn):
    """Handle the case where the tray is currently 'off' and remains off.

    Returns True when the change is handled (no further action required).
    """
    if not tray.is_off:
        return False

    if not (
        bool(getattr(tray, "_user_forced_off", False))
        or bool(getattr(tray, "_power_forced_off", False))
        or bool(getattr(tray, "_idle_forced_off", False))
    ):
        return False

    log_event = getattr(tray, "_log_event", None)
    if callable(log_event):
        try:
            old_state = state_for_log_fn(last_applied)
            new_state = state_for_log_fn(current)
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
    return True


def _apply_turn_off(tray: Any, current, cause: str, monotonic_fn, last_apply_warn_at: float):
    log_event = getattr(tray, "_log_event", None)
    if callable(log_event):
        try:
            log_event(
                "config",
                "apply_turn_off",
                cause=str(cause or "unknown"),
                brightness=0,
            )
        except Exception:
            pass
    try:
        tray.engine.turn_off()
    except Exception as exc:
        now = float(monotonic_fn())
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
    return last_apply_warn_at


def _sync_reactive(tray: Any, current) -> None:
    try:
        tray.engine.reactive_use_manual_color = bool(current.reactive_use_manual)
        tray.engine.reactive_color = tuple(current.reactive_color)
    except Exception:
        pass


def _apply_perkey(tray: Any, current, ite_num_rows: int, ite_num_cols: int, *, cause: str) -> None:
    if callable(getattr(tray, "_log_event", None)):
        try:
            tray._log_event(
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


def _apply_uniform(tray: Any, *, cause: str) -> None:
    if callable(getattr(tray, "_log_event", None)):
        try:
            tray._log_event(
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


def _apply_effect(tray: Any, *, cause: str) -> None:
    if callable(getattr(tray, "_log_event", None)):
        try:
            tray._log_event(
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
