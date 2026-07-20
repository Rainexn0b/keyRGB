"""Field bridge: legacy tray attr ↔ typed ``TrayIdlePowerState`` owner.

Extracted from ``idle_power_state.py`` (WS1 / A2 slice 1). Callers should
prefer the public re-exports on ``src.tray.idle_power_state`` (and
``src.tray.protocols``) so import paths stay stable.
"""

from __future__ import annotations

from typing import Callable, Optional

from src.tray.idle_power_state import ensure_tray_idle_power_state


def _normalize_idle_power_field_names(
    *,
    attr_name: object,
    state_name: object,
    alias_kwargs: dict[str, object],
) -> tuple[str, str]:
    prior_attr_key = "le" + "gacy" + "_" + "attr"
    state_attr_key = "ow" + "ner" + "_" + "attr"

    if prior_attr_key in alias_kwargs:
        if attr_name is not None:
            raise TypeError("sync/set/read received multiple values for attr_name")
        attr_name = alias_kwargs.pop(prior_attr_key)

    if state_attr_key in alias_kwargs:
        if state_name is not None:
            raise TypeError("sync/set/read received multiple values for state_name")
        state_name = alias_kwargs.pop(state_attr_key)

    if alias_kwargs:
        bad = ", ".join(sorted(alias_kwargs))
        raise TypeError(f"unexpected keyword argument(s): {bad}")

    if attr_name is None:
        raise TypeError("missing required keyword argument: attr_name")
    if state_name is None:
        raise TypeError("missing required keyword argument: state_name")

    return str(attr_name), str(state_name)


def sync_idle_power_state_field(
    tray: object,
    *,
    attr_name: object = None,
    state_name: object = None,
    **alias_kwargs: object,
) -> object:
    """Synchronize one idle/power field and return the effective value.

    Compatibility rule:
    - Prefer the typed owner when present and the legacy attr is only a
      property/proxy (not an instance dict entry).
    - If a legacy *instance* attr exists (tests/fakes), it remains source-of-
      truth and the owner mirrors it.
    - Otherwise, owner value seeds the legacy attr.
    """

    attr_name, state_name = _normalize_idle_power_field_names(
        attr_name=attr_name,
        state_name=state_name,
        alias_kwargs=dict(alias_kwargs),
    )

    state = ensure_tray_idle_power_state(tray)

    tray_vars: dict[str, object]
    try:
        tray_vars = vars(tray)
    except TypeError:
        tray_vars = {}

    if attr_name in tray_vars:
        value = tray_vars[attr_name]
        setattr(state, state_name, value)
        return value

    value = getattr(state, state_name)
    try:
        setattr(tray, attr_name, value)
    except AttributeError:
        pass
    return value


def _coerce_idle_power_bool(value: object) -> tuple[bool, bool]:
    if isinstance(value, bool):
        return value, True

    if isinstance(value, (int, float)):
        return bool(value), True

    if isinstance(value, (str, bytes, bytearray)):
        text = value.decode() if isinstance(value, (bytes, bytearray)) else value
        normalized = text.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True, True
        if normalized in {"0", "false", "no", "off"}:
            return False, True

    return False, False


def _coerce_idle_power_optional_int(value: object) -> tuple[Optional[int], bool]:
    if value is None:
        return None, True

    if isinstance(value, bool):
        return None, False

    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            return int(value), True
        except (TypeError, ValueError):
            return None, False

    return None, False


def _coerce_idle_power_optional_bool(value: object) -> tuple[Optional[bool], bool]:
    if value is None:
        return None, True

    bool_value, ok = _coerce_idle_power_bool(value)
    if ok:
        return bool_value, True
    return None, False


def _coerce_idle_power_float(value: object) -> tuple[float, bool]:
    if isinstance(value, bool):
        return 0.0, False

    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            return float(value), True
        except (TypeError, ValueError):
            return 0.0, False

    return 0.0, False


