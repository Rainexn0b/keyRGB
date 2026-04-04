from __future__ import annotations

from typing import Any

from src.core.effects.catalog import normalize_effect_name


def effect_key_callback(tray: Any, effect: str):
    def _action(_icon, _item):
        tray._on_effect_key_clicked(effect)

    return _action


def checked_hw_effect(tray: Any, effect: str, *, hw_mode: bool):
    def _checked(_item):
        current = normalize_effect_name(str(getattr(tray.config, "effect", "none") or "none"))
        return (
            current in {effect, normalize_effect_name(effect), normalize_effect_name(effect).removeprefix("hw:")}
            and hw_mode
            and not tray.is_off
        )

    return _checked


def checked_sw_effect(tray: Any, effect: str, *, sw_mode: bool):
    def _checked(_item):
        return tray.config.effect == effect and sw_mode and not tray.is_off

    return _checked


def checked_speed(tray: Any, speed: int):
    def _checked(_item):
        return tray.config.speed == speed

    return _checked


def checked_brightness(tray: Any, brightness: int):
    def _checked(_item):
        return tray.config.brightness == brightness

    return _checked


def checked_hw_static(tray: Any, *, hw_mode: bool):
    def _checked(_item):
        return tray.config.effect == "none" and hw_mode and not tray.is_off

    return _checked


def device_context_callback(tray: Any, context_key: str):
    def _action(_icon, _item):
        tray._on_device_context_clicked(context_key)

    return _action


def checked_device_context(selected_context: dict[str, Any], context_key: str):
    def _checked(_item):
        return str(selected_context.get("key") or "keyboard") == context_key

    return _checked


def software_target_callback(tray: Any, target_key: str):
    def _action(_icon, _item):
        tray._on_software_effect_target_clicked(target_key)

    return _action


def checked_software_target(tray: Any, target_key: str):
    def _checked(_item):
        current = str(getattr(tray.config, "software_effect_target", "keyboard") or "keyboard")
        return current == target_key

    return _checked


def checked_perkey(tray: Any):
    def _checked(_item):
        return tray.config.effect == "perkey" and not tray.is_off

    return _checked
