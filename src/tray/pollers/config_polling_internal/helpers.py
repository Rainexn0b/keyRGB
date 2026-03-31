from __future__ import annotations

from src.tray.protocols import ConfigPollingTrayProtocol


def _log_detected_change(tray: ConfigPollingTrayProtocol, last_applied, current, cause: str, state_for_log_fn):
    log_event = tray._log_event
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


def _handle_forced_off(tray: ConfigPollingTrayProtocol, last_applied, current, cause: str, state_for_log_fn):
    if not tray.is_off:
        return False

    if not (bool(tray._user_forced_off) or bool(tray._power_forced_off) or bool(tray._idle_forced_off)):
        return False

    log_event = tray._log_event
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
    try:
        log_event(
            "config",
            "skipped_forced_off",
            cause=str(cause or "unknown"),
            is_off=True,
            user_forced_off=bool(tray._user_forced_off),
            power_forced_off=bool(tray._power_forced_off),
            idle_forced_off=bool(tray._idle_forced_off),
        )
    except Exception:
        pass
    try:
        tray._update_menu()
    except Exception:
        pass
    return True


def _apply_turn_off(tray: ConfigPollingTrayProtocol, current, cause: str, monotonic_fn, last_apply_warn_at: float):
    log_event = tray._log_event
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


def _sync_reactive(tray: ConfigPollingTrayProtocol, current) -> None:
    try:
        tray.engine.reactive_use_manual_color = bool(current.reactive_use_manual)
        tray.engine.reactive_color = tuple(current.reactive_color)
        tray.engine.reactive_brightness = int(
            getattr(current, "reactive_brightness", getattr(tray.config, "reactive_brightness", tray.config.brightness))
            or 0
        )
    except Exception:
        pass


def _apply_perkey(
    tray: ConfigPollingTrayProtocol, current, ite_num_rows: int, ite_num_cols: int, *, cause: str
) -> None:
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
    configured_map = getattr(tray.config, "per_key_colors", None)
    if configured_map is None:
        configured_map = {}
    color_map = configured_map

    if 0 < len(configured_map) < (ite_num_rows * ite_num_cols):
        color_map = dict(configured_map)
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


def _apply_uniform(tray: ConfigPollingTrayProtocol, *, cause: str) -> None:
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


def _apply_effect(tray: ConfigPollingTrayProtocol, *, cause: str) -> None:
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
