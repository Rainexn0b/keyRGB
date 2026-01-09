from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConfigApplyState:
    effect: str
    speed: int
    brightness: int
    color: tuple[int, int, int]
    perkey_sig: tuple | None
    reactive_use_manual: bool
    reactive_color: tuple[int, int, int]


def compute_config_apply_state(tray: Any) -> ConfigApplyState:
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
    tray: Any,
    *,
    last_applied: ConfigApplyState | None,
    current: ConfigApplyState,
    sw_effects_set: set[str] | frozenset[str],
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
    tray: Any,
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
    """Apply current tray config once.

    Intended for use by the polling loop and unit tests.
    Returns (new_last_applied, new_last_apply_warn_at).
    """

    # Signature is best-effort; avoid breaking reload on odd types.
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

    log_event = getattr(tray, "_log_event", None)
    # If the tray is currently off and a user/power/idle "forced off" state
    # is active, log and skip applying any changes.
    from ._config_polling_helpers import _handle_forced_off

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

    # If brightness is zero, attempt to turn off the engine in a
    # throttled manner and return early.
    from ._config_polling_helpers import _apply_turn_off

    if tray.config.brightness == 0:
        last_apply_warn_at = _apply_turn_off(tray, current, cause, monotonic_fn, last_apply_warn_at)
        return current, last_apply_warn_at

    if tray.config.brightness > 0:
        tray._last_brightness = tray.config.brightness

    # Always keep the engine's reactive color settings in sync so a running
    # reactive loop can pick up changes without requiring a restart.
    from ._config_polling_helpers import _sync_reactive

    _sync_reactive(tray, current)

    try:
        # Delegate the effect application to helpers to keep this function
        # compact and more testable.
        from ._config_polling_helpers import _apply_perkey, _apply_uniform, _apply_effect

        if tray.config.effect == "perkey":
            _apply_perkey(tray, current, ite_num_rows, ite_num_cols, cause=cause)

        elif tray.config.effect == "none":
            _apply_uniform(tray, cause=cause)

        else:
            _apply_effect(tray, cause=cause)

    except Exception as exc:
        # Device disconnects can happen at any time. Mark unavailable to avoid
        # spamming errors until a reconnect succeeds.
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
