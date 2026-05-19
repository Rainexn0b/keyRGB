from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Protocol, TypeAlias, cast


_RUNTIME_ACTIVATION_STATE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
PerKeyCoord: TypeAlias = tuple[int, int]
PerKeyColor: TypeAlias = tuple[int, int, int]
PerKeyColorMap: TypeAlias = dict[PerKeyCoord, PerKeyColor]


class _RuntimeProfileActivationTrayProtocol(Protocol):
    config: object
    is_off: bool

    def _start_current_effect(self, **kwargs: object) -> None: ...

    def _update_icon(self, *, animate: bool = True) -> None: ...

    def _update_menu(self) -> None: ...


class _OptionalPowerForcedOffTrayProtocol(Protocol):
    _power_forced_off: object


def _resolve_tray_callback(tray: object, name: str):
    instance_callback = vars(tray).get(name)
    if callable(instance_callback):
        return instance_callback

    class_callback = getattr(type(tray), name, None)
    if not callable(class_callback):
        return None

    return lambda *args, **kwargs: class_callback(tray, *args, **kwargs)


def _power_forced_off_or_false(tray: object) -> bool:
    try:
        return bool(cast(_OptionalPowerForcedOffTrayProtocol, tray)._power_forced_off)
    except AttributeError:
        return False


def _mirror_optional_idle_power_state_field(tray: object, *, state_name: str, value: object) -> None:
    owner = getattr(tray, "tray_idle_power_state", None)
    if owner is None:
        return
    try:
        setattr(owner, state_name, value)
    except _RUNTIME_ACTIVATION_STATE_EXCEPTIONS:
        return


def _mark_recent_power_source_transition(
    tray: object,
    *,
    profile_name: str | None,
    monotonic_fn: Callable[[], float],
) -> None:
    try:
        changed_at = float(monotonic_fn())
    except _RUNTIME_ACTIVATION_STATE_EXCEPTIONS:
        return
    try:
        setattr(tray, "_last_power_source_transition_at", changed_at)
    except _RUNTIME_ACTIVATION_STATE_EXCEPTIONS:
        return
    _mirror_optional_idle_power_state_field(
        tray,
        state_name="last_power_source_transition_at",
        value=changed_at,
    )

    if profile_name is None:
        return

    profile_name_text = str(profile_name)
    try:
        setattr(tray, "_last_power_source_transition_profile_name", profile_name_text)
    except _RUNTIME_ACTIVATION_STATE_EXCEPTIONS:
        return
    _mirror_optional_idle_power_state_field(
        tray,
        state_name="last_power_source_transition_profile_name",
        value=profile_name_text,
    )


def _apply_runtime_profile_transition(tray: object) -> bool:
    apply_transition = _resolve_tray_callback(tray, "_apply_power_source_perkey_profile_transition")
    if not callable(apply_transition):
        return False

    try:
        return bool(apply_transition())
    except AttributeError:
        return False


def activate_perkey_profile_runtime(
    tray: object,
    profile_name: str,
    *,
    set_active_profile_fn: Callable[[str], str],
    load_per_key_colors_fn: Callable[[str | None], Mapping[PerKeyCoord, PerKeyColor]],
    apply_profile_to_config_fn: Callable[[object, PerKeyColorMap], None],
    mark_power_source_transition: bool = False,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> str:
    activation_tray = cast(_RuntimeProfileActivationTrayProtocol, tray)
    name = set_active_profile_fn(profile_name)
    colors = dict(load_per_key_colors_fn(name) or {})
    apply_profile_to_config_fn(activation_tray.config, colors)

    if mark_power_source_transition:
        _mark_recent_power_source_transition(
            activation_tray,
            profile_name=name,
            monotonic_fn=monotonic_fn,
        )

    if not _power_forced_off_or_false(tray):
        activation_tray.is_off = False
        if not _apply_runtime_profile_transition(activation_tray):
            activation_tray._start_current_effect()

    activation_tray._update_icon()
    activation_tray._update_menu()
    return name
