from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Protocol

from src.core.utils.logging_utils import log_throttled
from src.tray.controllers import menu_adapters as profile_power_menu_actions

from src.core.power.system import get_status, set_mode
from ._menu_sections_profile_power import ProfilePowerMenuBuilder


_MenuAction = Callable[[object, object], None]
_ProfileActivationAction = Callable[[], None]


class _MenuFactoryProtocol(Protocol):
    SEPARATOR: object

    def __call__(self, *items: object) -> object: ...


class _PystrayProtocol(Protocol):
    Menu: _MenuFactoryProtocol


class _ItemFactoryProtocol(Protocol):
    def __call__(self, text: str, action: object | None = None, **kwargs: object) -> object: ...


class _SystemPowerMenuTrayProtocol(Protocol):
    _on_power_mode_settings_clicked: _MenuAction


class _PerkeyMenuTrayProtocol(Protocol):
    _on_perkey_clicked: _MenuAction


logger = logging.getLogger(__name__)

_MENU_BUILD_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
# Profile menu activation callbacks (UI/persist/runtime); keep OSError, drop map LookupError.
_PROFILE_CALLBACK_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def _log_menu_debug(key: str, msg: str, exc: Exception, *, interval_s: float = 60) -> None:
    log_throttled(
        logger,
        key,
        interval_s=interval_s,
        level=logging.DEBUG,
        msg=msg,
        exc=exc,
    )


def _make_profile_activation_callback(
    action: _ProfileActivationAction,
    *,
    debug_key: str,
    debug_msg: str,
) -> _MenuAction:
    def _cb(_icon: object, _item: object) -> None:
        try:
            action()
        except _PROFILE_CALLBACK_EXCEPTIONS as exc:  # @quality-exception exception-transparency: tray profile activation callbacks cross UI, persistence, and runtime backend/effect boundaries and must remain best-effort for recoverable failures while unexpected defects still propagate
            _log_menu_debug(
                debug_key,
                debug_msg,
                exc,
                interval_s=60,
            )

    return _cb


def _profile_power_menu_builder() -> ProfilePowerMenuBuilder:
    return ProfilePowerMenuBuilder(
        make_profile_activation_callback=_make_profile_activation_callback,
        log_menu_debug=_log_menu_debug,
        get_status=get_status,
        set_mode=set_mode,
        set_system_power_result=profile_power_menu_actions.set_system_power_last_ok,
        refresh_system_power_menu=profile_power_menu_actions.update_menu_if_present,
        list_perkey_profiles=profile_power_menu_actions.list_perkey_profiles,
        get_active_perkey_profile=profile_power_menu_actions.get_active_perkey_profile,
        activate_perkey_profile=profile_power_menu_actions.activate_perkey_profile,
    )


def build_system_power_mode_menu(
    tray: _SystemPowerMenuTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
) -> object | None:
    """Build a lightweight power mode submenu backed by cpufreq sysfs.

    Returns None when unsupported.
    """
    return _profile_power_menu_builder().build_system_power_mode_menu(
        tray,
        pystray=pystray,
        item=item,
    )


def build_perkey_profiles_menu(
    tray: _PerkeyMenuTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    per_key_supported: bool,
    secondary_lighting_supported: bool = False,
) -> object | None:
    """Build the whole-scene lighting profiles submenu.

    Returns None when neither per-key nor secondary lighting is supported.
    """
    return _profile_power_menu_builder().build_perkey_profiles_menu(
        tray,
        pystray=pystray,
        item=item,
        per_key_supported=per_key_supported,
        secondary_lighting_supported=secondary_lighting_supported,
    )
