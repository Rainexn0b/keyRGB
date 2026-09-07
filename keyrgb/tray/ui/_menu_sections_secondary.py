"""Builders for the selected-secondary-device tray menu section.

Extracted from ``menu.py`` so ``build_menu_items`` stays a thin orchestrator:
keyboard-only branches remain in the parent module while this module owns
the selected-secondary-device branch — brightness policy, secondary lighting
state, secondary power, and label/on-off/color item construction.

The parent module derives ``selected_route`` via its own imported
``route_for_context_entry`` and passes it in; this module never resolves
routes itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from keyrgb.core import secondary_lighting_state
from keyrgb.core.secondary_device_routes import (
    BRIGHTNESS_POLICY_INDEPENDENT,
    BRIGHTNESS_POLICY_PRIMARY_SHARED,
    SecondaryDeviceRoute,
)
from keyrgb.tray import secondary_device_power


class _MenuFactoryProtocol(Protocol):
    SEPARATOR: object

    def __call__(self, *items: object) -> object: ...


class _PystrayProtocol(Protocol):
    Menu: _MenuFactoryProtocol


class _ItemFactoryProtocol(Protocol):
    def __call__(self, text: str, action: object | None = None, **kwargs: object) -> object: ...


_MenuAction = Callable[[object, object], None]


class _SecondaryMenuTrayProtocol(Protocol):
    config: object
    _on_selected_device_color_clicked: _MenuAction
    _on_selected_device_brightness_clicked: _MenuAction
    _on_selected_device_turn_off_clicked: _MenuAction
    _on_selected_device_turn_on_clicked: _MenuAction


def selected_secondary_is_off(tray: object, route: SecondaryDeviceRoute | None) -> bool:
    """Return whether the selected secondary route currently reads as off."""

    payload = vars(tray).get("_active_secondary_lighting")
    entry = secondary_lighting_state.area_entry(payload, getattr(route, "state_key", ""))
    if entry is not None and "enabled" in entry:
        return not secondary_lighting_state.entry_enabled(entry)
    return secondary_device_power.is_off(getattr(tray, "config", None), route)


def build_selected_secondary_section(
    tray_state: _SecondaryMenuTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    selected_context: Mapping[str, object],
    selected_route: SecondaryDeviceRoute | None,
    controls_available: bool,
) -> tuple[object, list[object]]:
    """Build the brightness item and hardware-mode items for a secondary device.

    Owns brightness-policy branching (independent level menu, primary-shared
    notice, unsupported notice) plus the static-color / turn on-off items,
    including the secondary lighting-state power read and device label.
    """

    if selected_route is not None and selected_route.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT:
        selected_brightness_menu = pystray.Menu(
            *[
                item(
                    str(level),
                    tray_state._on_selected_device_brightness_clicked,
                    checked=lambda _i, current=level, route=selected_route: (
                        secondary_device_power.current_brightness(tray_state.config, route) == current * 5
                    ),
                    radio=True,
                    enabled=controls_available,
                )
                for level in range(11)
            ]
        )
        selected_brightness_item = item("Brightness Override", selected_brightness_menu)
    elif selected_route is not None and selected_route.brightness_policy == BRIGHTNESS_POLICY_PRIMARY_SHARED:
        selected_brightness_item = item("Brightness Override (follows Keyboard)", None, enabled=False)
    else:
        selected_brightness_item = item("Brightness Override (not supported)", None, enabled=False)

    device_label = (
        str(getattr(selected_route, "display_name", "") or "").strip()
        or str(selected_context.get("device_type") or "device").replace("_", " ").title()
    )
    selected_device_is_off = selected_secondary_is_off(tray_state, selected_route)
    hardware_mode_items: list[object] = [
        item(
            "Static Color…",
            tray_state._on_selected_device_color_clicked,
            enabled=bool(selected_route and selected_route.supports_uniform_color and controls_available),
        ),
        item(
            f"Turn {'On' if selected_device_is_off else 'Off'} {device_label}",
            (
                tray_state._on_selected_device_turn_on_clicked
                if selected_device_is_off
                else tray_state._on_selected_device_turn_off_clicked
            ),
            enabled=controls_available,
        ),
    ]
    return selected_brightness_item, hardware_mode_items


__all__ = [
    "build_selected_secondary_section",
    "selected_secondary_is_off",
]
