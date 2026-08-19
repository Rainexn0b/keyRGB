from __future__ import annotations

from types import SimpleNamespace


def test_update_icon_noop_without_icon(monkeypatch) -> None:
    from keyrgb.tray.ui.refresh import update_icon

    tray = SimpleNamespace(icon=None, config=SimpleNamespace(), is_off=False)
    update_icon(tray)


def test_update_icon_sets_icon_image(monkeypatch) -> None:
    from keyrgb.tray.ui import refresh

    calls = {"n": 0}

    monkeypatch.setattr(
        refresh.icon_mod,
        "representative_color",
        lambda *, config, is_off, now=None, backend=None, engine=None: (1, 2, 3),
    )
    monkeypatch.setattr(
        refresh.icon_mod,
        "create_icon",
        lambda color: calls.__setitem__("n", calls["n"] + 1) or f"icon:{color}",
    )

    tray = SimpleNamespace(icon=SimpleNamespace(icon=None), config=SimpleNamespace(), is_off=True, backend=None)

    refresh.update_icon(tray)
    assert tray.icon.icon == "icon:(1, 2, 3)"
    assert calls["n"] == 1


def test_update_menu_noop_without_icon(monkeypatch) -> None:
    from keyrgb.tray.ui.refresh import update_menu

    tray = SimpleNamespace(icon=None, config=SimpleNamespace(reload=lambda: None))
    update_menu(tray)


def test_update_menu_builds_from_committed_state_without_reloading(monkeypatch) -> None:
    from keyrgb.tray.ui import refresh

    reload_calls: list[str] = []
    tray = SimpleNamespace(
        icon=SimpleNamespace(menu=None),
        config=SimpleNamespace(reload=lambda: reload_calls.append("reload")),
    )

    monkeypatch.setattr(refresh.runtime, "get_pystray", lambda: (object(), object()))
    monkeypatch.setattr(refresh.menu_mod, "build_menu", lambda tray, *, pystray, item: "MENU")

    refresh.update_menu(tray)
    assert tray.icon.menu == "MENU"
    assert reload_calls == []


def test_refresh_ui_calls_both(monkeypatch) -> None:
    from keyrgb.tray.ui import refresh

    calls = {"icon": 0, "menu": 0}

    monkeypatch.setattr(
        refresh,
        "update_icon",
        lambda _tray, animate=True: calls.__setitem__("icon", calls["icon"] + 1),
    )
    monkeypatch.setattr(
        refresh,
        "update_menu",
        lambda _tray: calls.__setitem__("menu", calls["menu"] + 1),
    )

    refresh.refresh_ui(SimpleNamespace())
    assert calls == {"icon": 1, "menu": 1}