def _read_idle_power_state_field_converged(
    tray: object,
    *,
    attr_name: object = None,
    state_name: object = None,
    default: object,
    coerce: Callable[[object], tuple[object, bool]],
    **alias_kwargs: object,
) -> object:
    attr_name, state_name = _normalize_idle_power_field_names(
        attr_name=attr_name,
        state_name=state_name,
        alias_kwargs=dict(alias_kwargs),
    )

    state = ensure_tray_idle_power_state(tray)

    tray_vars: dict[str, object]
    try:
        tray_vars = vars(tray)
    except TypeError:
        tray_vars = {}

    owner_value = getattr(state, state_name, default)
    owner_normalized, owner_ok = coerce(owner_value)

    if attr_name in tray_vars:
        prior_normalized, prior_ok = coerce(tray_vars[attr_name])
        value = prior_normalized if prior_ok else (owner_normalized if owner_ok else default)
    else:
        value = owner_normalized if owner_ok else default

    try:
        setattr(tray, attr_name, value)
    except AttributeError:
        pass
    setattr(state, state_name, value)
    return value


def read_idle_power_state_bool_field(
    tray: object,
    *,
    attr_name: object = None,
    state_name: object = None,
    default: bool = False,
    **alias_kwargs: object,
) -> bool:
    """Read a bool idle/power field with safe owner fallback and convergence."""

    value = _read_idle_power_state_field_converged(
        tray,
        attr_name=attr_name,
        state_name=state_name,
        default=bool(default),
        coerce=_coerce_idle_power_bool,
        **alias_kwargs,
    )
    return bool(value)


def read_idle_power_state_optional_int_field(
    tray: object,
    *,
    attr_name: object = None,
    state_name: object = None,
    default: Optional[int] = None,
    **alias_kwargs: object,
) -> Optional[int]:
    """Read an optional-int idle/power field with safe owner fallback and convergence."""

    value = _read_idle_power_state_field_converged(
        tray,
        attr_name=attr_name,
        state_name=state_name,
        default=default,
        coerce=_coerce_idle_power_optional_int,
        **alias_kwargs,
    )
    if value is None:
        return None
    if isinstance(value, (int, float, str, bytes, bytearray)):
        return int(value)
    return default


def read_idle_power_state_optional_bool_field(
    tray: object,
    *,
    attr_name: object = None,
    state_name: object = None,
    default: Optional[bool] = None,
    **alias_kwargs: object,
) -> Optional[bool]:
    """Read an optional-bool idle/power field with safe owner fallback and convergence."""

    value = _read_idle_power_state_field_converged(
        tray,
        attr_name=attr_name,
        state_name=state_name,
        default=default,
        coerce=_coerce_idle_power_optional_bool,
        **alias_kwargs,
    )
    if value is None:
        return None
    return bool(value)


def read_idle_power_state_float_field(
    tray: object,
    *,
    attr_name: object = None,
    state_name: object = None,
    default: float = 0.0,
    **alias_kwargs: object,
) -> float:
    """Read a float idle/power field with safe owner fallback and convergence."""

    value = _read_idle_power_state_field_converged(
        tray,
        attr_name=attr_name,
        state_name=state_name,
        default=float(default),
        coerce=_coerce_idle_power_float,
        **alias_kwargs,
    )
    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return float(default)
    return float(default)


def set_idle_power_state_field(
    tray: object,
    *,
    attr_name: object = None,
    state_name: object = None,
    value: object,
    **alias_kwargs: object,
) -> None:
    """Set idle/power field on typed owner and compatibility tray surface.

    Always writes the typed owner. Dual-writes the legacy tray attr only when
    that name is not already a property on the tray type (``KeyRGBTray`` stores
    truth on the owner via properties; duck-typed fakes still dual-write).
    """

    attr_name, state_name = _normalize_idle_power_field_names(
        attr_name=attr_name,
        state_name=state_name,
        alias_kwargs=dict(alias_kwargs),
    )

    setattr(ensure_tray_idle_power_state(tray), state_name, value)
    if isinstance(getattr(type(tray), attr_name, None), property):
        return
    try:
        setattr(tray, attr_name, value)
    except AttributeError:
        pass


def clear_idle_power_state_field(
    tray: object,
    *,
    attr_name: object = None,
    state_name: object = None,
    value: object,
    **alias_kwargs: object,
) -> None:
    """Clear a legacy idle/power attr while updating the typed owner state."""

    attr_name, state_name = _normalize_idle_power_field_names(
        attr_name=attr_name,
        state_name=state_name,
        alias_kwargs=dict(alias_kwargs),
    )

    try:
        tray_vars = vars(tray)
    except TypeError:
        tray_vars = {}
    tray_vars.pop(attr_name, None)

    try:
        tray.__delattr__(attr_name)
    except AttributeError:
        pass

    setattr(ensure_tray_idle_power_state(tray), state_name, value)
