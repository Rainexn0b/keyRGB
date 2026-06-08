from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from src.tray import secondary_device_power
from src.tray.secondary_device_routes import SecondaryDeviceRoute

from .menu_status import DeviceContextEntry


MenuAction = Callable[..., None]
CheckedMenuItem = Callable[[object], bool]
ControlsAvailableResolver = Callable[[object, DeviceContextEntry], bool]
RouteResolver = Callable[[Mapping[str, object] | None], SecondaryDeviceRoute | None]


class SafeIntAttrResolver(secondary_device_power.SafeIntAttrReader, Protocol):
    def __call__(
        self,
        obj: object,
        attr_name: str,
        *,
        default: int = 0,
        min_v: int | None = None,
        max_v: int | None = None,
    ) -> int: ...


class _DeviceContextFooterTrayProtocol(Protocol):
    _on_support_debug_clicked: MenuAction
    _on_power_settings_clicked: MenuAction
    _on_quit_clicked: MenuAction


class _DeviceContextTrayProtocol(_DeviceContextFooterTrayProtocol, Protocol):
    config: object | None
    _on_selected_device_color_clicked: MenuAction
    _on_selected_device_brightness_clicked: MenuAction
    _on_selected_device_turn_off_clicked: MenuAction
    _on_selected_device_turn_on_clicked: MenuAction


class _MenuFactoryProtocol(Protocol):
    SEPARATOR: object

    def __call__(self, *items: object) -> object: ...


class _PystrayProtocol(Protocol):
    Menu: _MenuFactoryProtocol


class _ItemFactoryProtocol(Protocol):
    def __call__(self, text: str, action: object | None = None, **kwargs: object) -> object: ...


class _DeviceContextMenuBuilder(Protocol):
    def __call__(
        self,
        tray: _DeviceContextTrayProtocol,
        *,
        pystray: _PystrayProtocol,
        item: _ItemFactoryProtocol,
        context_entry: DeviceContextEntry,
        route_for_context_entry: RouteResolver,
        device_context_controls_available: ControlsAvailableResolver,
        safe_int_attr: SafeIntAttrResolver,
    ) -> list[object]: ...


def _device_context_footer_items(
    tray: _DeviceContextFooterTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
) -> list[object]:
    return [
        pystray.Menu.SEPARATOR,
        item("Support Tools…", tray._on_support_debug_clicked),
        item("Settings", tray._on_power_settings_clicked),
        pystray.Menu.SEPARATOR,
        item("Quit", tray._on_quit_clicked),
    ]


def _unsupported_device_context_text(device_label: str, status: str) -> str:
    return {
        "known_dormant": f"{device_label} detected, but this backend is still dormant in this build",
        "experimental_disabled": f"{device_label} backend is present but disabled by experimental-backend policy",
        "known_unavailable": f"{device_label} was identified, but it is not currently available for control",
        "unrecognized_ite": f"{device_label} was detected, but it is not recognized by a supported backend yet",
    }.get(status, f"{device_label} controls are not available in this build")


def _secondary_brightness_matches(
    tray: _DeviceContextTrayProtocol,
    *,
    route: SecondaryDeviceRoute | None,
    expected_level: int,
    safe_int_attr: SafeIntAttrResolver,
) -> bool:
    return (
        secondary_device_power.current_brightness(tray.config, route, safe_int_attr=safe_int_attr) == expected_level * 5
    )


