from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, cast

from src.core.profile import profiles as core_profiles

__all__ = [
    "activate_perkey_profile",
    "get_active_perkey_profile",
    "get_active_perkey_profile_name",
    "list_perkey_profiles",
    "set_system_power_last_ok",
    "update_menu_if_present",
]


class _OptionalUpdateMenuTrayProtocol(Protocol):
    _update_menu: object


class _OptionalPowerForcedOffTrayProtocol(Protocol):
    _power_forced_off: object


class _HasSystemPowerLastOk(Protocol):
    _system_power_last_ok: bool


class _PerkeyProfileActivationTrayProtocol(Protocol):
    config: object
    is_off: bool

    def _start_current_effect(self, **kwargs: object) -> None: ...

    def _update_icon(self, *, animate: bool = True) -> None: ...

    def _update_menu(self) -> None: ...


def list_perkey_profiles() -> Sequence[str]:
    return core_profiles.list_profiles()


def get_active_perkey_profile() -> str | None:
    active = core_profiles.get_active_profile()
    if active is None:
        return None
    return str(active)


def get_active_perkey_profile_name() -> str:
    return str(core_profiles.get_active_profile())


def set_system_power_last_ok(tray: object, ok: bool) -> None:
    cast(_HasSystemPowerLastOk, tray)._system_power_last_ok = bool(ok)


def update_menu_if_present(tray: object) -> None:
    try:
        update_menu = cast(_OptionalUpdateMenuTrayProtocol, tray)._update_menu
    except AttributeError:
        return
    if not callable(update_menu):
        return
    cast(Callable[[], None], update_menu)()


def activate_perkey_profile(tray: object, profile_name: str) -> None:
    activation_tray = cast(_PerkeyProfileActivationTrayProtocol, tray)
    name = core_profiles.set_active_profile(profile_name)
    colors = core_profiles.load_per_key_colors(name)
    core_profiles.apply_profile_to_config(activation_tray.config, colors)

    if not _power_forced_off_or_false(tray):
        activation_tray.is_off = False
        activation_tray._start_current_effect()

    activation_tray._update_icon()
    activation_tray._update_menu()


def _power_forced_off_or_false(tray: object) -> bool:
    try:
        return bool(cast(_OptionalPowerForcedOffTrayProtocol, tray)._power_forced_off)
    except AttributeError:
        return False
