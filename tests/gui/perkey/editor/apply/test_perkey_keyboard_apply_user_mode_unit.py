from __future__ import annotations

import pytest

import src.gui.perkey.keyboard_apply as keyboard_apply
from src.gui.perkey.keyboard_apply import push_per_key_colors


def test_push_per_key_colors_returns_none_when_keyboard_handle_is_missing() -> None:
    assert push_per_key_colors(None, {(0, 0): (1, 2, 3)}, brightness=20) is None


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


def test_push_per_key_colors_falls_back_when_enable_user_mode_rejects_save_kwarg() -> None:
    calls: list[tuple[str, object]] = []

    class DummyKb:
        def enable_user_mode(self, *, brightness: int, save: bool = False):
            if save:
                raise TypeError("no save kwarg")
            calls.append(("enable_user_mode", brightness))

        def set_key_colors(self, colors, *, brightness: int, enable_user_mode: bool = True):
            calls.append(("set_key_colors", (dict(colors), brightness, enable_user_mode)))

    kb = DummyKb()

    out = push_per_key_colors(kb, {(0, 0): (10, 20, 30)}, brightness=31, enable_user_mode=True)

    assert out is kb
    assert calls == [
        ("enable_user_mode", 31),
        ("set_key_colors", ({(0, 0): (10, 20, 30)}, 31, True)),
    ]


def test_push_per_key_colors_ignores_enable_user_mode_failures_and_still_sets_colors() -> None:
    calls: list[str] = []

    class DummyKb:
        def enable_user_mode(self, *, brightness: int, save: bool = False):
            raise RuntimeError("boom")

        def set_key_colors(self, colors, *, brightness: int, enable_user_mode: bool = True):
            calls.append("set")

    kb = DummyKb()

    out = push_per_key_colors(kb, {(0, 0): (1, 2, 3)}, brightness=18, enable_user_mode=True)

    assert out is kb
    assert calls == ["set"]


@pytest.mark.parametrize(
    ("exc", "busy", "disconnected", "expected"),
    [
        (OSError("device issue"), True, False, None),
        (OSError("device issue"), False, True, None),
        (OSError("device issue"), False, False, "kb"),
    ],
)
def test_push_per_key_colors_handles_recoverable_device_states(
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
    busy: bool,
    disconnected: bool,
    expected,
) -> None:
    class DummyKb:
        def set_key_colors(self, colors, *, brightness: int, enable_user_mode: bool = True):
            raise exc

    kb = DummyKb()
    monkeypatch.setattr(keyboard_apply, "is_device_busy", lambda raised_exc: raised_exc is exc and busy)
    monkeypatch.setattr(
        keyboard_apply,
        "is_device_disconnected",
        lambda raised_exc: raised_exc is exc and disconnected,
    )

    out = push_per_key_colors(kb, {(0, 0): (1, 2, 3)}, brightness=10, enable_user_mode=False)

    assert out is (kb if expected == "kb" else None)


def test_push_per_key_colors_returns_keyboard_for_other_recoverable_exceptions() -> None:
    class DummyKb:
        def set_key_colors(self, colors, *, brightness: int, enable_user_mode: bool = True):
            raise LookupError("boom")

    kb = DummyKb()

    out = push_per_key_colors(kb, {(0, 0): (1, 2, 3)}, brightness=10, enable_user_mode=False)

    assert out is kb


def test_push_per_key_colors_returns_keyboard_for_unexpected_write_exceptions() -> None:
    class DummyKb:
        def set_key_colors(self, colors, *, brightness: int, enable_user_mode: bool = True):
            raise AssertionError("boom")

    kb = DummyKb()

    out = push_per_key_colors(kb, {(0, 0): (1, 2, 3)}, brightness=10, enable_user_mode=False)

    assert out is kb
