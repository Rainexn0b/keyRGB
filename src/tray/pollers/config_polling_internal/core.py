from __future__ import annotations

from src.core.effects.catalog import REACTIVE_EFFECTS, resolve_effect_name_for_backend
from src.core.effects.software_targets import normalize_software_effect_target
from src.core.utils.safe_attrs import safe_bool_attr, safe_int_attr, safe_str_attr
from src.tray.protocols import ConfigPollingTrayProtocol, ConfigStateResolveTrayProtocol

from . import _planning as _planning
from . import _post_fast_path_apply as _post_fast_path_apply
from ._config_apply_state import _CONFIG_FALLBACK_EXCEPTIONS
from ._config_apply_state import _safe_perkey_signature, _safe_tuple_attr
from ._config_apply_state import ConfigApplyState, build_config_apply_state
from ._fast_path import apply_fast_path_change, classify_fast_path_change
from .helpers import (
    _apply_effect,
    _apply_perkey,
    _apply_turn_off,
    _apply_uniform,
    _handle_forced_off,
    _sync_reactive,
    _sync_software_target_policy,
)


REACTIVE_EFFECTS_SET = frozenset(REACTIVE_EFFECTS)
_FAST_PATH_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_CONFIG_RUNTIME_BOUNDARY_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
apply_post_fast_path_execution = _post_fast_path_apply.apply_post_fast_path_execution
execute_non_fast_path_plan = _post_fast_path_apply.execute_non_fast_path_plan
classify_apply_from_config = _planning.classify_apply_from_config
resolve_apply_from_config_policy = _planning.resolve_apply_from_config_policy


def compute_config_apply_state(tray: ConfigStateResolveTrayProtocol) -> ConfigApplyState:
    def _resolve_effect_name(effect_name: str) -> str:
        return resolve_effect_name_for_backend(effect_name, getattr(tray, "backend", None))

    return build_config_apply_state(
        tray.config,
        resolve_effect_name=_resolve_effect_name,
        read_bool_attr=safe_bool_attr,
        read_int_attr=safe_int_attr,
        read_str_attr=safe_str_attr,
        read_tuple_attr=_safe_tuple_attr,
        read_perkey_signature=_safe_perkey_signature,
        normalize_software_effect_target_fn=normalize_software_effect_target,
        reactive_effects_set=REACTIVE_EFFECTS_SET,
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

    change_kind = classify_fast_path_change(last_applied=last_applied, current=current)

    handled = apply_fast_path_change(
        tray,
        change_kind=change_kind,
        current=current,
        sw_effects_set=sw_effects_set,
    )
    if not handled:
        return False, current

    try:
        tray._refresh_ui()
    except _FAST_PATH_EXCEPTIONS:
        pass

    return True, current


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

    apply_plan = resolve_apply_from_config_policy(
        tray.config,
        current=current,
        read_str_attr_fn=safe_str_attr,
    )

    if apply_plan.persist_effect is not None:
        try:
            tray.config.effect = apply_plan.persist_effect
        except _CONFIG_FALLBACK_EXCEPTIONS:
            pass

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

    last_apply_warn_at = execute_non_fast_path_plan(
        tray,
        apply_plan=apply_plan,
        current=current,
        last_applied=last_applied,
        cause=cause,
        last_apply_warn_at=last_apply_warn_at,
        state_for_log_fn=state_for_log_fn,
        monotonic_fn=monotonic_fn,
        ite_num_rows=ite_num_rows,
        ite_num_cols=ite_num_cols,
        is_device_disconnected_fn=is_device_disconnected_fn,
        apply_turn_off_fn=_apply_turn_off,
        sync_reactive_fn=_sync_reactive,
        apply_perkey_fn=_apply_perkey,
        apply_uniform_fn=_apply_uniform,
        apply_effect_fn=_apply_effect,
        config_fallback_exceptions=_CONFIG_FALLBACK_EXCEPTIONS,
        runtime_boundary_exceptions=_CONFIG_RUNTIME_BOUNDARY_EXCEPTIONS,
    )

    return current, last_apply_warn_at
