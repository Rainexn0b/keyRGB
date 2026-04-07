from __future__ import annotations

from types import SimpleNamespace

from src.tray.ui import menu_sections


class _MenuItem:
    def __init__(self, text, action=None, **kwargs):
        self.text = text
        self.action = action
        self.kwargs = kwargs


class _Menu:
    SEPARATOR = object()

    def __call__(self, *items):
        return list(items)


class _Pystray:
    Menu = _Menu()


def _item(text, action=None, **kwargs):
    return _MenuItem(text, action, **kwargs)


def test_build_device_context_menu_items_shows_uniform_controls_for_mouse_route() -> None:
    tray = SimpleNamespace(
        config=SimpleNamespace(
            get_secondary_device_brightness=lambda state_key, *, fallback_keys=(), default=0: 25,
        ),
        _on_selected_device_color_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_brightness_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_turn_off_clicked=lambda *_args, **_kwargs: None,
        _on_support_debug_clicked=lambda *_args, **_kwargs: None,
        _on_power_settings_clicked=lambda *_args, **_kwargs: None,
        _on_quit_clicked=lambda *_args, **_kwargs: None,
    )
    context_entry = {
        "key": "mouse:sysfs:usbmouse__rgb",
        "device_type": "mouse",
        "backend_name": "sysfs-mouse",
        "status": "supported",
        "text": "Mouse: usbmouse::rgb",
    }

    items = menu_sections.build_device_context_menu_items(tray, pystray=_Pystray(), item=_item, context_entry=context_entry)

    assert items[0].text == "Color…"
    assert items[1].text == "Brightness"
    assert items[3].text == "Turn Off"