from __future__ import annotations

from types import SimpleNamespace

import pytest


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
        _on_selected_device_turn_on_clicked=lambda *_args, **_kwargs: None,
        _on_support_debug_clicked=lambda *_args, **_kwargs: None,
        _on_power_settings_clicked=lambda *_args, **_kwargs: None,
        _on_power_mode_settings_clicked=lambda *_args, **_kwargs: None,
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


def test_build_device_context_menu_items_shows_turn_on_when_secondary_route_is_off() -> None:
    def turn_on_action(*_args, **_kwargs):
        return None
    def turn_off_action(*_args, **_kwargs):
        return None
    tray = SimpleNamespace(
        config=SimpleNamespace(
            get_secondary_device_brightness=lambda state_key, *, fallback_keys=(), default=0: 0,
        ),
        _on_selected_device_color_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_brightness_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_turn_off_clicked=turn_off_action,
        _on_selected_device_turn_on_clicked=turn_on_action,
        _on_support_debug_clicked=lambda *_args, **_kwargs: None,
        _on_power_settings_clicked=lambda *_args, **_kwargs: None,
        _on_power_mode_settings_clicked=lambda *_args, **_kwargs: None,
        _on_quit_clicked=lambda *_args, **_kwargs: None,
    )
    context_entry = {
        "key": "lightbar:048d:7001",
        "device_type": "lightbar",
        "backend_name": "ite8233_lightbar",
        "status": "supported",
        "text": "Lightbar",
    }

    items = menu_sections.build_device_context_menu_items(tray, pystray=_Pystray(), item=_item, context_entry=context_entry)

    assert items[3].text == "Turn On"
    assert items[3].action is turn_on_action


def test_build_device_context_menu_items_shows_unsupported_generic_device_with_footer() -> None:
    tray = SimpleNamespace(
        _on_support_debug_clicked=lambda *_args, **_kwargs: None,
        _on_power_settings_clicked=lambda *_args, **_kwargs: None,
        _on_power_mode_settings_clicked=lambda *_args, **_kwargs: None,
        _on_quit_clicked=lambda *_args, **_kwargs: None,
    )
    context_entry = {
        "device_type": "touchpad",
        "status": "known_unavailable",
    }

    items = menu_sections.build_device_context_menu_items(tray, pystray=_Pystray(), item=_item, context_entry=context_entry)
    texts = [entry.text for entry in items if hasattr(entry, "text")]

    assert texts == [
        "Touchpad was identified, but it is not currently available for control",
        "Support Tools…",
        "Settings",
        "Quit",
    ]
    assert items[0].kwargs["enabled"] is False


def test_build_device_context_menu_items_uses_facade_collaborators_for_fallback_brightness_checked_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collaborator_calls: list[tuple[str, str]] = []
    safe_int_calls: list[tuple[object, str, int, object, object]] = []
    route = SimpleNamespace(
        display_name="Rear Lightbar",
        supports_uniform_color=True,
        state_key="lightbar",
        config_brightness_attr="lightbar_brightness",
    )

    monkeypatch.setattr(
        menu_sections,
        "route_for_context_entry",
        lambda context_entry: collaborator_calls.append(("route", str(context_entry["device_type"]))) or route,
    )
    monkeypatch.setattr(
        menu_sections,
        "device_context_controls_available",
        lambda tray, context_entry: collaborator_calls.append(("controls", str(context_entry["device_type"]))) or True,
    )
    monkeypatch.setattr(
        menu_sections,
        "safe_int_attr",
        lambda config, attr_name, *, default=0, min_v=None, max_v=None: safe_int_calls.append(
            (config, attr_name, default, min_v, max_v)
        ) or 15,
    )

    tray = SimpleNamespace(
        config=SimpleNamespace(lightbar_brightness=0),
        _on_selected_device_color_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_brightness_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_turn_off_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_turn_on_clicked=lambda *_args, **_kwargs: None,
        _on_support_debug_clicked=lambda *_args, **_kwargs: None,
        _on_power_settings_clicked=lambda *_args, **_kwargs: None,
        _on_power_mode_settings_clicked=lambda *_args, **_kwargs: None,
        _on_quit_clicked=lambda *_args, **_kwargs: None,
    )

    items = menu_sections.build_device_context_menu_items(
        tray,
        pystray=_Pystray(),
        item=_item,
        context_entry={"device_type": "lightbar", "status": "supported"},
    )

    brightness_items = items[1].action
    checked_entry = next(entry for entry in brightness_items if entry.text == "3")

    assert checked_entry.kwargs["checked"](checked_entry) is True
    assert collaborator_calls == [("route", "lightbar"), ("controls", "lightbar")]
    assert len(safe_int_calls) == 2
    assert all(call[1] == "lightbar_brightness" for call in safe_int_calls)
    assert all(call[2] == 0 for call in safe_int_calls)


def test_sw_effects_menu_first_item_is_reactive_typing_settings() -> None:
    """The Software Effects submenu must open with 'Reactive Typing Settings...' -
    confirmed after the rename from 'Reactive Typing Color...'."""
    import inspect
    src = inspect.getsource(menu)
    assert "Reactive Typing Settings" in src
    assert "Reactive Typing Color" not in src


