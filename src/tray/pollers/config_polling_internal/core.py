from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from src.core.effects.catalog import REACTIVE_EFFECTS
from src.core.effects.catalog import resolve_effect_name_for_backend
from src.core.effects.software_targets import normalize_software_effect_target
from src.core.utils.safe_attrs import safe_bool_attr
from src.core.utils.safe_attrs import safe_int_attr
from src.core.utils.safe_attrs import safe_str_attr
from src.tray.protocols import ConfigPollingTrayProtocol


ColorTuple = tuple[int, int, int]

REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)
_CONFIG_FALLBACK_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
_FAST_PATH_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def _safe_tuple_attr(config: object, name: str, *, default: ColorTuple) -> ColorTuple:
    try:
        raw = getattr(config, name, default)
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return default

    if not isinstance(raw, Iterable):
        return default

    try:
        value = tuple(raw)
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return default

    if len(value) != 3:
        return default

    return cast(ColorTuple, value)


def _safe_perkey_signature(config: object) -> tuple | None:
    try:
        per_key_colors = getattr(config, "per_key_colors", None)
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return None

    if per_key_colors is None:
        return None

    try:
        return tuple(sorted(per_key_colors.items()))
    except _CONFIG_FALLBACK_EXCEPTIONS:
        return None


@dataclass(frozen=True)
class ConfigApplyState:
    effect: str
    speed: int
    brightness: int
    color: ColorTuple
    perkey_sig: tuple | None
    reactive_use_manual: bool
    reactive_color: ColorTuple
    reactive_brightness: int = 0
    software_effect_target: str = "keyboard"


