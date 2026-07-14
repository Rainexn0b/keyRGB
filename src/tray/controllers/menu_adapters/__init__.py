from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, cast

from src.core.profile import profiles as core_profiles
from src.core.profile import runtime_activation as profile_runtime_activation

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


class _HasSystemPowerLastOk(Protocol):
    _system_power_last_ok: bool


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
    profile_runtime_activation.activate_perkey_profile_runtime(
        cast(object, tray),
        profile_name,
        set_active_profile_fn=core_profiles.set_active_profile,
        load_per_key_colors_fn=core_profiles.load_per_key_colors,
        apply_profile_to_config_fn=core_profiles.apply_profile_to_config,
        load_secondary_lighting_fn=core_profiles.load_secondary_lighting,
    )
