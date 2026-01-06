from __future__ import annotations

from types import SimpleNamespace


def test_update_icon_noop_without_icon(monkeypatch) -> None:
    from src.tray.ui.refresh import update_icon

    tray = SimpleNamespace(icon=None, config=SimpleNamespace(), is_off=False)
    update_icon(tray)


def test_update_icon_sets_icon_image(monkeypatch) -> None:
    import src.tray.ui.refresh as refresh

    calls = {"n": 0}

    monkeypatch.setattr(refresh.icon_mod, "representative_color", lambda *, config, is_off: (1, 2, 3))
    monkeypatch.setattr(
        refresh.icon_mod,
        "create_icon",
        lambda color: (calls.__setitem__("n", calls["n"] + 1) or f"icon:{color}"),
    )

    tray = SimpleNamespace(icon=SimpleNamespace(icon=None), config=SimpleNamespace(), is_off=True)

    refresh.update_icon(tray)
    assert tray.icon.icon == "icon:(1, 2, 3)"
    assert calls["n"] == 1


def test_update_menu_noop_without_icon(monkeypatch) -> None:
    from src.tray.ui.refresh import update_menu

    tray = SimpleNamespace(icon=None, config=SimpleNamespace(reload=lambda: None))
    update_menu(tray)


def test_update_menu_reloads_and_builds_menu(monkeypatch) -> None:
    import src.tray.ui.refresh as refresh

    tray = SimpleNamespace(icon=SimpleNamespace(menu=None), config=SimpleNamespace(reload=lambda: None))

    monkeypatch.setattr(refresh.runtime, "get_pystray", lambda: (object(), object()))
    monkeypatch.setattr(refresh.menu_mod, "build_menu", lambda tray, *, pystray, item: "MENU")

    refresh.update_menu(tray)
    assert tray.icon.menu == "MENU"


def test_refresh_ui_calls_both(monkeypatch) -> None:
    import src.tray.ui.refresh as refresh

    calls = {"icon": 0, "menu": 0}

    monkeypatch.setattr(
        refresh,
        "update_icon",
        lambda _tray: calls.__setitem__("icon", calls["icon"] + 1),
    )
    monkeypatch.setattr(
        refresh,
        "update_menu",
        lambda _tray: calls.__setitem__("menu", calls["menu"] + 1),
    )

    refresh.refresh_ui(SimpleNamespace())
    assert calls == {"icon": 1, "menu": 1}
