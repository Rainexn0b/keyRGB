from __future__ import annotations

from types import SimpleNamespace

import pytest

from types import SimpleNamespace

from src.tray.ui import menu, menu_sections


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

def test_sw_effects_menu_first_item_is_reactive_typing_settings() -> None:
    """The Software Effects submenu must open with 'Reactive Typing Settings...' -
    confirmed after the rename from 'Reactive Typing Color...'."""
    import inspect
    src = inspect.getsource(menu)
    assert "Reactive Typing Settings" in src
    assert "Reactive Typing Color" not in src


def test_tcc_profile_callback_logs_recoverable_runtime_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[tuple[str, str, Exception]] = []

    monkeypatch.setattr(
        menu_sections,
        "_log_menu_debug",
        lambda key, msg, exc, *, interval_s=60: logged.append((key, msg, exc)),
    )

    tray = SimpleNamespace(
        _on_tcc_profile_clicked=lambda _profile_id: (_ for _ in ()).throw(RuntimeError("tcc boom")),
        _on_tcc_profiles_gui_clicked=lambda *_args, **_kwargs: None,
    )
    tcc = SimpleNamespace(
        list_profiles=lambda: [SimpleNamespace(id="balanced", name="Balanced")],
        get_active_profile=lambda: None,
    )

    menu_items = menu_sections.build_tcc_profiles_menu(tray, pystray=_Pystray(), item=_item, tcc=tcc)

    assert isinstance(menu_items, list)
    menu_items[2].action(None, None)

    assert len(logged) == 1
    assert logged[0][0] == "tray.menu.tcc_profile_click"
    assert isinstance(logged[0][2], RuntimeError)


def test_tcc_profile_callback_propagates_unexpected_errors() -> None:
    tray = SimpleNamespace(
        _on_tcc_profile_clicked=lambda _profile_id: (_ for _ in ()).throw(AssertionError("unexpected tcc bug")),
        _on_tcc_profiles_gui_clicked=lambda *_args, **_kwargs: None,
    )
    tcc = SimpleNamespace(
        list_profiles=lambda: [SimpleNamespace(id="balanced", name="Balanced")],
        get_active_profile=lambda: None,
    )

    menu_items = menu_sections.build_tcc_profiles_menu(tray, pystray=_Pystray(), item=_item, tcc=tcc)

    assert isinstance(menu_items, list)
    with pytest.raises(AssertionError, match="unexpected tcc bug"):
        menu_items[2].action(None, None)


def test_perkey_profile_callback_logs_recoverable_runtime_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.profile import profiles as core_profiles

    logged: list[tuple[str, str, Exception]] = []

    monkeypatch.setattr(
        menu_sections,
        "_log_menu_debug",
        lambda key, msg, exc, *, interval_s=60: logged.append((key, msg, exc)),
    )
    monkeypatch.setattr(core_profiles, "list_profiles", lambda: ["gaming"])
    monkeypatch.setattr(core_profiles, "get_active_profile", lambda: None)
    monkeypatch.setattr(
        core_profiles,
        "set_active_profile",
        lambda _name: (_ for _ in ()).throw(RuntimeError("perkey boom")),
    )

    tray = SimpleNamespace(
        config=SimpleNamespace(),
        is_off=True,
        _start_current_effect=lambda: None,
        _update_icon=lambda: None,
        _update_menu=lambda: None,
        _on_perkey_clicked=lambda *_args, **_kwargs: None,
    )

    menu_items = menu_sections.build_perkey_profiles_menu(
        tray,
        pystray=_Pystray(),
        item=_item,
        per_key_supported=True,
    )

    assert isinstance(menu_items, list)
    menu_items[2].action(None, None)

    assert len(logged) == 1
    assert logged[0][0] == "tray.menu.perkey_profile_click"
    assert isinstance(logged[0][2], RuntimeError)


def test_perkey_profile_callback_propagates_unexpected_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.profile import profiles as core_profiles

    monkeypatch.setattr(core_profiles, "list_profiles", lambda: ["gaming"])
    monkeypatch.setattr(core_profiles, "get_active_profile", lambda: None)
    monkeypatch.setattr(
        core_profiles,
        "set_active_profile",
        lambda _name: (_ for _ in ()).throw(AssertionError("unexpected perkey bug")),
    )

    tray = SimpleNamespace(
        config=SimpleNamespace(),
        is_off=True,
        _start_current_effect=lambda: None,
        _update_icon=lambda: None,
        _update_menu=lambda: None,
        _on_perkey_clicked=lambda *_args, **_kwargs: None,
    )

    menu_items = menu_sections.build_perkey_profiles_menu(
        tray,
        pystray=_Pystray(),
        item=_item,
        per_key_supported=True,
    )

    assert isinstance(menu_items, list)
    with pytest.raises(AssertionError, match="unexpected perkey bug"):
        menu_items[2].action(None, None)
