from __future__ import annotations

from collections.abc import Callable, Sequence
import logging
from typing import Protocol, cast

from src.core.power.tcc_profiles.models import TccProfile
from src.core.utils.logging_utils import log_throttled
from src.core.utils.safe_attrs import safe_int_attr
from src.tray.secondary_device_routes import route_for_context_entry

from src.core.power.system import get_status, set_mode
from ._menu_sections_device_context import (
    DeviceContextEntry,
    build_device_context_menu_items as _build_device_context_menu_items,
)
from ._menu_sections_profile_power import ProfilePowerMenuBuilder
from .menu_status import device_context_controls_available


_MenuAction = Callable[[object, object], None]
_ProfileActivationAction = Callable[[], None]


class _MenuFactoryProtocol(Protocol):
    SEPARATOR: object

    def __call__(self, *items: object) -> object: ...


class _PystrayProtocol(Protocol):
    Menu: _MenuFactoryProtocol


class _ItemFactoryProtocol(Protocol):
    def __call__(self, text: str, action: object | None = None, **kwargs: object) -> object: ...


class _DeviceContextMenuTrayProtocol(Protocol):
    config: object | None
    _on_selected_device_color_clicked: _MenuAction
    _on_selected_device_brightness_clicked: _MenuAction
    _on_selected_device_turn_off_clicked: _MenuAction
    _on_support_debug_clicked: _MenuAction
    _on_power_settings_clicked: _MenuAction
    _on_quit_clicked: _MenuAction


class _TccProfilesProviderProtocol(Protocol):
    def list_profiles(self) -> Sequence[TccProfile]: ...

    def get_active_profile(self) -> TccProfile | None: ...


class _TccProfilesTrayProtocol(Protocol):
    _on_tcc_profiles_gui_clicked: _MenuAction

    def _on_tcc_profile_clicked(self, profile_id: str) -> None: ...


class _SystemPowerMenuTrayProtocol(Protocol):
    _system_power_last_ok: bool

    def _update_menu(self) -> None: ...


class _OptionalUpdateMenuTrayProtocol(Protocol):
    _update_menu: object


class _OptionalPowerForcedOffTrayProtocol(Protocol):
    _power_forced_off: object


class _PerkeyMenuTrayProtocol(Protocol):
    config: object
    is_off: bool
    _on_perkey_clicked: _MenuAction

    def _start_current_effect(self, **kwargs: object) -> None: ...

    def _update_icon(self, *, animate: bool = True) -> None: ...

    def _update_menu(self) -> None: ...


logger = logging.getLogger(__name__)

_MENU_BUILD_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
_PROFILE_CALLBACK_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _call_update_menu_if_present(tray: object) -> None:
    try:
        update_menu = cast(_OptionalUpdateMenuTrayProtocol, tray)._update_menu
    except AttributeError:
        return
    if not callable(update_menu):
        return
    cast(Callable[[], None], update_menu)()


def _power_forced_off_or_false(tray: object) -> bool:
    try:
        return bool(cast(_OptionalPowerForcedOffTrayProtocol, tray)._power_forced_off)
    except AttributeError:
        return False


def _device_context_controls_available_typed(tray: object, context_entry: DeviceContextEntry) -> bool:
    return device_context_controls_available(tray, context_entry)


def _safe_int_attr_typed(
    obj: object,
    attr_name: str,
    *,
    default: int = 0,
    min_v: int | None = None,
    max_v: int | None = None,
) -> int:
    return safe_int_attr(obj, attr_name, default=default, min_v=min_v, max_v=max_v)


def build_device_context_menu_items(
    tray: _DeviceContextMenuTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    context_entry: DeviceContextEntry,
) -> list[object]:
    """Build a selected device-context surface for non-keyboard devices."""

    return _build_device_context_menu_items(
        tray,
        pystray=pystray,
        item=item,
        context_entry=context_entry,
        route_for_context_entry=route_for_context_entry,
        device_context_controls_available=_device_context_controls_available_typed,
        safe_int_attr=_safe_int_attr_typed,
    )


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
        call_update_menu_if_present=_call_update_menu_if_present,
        power_forced_off_or_false=_power_forced_off_or_false,
    )


def build_tcc_profiles_menu(
    tray: _TccProfilesTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    tcc: _TccProfilesProviderProtocol,
) -> object | None:
    """Build the TCC profiles submenu (or return None if unavailable)."""
    return _profile_power_menu_builder().build_tcc_profiles_menu(
        tray,
        pystray=pystray,
        item=item,
        tcc=tcc,
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
) -> object | None:
    """Build the per-key profiles submenu.

    Returns None when per-key is not supported.
    """
    return _profile_power_menu_builder().build_perkey_profiles_menu(
        tray,
        pystray=pystray,
        item=item,
        per_key_supported=per_key_supported,
    )
