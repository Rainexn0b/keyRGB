"""Tray UI refresh helpers."""

from __future__ import annotations

from typing import Any

from ..integrations import runtime
from . import icon as icon_mod
from . import menu as menu_mod


def update_icon(tray: Any) -> None:
    """Update the tray icon image based on current config state."""

    if getattr(tray, "icon", None):
        color = icon_mod.representative_color(config=tray.config, is_off=tray.is_off)
        tray.icon.icon = icon_mod.create_icon(color)


def update_menu(tray: Any) -> None:
    """Rebuild the tray menu from current config/backend state."""

    if getattr(tray, "icon", None):
        tray.config.reload()
        pystray, item = runtime.get_pystray()
        tray.icon.menu = menu_mod.build_menu(tray, pystray=pystray, item=item)


def refresh_ui(tray: Any) -> None:
    """Refresh both icon and menu."""

    update_icon(tray)
    update_menu(tray)
