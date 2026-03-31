from __future__ import annotations

from dataclasses import dataclass

from src.core.effects.catalog import REACTIVE_EFFECTS
from src.core.effects.catalog import resolve_effect_name_for_backend
from src.core.utils.safe_attrs import safe_int_attr
from src.tray.protocols import ConfigPollingTrayProtocol


REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)


@dataclass(frozen=True)
class ConfigApplyState:
    effect: str
    speed: int
    brightness: int
    color: tuple[int, int, int]
    perkey_sig: tuple | None
    reactive_use_manual: bool
    reactive_color: tuple[int, int, int]
    reactive_brightness: int = 0


def compute_config_apply_state(tray: ConfigPollingTrayProtocol) -> ConfigApplyState:
    try:
        effect = resolve_effect_name_for_backend(
            str(getattr(tray.config, "effect", "none") or "none"),
            getattr(tray, "backend", None),
        )
    except Exception:
        effect = "none"

    perkey_sig = None
    if effect == "perkey":
        try:
            perkey_sig = tuple(sorted(tray.config.per_key_colors.items()))
        except Exception:
            perkey_sig = None

    try:
        reactive_use_manual = bool(getattr(tray.config, "reactive_use_manual_color", False))
    except Exception:
        reactive_use_manual = False
    try:
        reactive_color = tuple(getattr(tray.config, "reactive_color", (255, 255, 255)))
    except Exception:
        reactive_color = (255, 255, 255)

    base_brightness = safe_int_attr(tray.config, "brightness", default=0)
    reactive_brightness = 0
    if effect in REACTIVE_EFFECTS_SET:
        reactive_brightness = safe_int_attr(tray.config, "reactive_brightness", default=base_brightness)

    try:
        color = tuple(getattr(tray.config, "color", (255, 255, 255)))
    except Exception:
        color = (255, 255, 255)

    return ConfigApplyState(
        effect=str(effect),
        speed=safe_int_attr(tray.config, "speed", default=0),
        brightness=base_brightness,
        color=tuple(color),
        perkey_sig=perkey_sig,
        reactive_use_manual=bool(reactive_use_manual),
        reactive_color=tuple(reactive_color),
        reactive_brightness=int(reactive_brightness),
    )


def state_for_log(state: ConfigApplyState | None):
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


def maybe_apply_fast_path(
    tray: ConfigPollingTrayProtocol,
    *,
    last_applied: ConfigApplyState | None,
    current: ConfigApplyState,
    sw_effects_set: set[str] | frozenset[str],
) -> tuple[bool, ConfigApplyState]:
    """Apply fast-path config updates."""

    if last_applied is None:
        return False, current

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
                or last_applied.reactive_brightness != current.reactive_brightness
            )
        )
    except Exception:
        only_reactive_changed = False

    if only_reactive_changed:
        try:
            tray.engine.reactive_use_manual_color = bool(current.reactive_use_manual)
            tray.engine.reactive_color = tuple(current.reactive_color)
            tray.engine.reactive_brightness = int(current.reactive_brightness)
        except Exception:
            pass
        try:
            tray._refresh_ui()
        except Exception:
            pass
        return True, current

    try:
        only_brightness_changed = (
            last_applied.effect == current.effect
            and last_applied.speed == current.speed
            and last_applied.color == current.color
            and last_applied.perkey_sig == current.perkey_sig
            and last_applied.reactive_use_manual == current.reactive_use_manual
            and last_applied.reactive_color == current.reactive_color
            and last_applied.reactive_brightness == current.reactive_brightness
            and last_applied.brightness != current.brightness
        )
    except Exception:
        only_brightness_changed = False

    if (
        only_brightness_changed
        and str(current.effect) in sw_effects_set
        and bool(getattr(tray.engine, "running", False))
    ):
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


def apply_from_config_once(
    tray: ConfigPollingTrayProtocol,
    *,
    ite_num_rows: int,
    ite_num_cols: int,
    cause: str,
    last_applied: ConfigApplyState | None,
    last_apply_warn_at: float,
    monotonic_fn,
    compute_state_fn,
    state_for_log_fn,
    maybe_apply_fast_path_fn,
    is_device_disconnected_fn,
) -> tuple[ConfigApplyState | None, float]:
    """Apply current tray config once."""

    try:
        current = compute_state_fn(tray)
    except Exception as exc:
        now = float(monotonic_fn())
        if now - last_apply_warn_at > 60:
            last_apply_warn_at = now
            try:
                tray._log_exception("Error computing config signature: %s", exc)
            except (OSError, RuntimeError, ValueError):
                pass
        return last_applied, last_apply_warn_at

    if current == last_applied:
        return last_applied, last_apply_warn_at

    try:
        if str(getattr(tray.config, "effect", "none") or "none") != current.effect:
            tray.config.effect = current.effect
    except Exception:
        pass

    log_event = getattr(tray, "_log_event", None)
    from .helpers import (
        _apply_effect,
        _apply_perkey,
        _apply_turn_off,
        _apply_uniform,
        _handle_forced_off,
        _sync_reactive,
    )

    if _handle_forced_off(tray, last_applied, current, cause, state_for_log_fn):
        return current, last_apply_warn_at

    handled, new_last_applied = maybe_apply_fast_path_fn(tray, last_applied=last_applied, current=current)
    if handled:
        return new_last_applied, last_apply_warn_at

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

    if tray.config.brightness == 0:
        last_apply_warn_at = _apply_turn_off(tray, current, cause, monotonic_fn, last_apply_warn_at)
        return current, last_apply_warn_at

    if tray.config.brightness > 0:
        tray._last_brightness = tray.config.brightness

    _sync_reactive(tray, current)

    try:
        if current.effect == "perkey":
            _apply_perkey(tray, current, ite_num_rows, ite_num_cols, cause=cause)
        elif current.effect == "none":
            _apply_uniform(tray, cause=cause)
        else:
            _apply_effect(tray, cause=cause)
    except Exception as exc:
        if is_device_disconnected_fn(exc):
            try:
                tray.engine.mark_device_unavailable()
            except Exception as mark_exc:
                now = float(monotonic_fn())
                if now - last_apply_warn_at > 60:
                    last_apply_warn_at = now
                    try:
                        tray._log_exception("Failed to mark device unavailable: %s", mark_exc)
                    except (OSError, RuntimeError, ValueError):
                        pass
        tray._log_exception("Error applying config change: %s", exc)

    try:
        tray._refresh_ui()
    except Exception:
        pass

    return current, last_apply_warn_at