def compute_config_apply_state(tray: ConfigPollingTrayProtocol) -> ConfigApplyState:
    try:
        effect = resolve_effect_name_for_backend(
            safe_str_attr(tray.config, "effect", default="none") or "none",
            getattr(tray, "backend", None),
        )
    except _CONFIG_FALLBACK_EXCEPTIONS:
        effect = "none"

    perkey_sig = None
    if effect == "perkey":
        perkey_sig = _safe_perkey_signature(tray.config)

    reactive_use_manual = safe_bool_attr(tray.config, "reactive_use_manual_color", default=False)
    reactive_color = _safe_tuple_attr(tray.config, "reactive_color", default=(255, 255, 255))

    base_brightness = safe_int_attr(tray.config, "brightness", default=0)
    reactive_brightness = 0
    if effect in REACTIVE_EFFECTS_SET:
        reactive_brightness = safe_int_attr(tray.config, "reactive_brightness", default=base_brightness)

    color = _safe_tuple_attr(tray.config, "color", default=(255, 255, 255))
    software_effect_target = normalize_software_effect_target(
        safe_str_attr(tray.config, "software_effect_target", default="keyboard") or "keyboard"
    )

    return ConfigApplyState(
        effect=str(effect),
        speed=safe_int_attr(tray.config, "speed", default=0),
        brightness=base_brightness,
        color=color,
        perkey_sig=perkey_sig,
        software_effect_target=software_effect_target,
        reactive_use_manual=bool(reactive_use_manual),
        reactive_color=reactive_color,
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
            "software_effect_target": state.software_effect_target,
        }
    except _CONFIG_FALLBACK_EXCEPTIONS:
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
        only_target_changed = (
            last_applied.effect == current.effect
            and last_applied.speed == current.speed
            and last_applied.brightness == current.brightness
            and last_applied.color == current.color
            and last_applied.perkey_sig == current.perkey_sig
            and last_applied.reactive_use_manual == current.reactive_use_manual
            and last_applied.reactive_color == current.reactive_color
            and last_applied.reactive_brightness == current.reactive_brightness
            and last_applied.software_effect_target != current.software_effect_target
        )
    except _CONFIG_FALLBACK_EXCEPTIONS:
        only_target_changed = False

    if only_target_changed:
        try:
            from .helpers import _sync_software_target_policy

            _sync_software_target_policy(tray, current)
        except _FAST_PATH_EXCEPTIONS:
            pass
        try:
            tray._refresh_ui()
        except _FAST_PATH_EXCEPTIONS:
            pass
        return True, current

    try:
        only_reactive_changed = (
            last_applied.effect == current.effect
            and last_applied.speed == current.speed
            and last_applied.brightness == current.brightness
            and last_applied.color == current.color
            and last_applied.perkey_sig == current.perkey_sig
            and last_applied.software_effect_target == current.software_effect_target
            and (
                last_applied.reactive_use_manual != current.reactive_use_manual
                or last_applied.reactive_color != current.reactive_color
                or last_applied.reactive_brightness != current.reactive_brightness
            )
        )
    except _CONFIG_FALLBACK_EXCEPTIONS:
        only_reactive_changed = False

    if only_reactive_changed:
        try:
            tray.engine.reactive_use_manual_color = bool(current.reactive_use_manual)
            tray.engine.reactive_color = current.reactive_color
            tray.engine.reactive_brightness = int(current.reactive_brightness)
        except _FAST_PATH_EXCEPTIONS:
            pass
        try:
            tray._refresh_ui()
        except _FAST_PATH_EXCEPTIONS:
            pass
        return True, current

    try:
        only_brightness_changed = (
            last_applied.effect == current.effect
            and last_applied.speed == current.speed
            and last_applied.color == current.color
            and last_applied.perkey_sig == current.perkey_sig
            and last_applied.software_effect_target == current.software_effect_target
            and last_applied.reactive_use_manual == current.reactive_use_manual
            and last_applied.reactive_color == current.reactive_color
            and last_applied.reactive_brightness == current.reactive_brightness
            and last_applied.brightness != current.brightness
        )
    except _CONFIG_FALLBACK_EXCEPTIONS:
        only_brightness_changed = False

    if (
        only_brightness_changed
        and str(current.effect) in sw_effects_set
        and bool(getattr(tray.engine, "running", False))
    ):
        try:
            tray.engine.set_brightness(int(current.brightness), apply_to_hardware=False)
        except _FAST_PATH_EXCEPTIONS:
            pass
        try:
            tray._refresh_ui()
        except _FAST_PATH_EXCEPTIONS:
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
    except _CONFIG_FALLBACK_EXCEPTIONS as exc:
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

    configured_effect = safe_str_attr(tray.config, "effect", default="none") or "none"
    if configured_effect != current.effect:
        try:
            tray.config.effect = current.effect
        except _CONFIG_FALLBACK_EXCEPTIONS:
            pass

    from .helpers import (
        _apply_effect,
        _apply_perkey,
        _apply_turn_off,
        _apply_uniform,
        _handle_forced_off,
        _sync_reactive,
        _sync_software_target_policy,
    )

    _sync_software_target_policy(tray, current)

    if _handle_forced_off(tray, last_applied, current, cause, state_for_log_fn):
        return current, last_apply_warn_at

    try:
        handled, new_last_applied = maybe_apply_fast_path_fn(tray, last_applied=last_applied, current=current)
    except _FAST_PATH_EXCEPTIONS as exc:
        now = float(monotonic_fn())
        if now - last_apply_warn_at > 60:
            last_apply_warn_at = now
            try:
                tray._log_exception("Error applying config fast path: %s", exc)
            except (OSError, RuntimeError, ValueError):
                pass
        handled, new_last_applied = False, current
    if handled:
        return new_last_applied, last_apply_warn_at

    try:
        old_state = state_for_log_fn(last_applied)
        new_state = state_for_log_fn(current)
        tray._log_event(
            "config",
            "detected_change",
            cause=str(cause or "unknown"),
            old=old_state,
            new=new_state,
        )
    except _CONFIG_FALLBACK_EXCEPTIONS:
        pass

    if current.brightness == 0:
        last_apply_warn_at = _apply_turn_off(tray, current, cause, monotonic_fn, last_apply_warn_at)
        return current, last_apply_warn_at

    if current.brightness > 0:
        tray._last_brightness = current.brightness

    _sync_reactive(tray, current)

    try:
        if current.effect == "perkey":
            _apply_perkey(tray, current, ite_num_rows, ite_num_cols, cause=cause)
        elif current.effect == "none":
            _apply_uniform(tray, current, cause=cause)
        else:
            _apply_effect(tray, current, cause=cause)
    except Exception as exc:  # @quality-exception exception-transparency: backend apply is a runtime hardware boundary and device disconnect/errors must degrade tray state gracefully
        if is_device_disconnected_fn(exc):
            try:
                tray.engine.mark_device_unavailable()
            except Exception as mark_exc:  # @quality-exception exception-transparency: marking device unavailable is itself a degraded-hardware boundary
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
    except Exception as exc:  # @quality-exception exception-transparency: tray UI refresh is a runtime Tk widget boundary and must not break config apply on widget errors
        now = float(monotonic_fn())
        if now - last_apply_warn_at > 60:
            last_apply_warn_at = now
            try:
                tray._log_exception("Failed to refresh tray UI after config apply: %s", exc)
            except (OSError, RuntimeError, ValueError):
                pass

    return current, last_apply_warn_at
