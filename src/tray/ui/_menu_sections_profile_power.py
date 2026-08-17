from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from src.core.power.system import PowerMode
from src.tray.controllers.runtime_coordination import run_tray_transition

_MenuAction = Callable[[object, object], None]
_MenuChecked = Callable[[object], bool]
_ProfileActivationAction = Callable[[], None]

_MENU_BUILD_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
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


_ReadStatus = Callable[[object], object | None]
_RefreshStatus = Callable[[object], object]


class _SetModeProtocol(Protocol):
    def __call__(self, mode: PowerMode) -> object: ...


class _SystemPowerMenuTrayProtocol(Protocol):
    _on_power_mode_settings_clicked: _MenuAction


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
    read_status: _ReadStatus
    refresh_status: _RefreshStatus
    set_mode: _SetModeProtocol
    set_system_power_result: _SetSystemPowerResultProtocol
    refresh_system_power_menu: _RefreshSystemPowerMenuProtocol
    list_perkey_profiles: _ListPerkeyProfilesProtocol
    get_active_perkey_profile: _GetActivePerkeyProfileProtocol
    activate_perkey_profile: _ActivatePerkeyProfileProtocol

    def build_system_power_mode_menu(
        self,
        tray: _SystemPowerMenuTrayProtocol,
        *,
        pystray: _PystrayProtocol,
        item: _ItemFactoryProtocol,
    ) -> object | None:
        try:
            status = self.read_status(tray)
            if status is None or not bool(getattr(status, "supported", False)):
                return None
            raw_identifiers = getattr(status, "identifiers", None)
            identifiers = raw_identifiers if isinstance(raw_identifiers, Mapping) else {}
            can_apply = identifiers.get("can_apply") == "true"
            current_mode = getattr(status, "mode", None)

            return pystray.Menu(
                item(
                    "Extreme Saver",
                    self._system_power_callback(tray, PowerMode.EXTREME_SAVER),
                    checked=self._checked_system_power_mode(PowerMode.EXTREME_SAVER, current_mode),
                    enabled=can_apply,
                    radio=True,
                ),
                item(
                    "Balanced",
                    self._system_power_callback(tray, PowerMode.BALANCED),
                    checked=self._checked_system_power_mode(PowerMode.BALANCED, current_mode),
                    enabled=can_apply,
                    radio=True,
                ),
                item(
                    "Performance",
                    self._system_power_callback(tray, PowerMode.PERFORMANCE),
                    checked=self._checked_system_power_mode(PowerMode.PERFORMANCE, current_mode),
                    enabled=can_apply,
                    radio=True,
                ),
                pystray.Menu.SEPARATOR,
                item("Power Mode Settings…", tray._on_power_mode_settings_clicked),
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
        secondary_lighting_supported: bool = False,
    ) -> object | None:
        if not per_key_supported and not secondary_lighting_supported:
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
                item("Lighting Profile Editor", tray._on_perkey_clicked),
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
            return pystray.Menu(item("Lighting Profile Editor", tray._on_perkey_clicked))

    def _system_power_callback(self, tray: object, mode: PowerMode) -> _MenuAction:
        def _cb(_icon: object, _item: object) -> None:
            def apply_power_mode_transition() -> None:
                try:
                    ok = self.set_mode(mode)
                    self.refresh_status(tray)
                    self.set_system_power_result(tray, bool(ok))
                except _SYSTEM_POWER_CALLBACK_EXCEPTIONS as exc:
                    self.refresh_status(tray)
                    self.set_system_power_result(tray, False)
                    self.log_menu_debug(
                        "tray.menu.system_power.click",
                        "System power mode activation failed",
                        exc,
                        interval_s=60,
                    )
                finally:
                    self.refresh_system_power_menu(tray)

            run_tray_transition(tray, apply_power_mode_transition)

        return _cb

    def _checked_system_power_mode(self, mode: PowerMode, current_mode: object) -> _MenuChecked:
        def _is_checked(_item: object) -> bool:
            return current_mode == mode

        return _is_checked

    def _perkey_profile_callback(self, tray: _PerkeyMenuTrayProtocol, profile_name: str) -> _MenuAction:
        def _activate_profile() -> None:
            self.activate_perkey_profile(tray, profile_name)

        return self.make_profile_activation_callback(
            _activate_profile,
            debug_key="tray.menu.perkey_profile_click",
            debug_msg="Per-key profile activation callback failed",
        )
