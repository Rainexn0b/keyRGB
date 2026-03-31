from __future__ import annotations

from src.tray.app.application import KeyRGBTray


def test_tray_refresh_ui_calls_icon_and_menu() -> None:
    assert hasattr(KeyRGBTray, "_refresh_ui")

    calls: list[str] = []

    class DummyTray:
        def _update_icon(self) -> None:  # noqa: D401
            calls.append("icon")

        def _update_menu(self) -> None:
            calls.append("menu")

    dummy = DummyTray()

    # Call the method unbound to avoid constructing the real tray (which pulls
    # in desktop/hardware dependencies).
    KeyRGBTray._refresh_ui(dummy)  # type: ignore[arg-type]

    assert calls == ["icon", "menu"]
