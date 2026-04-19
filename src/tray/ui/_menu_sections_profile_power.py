from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from src.core.power.system import PowerMode
from src.core.power.tcc_profiles.models import TccProfile


_MenuAction = Callable[[object, object], None]
_MenuChecked = Callable[[object], bool]
_ProfileActivationAction = Callable[[], None]

_MENU_BUILD_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
_TCC_MENU_EXCEPTIONS = _MENU_BUILD_EXCEPTIONS + (OSError,)
_SYSTEM_POWER_MENU_EXCEPTIONS = _MENU_BUILD_EXCEPTIONS + (OSError,)
_SYSTEM_POWER_CALLBACK_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_PERKEY_MENU_EXCEPTIONS = _MENU_BUILD_EXCEPTIONS + (ImportError, OSError)


class _MenuFactoryProtocol(Protocol):
    SEPARATOR: object

    def __call__(self, *items: object) -> object: ...


class _PystrayProtocol(Protocol):
    Menu: _MenuFactoryProtocol


class _ItemFactoryProtocol(Protocol):
    def __call__(self, text: str, action: object | None = None, **kwargs: object) -> object: ...


class _TccProfilesProviderProtocol(Protocol):
    def list_profiles(self) -> Sequence[TccProfile]: ...

    def get_active_profile(self) -> TccProfile | None: ...


class _TccProfilesTrayProtocol(Protocol):
    _on_tcc_profiles_gui_clicked: _MenuAction

    def _on_tcc_profile_clicked(self, profile_id: str) -> None: ...


class _SystemPowerStatusProtocol(Protocol):
    @property
    def supported(self) -> bool: ...

    @property
    def identifiers(self) -> Mapping[str, str]: ...

    @property
    def mode(self) -> PowerMode | None: ...


_GetStatus = Callable[[], _SystemPowerStatusProtocol]


class _SetModeProtocol(Protocol):
    def __call__(self, mode: PowerMode) -> object: ...


class _PerkeyMenuTrayProtocol(Protocol):
    _on_perkey_clicked: _MenuAction


class _LogMenuDebugProtocol(Protocol):
    def __call__(self, key: str, msg: str, exc: Exception, *, interval_s: float = 60) -> None: ...


class _MakeProfileActivationCallbackProtocol(Protocol):
    def __call__(
        self,
        action: _ProfileActivationAction,
        *,
        debug_key: str,
        debug_msg: str,
    ) -> _MenuAction: ...


class _SetSystemPowerResultProtocol(Protocol):
    def __call__(self, tray: object, ok: bool) -> None: ...


class _RefreshSystemPowerMenuProtocol(Protocol):
    def __call__(self, tray: object) -> None: ...


class _ListPerkeyProfilesProtocol(Protocol):
    def __call__(self) -> Sequence[str]: ...


class _GetActivePerkeyProfileProtocol(Protocol):
    def __call__(self) -> str | None: ...


class _ActivatePerkeyProfileProtocol(Protocol):
    def __call__(self, tray: object, profile_name: str) -> None: ...


