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


def test_sw_effects_menu_first_item_is_reactive_typing_settings() -> None:
    """The Software Effects submenu must open with 'Reactive Typing Settings...' -
    confirmed after the rename from 'Reactive Typing Color...'."""
    import inspect

    from src.tray.ui import _menu_sections_effects as menu_effects

    # Label lives in the extracted effects section builder (WS1 / A8).
    src = inspect.getsource(menu_effects)
    assert "Reactive Typing Settings" in src
    assert "Reactive Typing Color" not in src
    # Parent orchestrator must not reintroduce the old label.
    assert "Reactive Typing Color" not in inspect.getsource(menu)


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