def test_system_power_callback_uses_runtime_helper_collaborators(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        menu_sections,
        "get_status",
        lambda: SimpleNamespace(supported=True, identifiers={"can_apply": "true"}, mode=None),
    )
    monkeypatch.setattr(menu_sections, "set_mode", lambda _mode: True)
    monkeypatch.setattr(
        menu_sections.profile_power_menu_actions,
        "set_system_power_last_ok",
        lambda tray, ok: calls.append(("status", ok)),
    )
    monkeypatch.setattr(
        menu_sections.profile_power_menu_actions,
        "update_menu_if_present",
        lambda tray: calls.append(("refresh", tray)),
    )

    tray = SimpleNamespace(_on_power_mode_settings_clicked=lambda *_args, **_kwargs: None)
    menu_items = menu_sections.build_system_power_mode_menu(tray, pystray=_Pystray(), item=_item)

    assert isinstance(menu_items, list)
    menu_items[0].action(None, None)

    assert calls == [("status", True), ("refresh", tray)]


def test_system_power_menu_includes_settings_entry() -> None:
    tray = SimpleNamespace(_on_power_mode_settings_clicked=lambda *_args, **_kwargs: None)

    menu_items = menu_sections.ProfilePowerMenuBuilder(
        make_profile_activation_callback=lambda action, **_kwargs: lambda *_a, **_k: action(),
        log_menu_debug=lambda *_args, **_kwargs: None,
        get_status=lambda: SimpleNamespace(supported=True, identifiers={"can_apply": "true"}, mode=None),
        set_mode=lambda _mode: True,
        set_system_power_result=lambda *_args, **_kwargs: None,
        refresh_system_power_menu=lambda *_args, **_kwargs: None,
        list_perkey_profiles=lambda: [],
        get_active_perkey_profile=lambda: None,
        activate_perkey_profile=lambda *_args, **_kwargs: None,
    ).build_system_power_mode_menu(tray, pystray=_Pystray(), item=_item)

    assert isinstance(menu_items, list)
    assert [entry.text for entry in menu_items if hasattr(entry, "text")] == [
        "Extreme Saver",
        "Balanced",
        "Performance",
        "Power Mode Settings…",
    ]


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


def test_perkey_profile_callback_uses_profile_activation_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, str]] = []

    monkeypatch.setattr(menu_sections.profile_power_menu_actions, "list_perkey_profiles", lambda: ["gaming"])
    monkeypatch.setattr(menu_sections.profile_power_menu_actions, "get_active_perkey_profile", lambda: None)
    monkeypatch.setattr(
        menu_sections.profile_power_menu_actions,
        "activate_perkey_profile",
        lambda tray, profile_name: calls.append((tray, profile_name)),
    )

    tray = SimpleNamespace(
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

    assert calls == [(tray, "gaming")]


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


def test_build_device_context_menu_items_falls_back_to_uniform_builder_for_unknown_device_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Virtual zone routes (logo/neon/vent) should render uniform controls without needing a dedicated builder."""
    route = SimpleNamespace(
        display_name="Logo",
        supports_uniform_color=True,
        state_key="ite8258_chassis_logo",
        config_brightness_attr="ite8258_chassis_logo_brightness",
    )

    monkeypatch.setattr(
        menu_sections,
        "route_for_context_entry",
        lambda _context_entry: route,
    )

    tray = SimpleNamespace(
        config=SimpleNamespace(
            get_secondary_device_brightness=lambda state_key, *, fallback_keys=(), default=0: 25,
        ),
        _on_selected_device_color_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_brightness_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_turn_off_clicked=lambda *_args, **_kwargs: None,
        _on_selected_device_turn_on_clicked=lambda *_args, **_kwargs: None,
        _on_support_debug_clicked=lambda *_args, **_kwargs: None,
        _on_power_settings_clicked=lambda *_args, **_kwargs: None,
        _on_power_mode_settings_clicked=lambda *_args, **_kwargs: None,
        _on_quit_clicked=lambda *_args, **_kwargs: None,
    )
    context_entry = {
        "key": "ite8258-chassis-logo",
        "device_type": "logo",
        "backend_name": "ite8258-chassis-logo",
        "status": "supported",
        "text": "Logo",
    }

    items = menu_sections.build_device_context_menu_items(tray, pystray=_Pystray(), item=_item, context_entry=context_entry)

    assert items[0].text == "Color…"
    assert items[1].text == "Brightness"
    assert items[3].text == "Turn Off"


def test_build_device_context_menu_items_still_shows_generic_for_unsupported_unknown_device_type() -> None:
    tray = SimpleNamespace(
        _on_support_debug_clicked=lambda *_args, **_kwargs: None,
        _on_power_settings_clicked=lambda *_args, **_kwargs: None,
        _on_power_mode_settings_clicked=lambda *_args, **_kwargs: None,
        _on_quit_clicked=lambda *_args, **_kwargs: None,
    )
    context_entry = {
        "device_type": "fan_controller",
        "status": "known_unavailable",
    }

    items = menu_sections.build_device_context_menu_items(tray, pystray=_Pystray(), item=_item, context_entry=context_entry)
    texts = [entry.text for entry in items if hasattr(entry, "text")]

    assert texts == [
        "Fan Controller was identified, but it is not currently available for control",
        "Support Tools…",
        "Settings",
        "Quit",
    ]
