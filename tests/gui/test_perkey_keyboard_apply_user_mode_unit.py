from __future__ import annotations

from src.gui.perkey.keyboard_apply import push_per_key_colors


def test_push_per_key_colors_enables_user_mode_save_true_when_available() -> None:
    calls: list[tuple[str, object]] = []

    class DummyKb:
        def enable_user_mode(self, *, brightness: int, save: bool):
            calls.append(("enable_user_mode", (brightness, save)))

        def set_key_colors(self, colors, *, brightness: int, enable_user_mode: bool = True):
            calls.append(("set_key_colors", (dict(colors), brightness, enable_user_mode)))

    kb = DummyKb()
    colors = {(0, 0): (10, 20, 30)}

    out = push_per_key_colors(kb, colors, brightness=25, enable_user_mode=True)
    assert out is kb

    assert calls[0] == ("enable_user_mode", (25, True))
    assert calls[1][0] == "set_key_colors"


def test_push_per_key_colors_works_when_enable_user_mode_not_supported() -> None:
    calls: list[tuple[str, object]] = []

    class DummyKb:
        def set_key_colors(self, colors, *, brightness: int, enable_user_mode: bool = True):
            calls.append(("set_key_colors", (dict(colors), brightness, enable_user_mode)))

    kb = DummyKb()
    colors = {(0, 0): (10, 20, 30)}

    out = push_per_key_colors(kb, colors, brightness=25, enable_user_mode=True)
    assert out is kb
    assert calls == [("set_key_colors", (colors, 25, True))]
