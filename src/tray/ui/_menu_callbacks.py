from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from src.core.effects.catalog import normalize_effect_name

from .menu_status import DeviceContextEntry


_MenuAction = Callable[[object, object], None]
_MenuChecked = Callable[[object], bool]


class _MenuConfig(Protocol):
    effect: object
    speed: int
    brightness: int
    software_effect_target: object


class _HasMenuConfig(Protocol):
    config: _MenuConfig


class _HasMenuPowerState(_HasMenuConfig, Protocol):
    is_off: bool


class _EffectKeyCallbackHost(Protocol):
    def _on_effect_key_clicked(self, effect: str) -> None: ...


class _DeviceContextCallbackHost(Protocol):
    def _on_device_context_clicked(self, context_key: str) -> None: ...


class _SoftwareTargetCallbackHost(Protocol):
    def _on_software_effect_target_clicked(self, target_key: str) -> None: ...


def effect_key_callback(tray: _EffectKeyCallbackHost, effect: str) -> _MenuAction:
    def _action(_icon: object, _item: object) -> None:
        tray._on_effect_key_clicked(effect)

    return _action


def checked_hw_effect(tray: _HasMenuPowerState, effect: str, *, hw_mode: bool) -> _MenuChecked:
    normalized_effect = normalize_effect_name(effect)
    allowed_effects = {effect, normalized_effect, normalized_effect.removeprefix("hw:")}

    def _checked(_item: object) -> bool:
        current = normalize_effect_name(str(getattr(tray.config, "effect", "none") or "none"))
        return current in allowed_effects and hw_mode and not tray.is_off

    return _checked


def checked_sw_effect(tray: _HasMenuPowerState, effect: str, *, sw_mode: bool) -> _MenuChecked:
    def _checked(_item: object) -> bool:
        return tray.config.effect == effect and sw_mode and not tray.is_off

    return _checked


def checked_speed(tray: _HasMenuConfig, speed: int) -> _MenuChecked:
    def _checked(_item: object) -> bool:
        return tray.config.speed == speed

    return _checked


def checked_brightness(tray: _HasMenuConfig, brightness: int) -> _MenuChecked:
    def _checked(_item: object) -> bool:
        return tray.config.brightness == brightness

    return _checked


def checked_hw_static(tray: _HasMenuPowerState, *, hw_mode: bool) -> _MenuChecked:
    def _checked(_item: object) -> bool:
        return tray.config.effect == "none" and hw_mode and not tray.is_off

    return _checked


def device_context_callback(tray: _DeviceContextCallbackHost, context_key: str) -> _MenuAction:
    def _action(_icon: object, _item: object) -> None:
        tray._on_device_context_clicked(context_key)

    return _action


def checked_device_context(
    selected_context: DeviceContextEntry | Mapping[str, object], context_key: str
) -> _MenuChecked:
    def _checked(_item: object) -> bool:
        return str(selected_context.get("key") or "keyboard") == context_key

    return _checked


def software_target_callback(tray: _SoftwareTargetCallbackHost, target_key: str) -> _MenuAction:
    def _action(_icon: object, _item: object) -> None:
        tray._on_software_effect_target_clicked(target_key)

    return _action


def checked_software_target(tray: _HasMenuConfig, target_key: str) -> _MenuChecked:
    def _checked(_item: object) -> bool:
        current = str(getattr(tray.config, "software_effect_target", "keyboard") or "keyboard")
        return current == target_key

    return _checked


def checked_perkey(tray: _HasMenuPowerState) -> _MenuChecked:
    def _checked(_item: object) -> bool:
        return tray.config.effect == "perkey" and not tray.is_off

    return _checked