@dataclass(frozen=True)
class ProfilePowerMenuBuilder:
    make_profile_activation_callback: _MakeProfileActivationCallbackProtocol
    log_menu_debug: _LogMenuDebugProtocol
    get_status: _GetStatus
    set_mode: _SetModeProtocol
    set_system_power_result: _SetSystemPowerResultProtocol
    refresh_system_power_menu: _RefreshSystemPowerMenuProtocol
    list_perkey_profiles: _ListPerkeyProfilesProtocol
    get_active_perkey_profile: _GetActivePerkeyProfileProtocol
    activate_perkey_profile: _ActivatePerkeyProfileProtocol

    def build_tcc_profiles_menu(
        self,
        tray: _TccProfilesTrayProtocol,
        *,
        pystray: _PystrayProtocol,
        item: _ItemFactoryProtocol,
        tcc: _TccProfilesProviderProtocol,
    ) -> object | None:
        try:
            tcc_profiles = tcc.list_profiles()
            active = tcc.get_active_profile()
            if not tcc_profiles:
                return None

            profile_items = [
                item(
                    profile.name,
                    self._tcc_profile_callback(tray, profile.id),
                    checked=lambda _i, pid=profile.id: active is not None and active.id == pid,
                    radio=True,
                )
                for profile in tcc_profiles
            ]

            return pystray.Menu(
                item("Open Power Profiles…", tray._on_tcc_profiles_gui_clicked),
                pystray.Menu.SEPARATOR,
                *profile_items,
            )
        except _TCC_MENU_EXCEPTIONS as exc:
            self.log_menu_debug(
                "tray.menu.tcc_profiles",
                "Failed to populate TCC profiles menu",
                exc,
                interval_s=120,
            )
            return None

    def _tcc_profile_callback(self, tray: _TccProfilesTrayProtocol, profile_id: str) -> _MenuAction:
        def _activate_profile() -> None:
            tray._on_tcc_profile_clicked(profile_id)

        return self.make_profile_activation_callback(
            _activate_profile,
            debug_key="tray.menu.tcc_profile_click",
            debug_msg="TCC profile activation callback failed",
        )

    def build_system_power_mode_menu(
        self,
        tray: object,
        *,
        pystray: _PystrayProtocol,
        item: _ItemFactoryProtocol,
    ) -> object | None:
        try:
            status = self.get_status()
            if not status.supported:
                return None
            can_apply = status.identifiers.get("can_apply") == "true"

            return pystray.Menu(
                item(
                    "Extreme Saver",
                    self._system_power_callback(tray, PowerMode.EXTREME_SAVER),
                    checked=self._checked_system_power_mode(PowerMode.EXTREME_SAVER),
                    enabled=can_apply,
                    radio=True,
                ),
                item(
                    "Balanced",
                    self._system_power_callback(tray, PowerMode.BALANCED),
                    checked=self._checked_system_power_mode(PowerMode.BALANCED),
                    enabled=can_apply,
                    radio=True,
                ),
                item(
                    "Performance",
                    self._system_power_callback(tray, PowerMode.PERFORMANCE),
                    checked=self._checked_system_power_mode(PowerMode.PERFORMANCE),
                    enabled=can_apply,
                    radio=True,
                ),
            )
        except _SYSTEM_POWER_MENU_EXCEPTIONS as exc:
            self.log_menu_debug(
                "tray.menu.system_power",
                "Failed to populate system power mode menu",
                exc,
                interval_s=120,
            )
            return None

    def build_perkey_profiles_menu(
        self,
        tray: _PerkeyMenuTrayProtocol,
        *,
        pystray: _PystrayProtocol,
        item: _ItemFactoryProtocol,
        per_key_supported: bool,
    ) -> object | None:
        if not per_key_supported:
            return None

        try:
            perkey_profiles = self.list_perkey_profiles()
            active_profile = self.get_active_perkey_profile()

            profile_items = [
                item(
                    name,
                    self._perkey_profile_callback(tray, name),
                    checked=lambda _i, current_name=name: active_profile == current_name,
                    radio=True,
                )
                for name in perkey_profiles
            ]

            return pystray.Menu(
                item("Open Color Editor…", tray._on_perkey_clicked),
                pystray.Menu.SEPARATOR,
                *profile_items,
            )
        except _PERKEY_MENU_EXCEPTIONS as exc:
            self.log_menu_debug(
                "tray.menu.perkey_profiles",
                "Failed to populate per-key profiles menu",
                exc,
                interval_s=120,
            )
            return pystray.Menu(item("Open Color Editor…", tray._on_perkey_clicked))

    def _system_power_callback(self, tray: object, mode: PowerMode) -> _MenuAction:
        def _cb(_icon: object, _item: object) -> None:
            try:
                ok = self.set_mode(mode)
                self.set_system_power_result(tray, bool(ok))
            except _SYSTEM_POWER_CALLBACK_EXCEPTIONS as exc:
                self.set_system_power_result(tray, False)
                self.log_menu_debug(
                    "tray.menu.system_power.click",
                    "System power mode activation failed",
                    exc,
                    interval_s=60,
                )
            finally:
                self.refresh_system_power_menu(tray)

        return _cb

    def _checked_system_power_mode(self, mode: PowerMode) -> _MenuChecked:
        current_mode = mode

        def _is_checked(_item: object) -> bool:
            return self.get_status().mode == current_mode

        return _is_checked

    def _perkey_profile_callback(self, tray: _PerkeyMenuTrayProtocol, profile_name: str) -> _MenuAction:
        def _activate_profile() -> None:
            self.activate_perkey_profile(tray, profile_name)

        return self.make_profile_activation_callback(
            _activate_profile,
            debug_key="tray.menu.perkey_profile_click",
            debug_msg="Per-key profile activation callback failed",
        )