def _build_uniform_secondary_context_menu_items(
    tray: _DeviceContextTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    context_entry: DeviceContextEntry,
    route_for_context_entry: RouteResolver,
    device_context_controls_available: ControlsAvailableResolver,
    safe_int_attr: SafeIntAttrResolver,
) -> list[object]:
    route = route_for_context_entry(context_entry)
    device_label = (
        str(route.display_name if route is not None else "").strip()
        or str(context_entry.get("device_type") or "device").replace("_", " ").title()
    )
    controls_available = device_context_controls_available(tray, context_entry)
    body: list[object]
    if controls_available and route is not None and bool(route.supports_uniform_color):
        body = [item("Color…", tray._on_selected_device_color_clicked)]

        def _checked_secondary_brightness(level: int) -> CheckedMenuItem:
            def _checked(_item: object) -> bool:
                return _secondary_brightness_matches(
                    tray,
                    route=route,
                    expected_level=level,
                    safe_int_attr=safe_int_attr,
                )

            return _checked

        brightness_menu = pystray.Menu(
            *[
                item(
                    str(level),
                    tray._on_selected_device_brightness_clicked,
                    checked=_checked_secondary_brightness(level),
                    radio=True,
                )
                for level in range(0, 11)
            ]
        )
        body.extend(
            [
                item("Brightness", brightness_menu),
                pystray.Menu.SEPARATOR,
            ]
        )
        is_off = secondary_device_power.is_off(tray.config, route, safe_int_attr=safe_int_attr)
        body.append(
            item(
                "Turn On" if is_off else "Turn Off",
                tray._on_selected_device_turn_on_clicked if is_off else tray._on_selected_device_turn_off_clicked,
            )
        )
    else:
        body = [
            item(
                _unsupported_device_context_text(device_label, str(context_entry.get("status") or "").strip()),
                lambda _icon, _item: None,
                enabled=False,
            )
        ]

    return [*body, *_device_context_footer_items(tray, pystray=pystray, item=item)]


def _build_lightbar_context_menu_items(
    tray: _DeviceContextTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    context_entry: DeviceContextEntry,
    route_for_context_entry: RouteResolver,
    device_context_controls_available: ControlsAvailableResolver,
    safe_int_attr: SafeIntAttrResolver,
) -> list[object]:
    return _build_uniform_secondary_context_menu_items(
        tray,
        pystray=pystray,
        item=item,
        context_entry=context_entry,
        route_for_context_entry=route_for_context_entry,
        device_context_controls_available=device_context_controls_available,
        safe_int_attr=safe_int_attr,
    )


def _build_generic_device_context_menu_items(
    tray: _DeviceContextTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    context_entry: DeviceContextEntry,
    route_for_context_entry: RouteResolver,
    device_context_controls_available: ControlsAvailableResolver,
    safe_int_attr: SafeIntAttrResolver,
) -> list[object]:
    device_label = str(context_entry.get("device_type") or "device").replace("_", " ").title()
    controls_available = device_context_controls_available(tray, context_entry)
    body: list[object]
    if controls_available:
        body = [
            item(
                f"{device_label} controls will be provided by its dedicated controller surface",
                lambda _icon, _item: None,
                enabled=False,
            )
        ]
    else:
        body = [
            item(
                _unsupported_device_context_text(device_label, str(context_entry.get("status") or "").strip()),
                lambda _icon, _item: None,
                enabled=False,
            )
        ]

    return [*body, *_device_context_footer_items(tray, pystray=pystray, item=item)]


_DEVICE_CONTEXT_MENU_BUILDERS: dict[str, _DeviceContextMenuBuilder] = {
    "lightbar": _build_lightbar_context_menu_items,
    "mouse": _build_uniform_secondary_context_menu_items,
}


def build_device_context_menu_items(
    tray: _DeviceContextTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    context_entry: DeviceContextEntry,
    route_for_context_entry: RouteResolver,
    device_context_controls_available: ControlsAvailableResolver,
    safe_int_attr: SafeIntAttrResolver,
) -> list[object]:
    """Build a selected device-context surface for non-keyboard devices."""

    device_type = str(context_entry.get("device_type") or "").strip().lower()
    builder = _DEVICE_CONTEXT_MENU_BUILDERS.get(device_type)

    if builder is None:
        route = route_for_context_entry(context_entry)
        if route is not None and bool(route.supports_uniform_color):
            builder = _build_uniform_secondary_context_menu_items
        else:
            builder = _build_generic_device_context_menu_items

    return builder(
        tray,
        pystray=pystray,
        item=item,
        context_entry=context_entry,
        route_for_context_entry=route_for_context_entry,
        device_context_controls_available=device_context_controls_available,
        safe_int_attr=safe_int_attr,
    )
